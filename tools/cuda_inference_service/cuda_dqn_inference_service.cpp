#include <cuda.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#pragma comment(lib, "Ws2_32.lib")

static const char* ACTION_TYPES[] = {
    "KEEP_CURRENT_SCHEDULE",
    "REQUEST_MATERIAL_REPLENISHMENT",
    "INCREASE_ORDER_PRIORITY",
    "REASSIGN_MACHINE",
    "PAUSE_LOW_PRIORITY_ORDER",
    "MAINTENANCE_CHECK",
    "OVERTIME_PRODUCTION",
    "ADJUST_BATCH_SIZE"
};

static const char* ACTION_NAMES[] = {
    "維持目前排程",
    "優先補線邊庫",
    "優先生產高缺貨風險品項",
    "改派可用 CNC",
    "暫緩低優先級工單",
    "安排換刀 / 保養",
    "啟動加班生產",
    "調整批量"
};

static const char* ACTION_REASONS[] = {
    "CUDA 缺貨優先 DQN 判斷目前缺貨與交期風險可控，建議維持目前排程。",
    "CUDA 缺貨優先 DQN 判斷線邊庫缺料或缺貨風險高，建議優先補線邊庫。",
    "CUDA 缺貨優先 DQN 判斷客戶缺貨或交期延遲風險高，建議優先生產高缺貨風險品項。",
    "CUDA 缺貨優先 DQN 判斷目前 CNC OEE 偏低或狀態不佳，建議改派可用 CNC。",
    "CUDA 缺貨優先 DQN 判斷此工單缺貨風險低，必要時可暫緩讓位給高缺貨風險工單。",
    "CUDA 缺貨優先 DQN 判斷設備、刀具、品質或電力特徵異常，建議安排換刀 / 保養。",
    "CUDA 缺貨優先 DQN 判斷缺貨與交期壓力高，建議啟動加班生產。",
    "CUDA 缺貨優先 DQN 判斷可透過調整批量降低缺貨或線邊庫壓力。"
};

static std::string cuda_error(CUresult result) {
    const char* name = nullptr;
    const char* desc = nullptr;
    cuGetErrorName(result, &name);
    cuGetErrorString(result, &desc);
    std::ostringstream oss;
    oss << (name ? name : "CUDA_ERROR_UNKNOWN") << ": " << (desc ? desc : "no detail");
    return oss.str();
}

#define CHECK_CUDA(call) do { CUresult _r = (call); if (_r != CUDA_SUCCESS) throw std::runtime_error(cuda_error(_r)); } while (0)

static double json_number(const std::string& body, const std::string& key, double def = 0.0) {
    std::string pattern = "\"" + key + "\"";
    size_t pos = body.find(pattern);
    if (pos == std::string::npos) return def;
    pos = body.find(':', pos);
    if (pos == std::string::npos) return def;
    ++pos;
    while (pos < body.size() && std::isspace(static_cast<unsigned char>(body[pos]))) ++pos;
    size_t end = pos;
    while (end < body.size()) {
        char c = body[end];
        if (!(std::isdigit(static_cast<unsigned char>(c)) || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E')) break;
        ++end;
    }
    if (end == pos) return def;
    return std::atof(body.substr(pos, end - pos).c_str());
}

static bool json_bool(const std::string& body, const std::string& key, bool def = false) {
    std::string pattern = "\"" + key + "\"";
    size_t pos = body.find(pattern);
    if (pos == std::string::npos) return def;
    pos = body.find(':', pos);
    if (pos == std::string::npos) return def;
    ++pos;
    while (pos < body.size() && std::isspace(static_cast<unsigned char>(body[pos]))) ++pos;
    if (body.compare(pos, 4, "true") == 0) return true;
    if (body.compare(pos, 5, "false") == 0) return false;
    if (body.compare(pos, 1, "1") == 0) return true;
    if (body.compare(pos, 1, "0") == 0) return false;
    return def;
}

static std::string json_string(const std::string& body, const std::string& key, const std::string& def = "") {
    std::string pattern = "\"" + key + "\"";
    size_t pos = body.find(pattern);
    if (pos == std::string::npos) return def;
    pos = body.find(':', pos);
    if (pos == std::string::npos) return def;
    pos = body.find('"', pos);
    if (pos == std::string::npos) return def;
    size_t end = body.find('"', pos + 1);
    if (end == std::string::npos) return def;
    return body.substr(pos + 1, end - pos - 1);
}

static int machine_status_code(const std::string& status) {
    if (status == "STOPPED") return 1;
    if (status == "ABNORMAL") return 2;
    return 0;
}

class CudaDqnEngine {
public:
    CudaDqnEngine(const std::string& ptx_path) {
        CHECK_CUDA(cuInit(0));
        CHECK_CUDA(cuDeviceGet(&device_, 0));
        CHECK_CUDA(cuDeviceGetName(device_name_, sizeof(device_name_), device_));
        CHECK_CUDA(cuCtxCreate(&context_, 0, device_));
        CHECK_CUDA(cuModuleLoad(&module_, ptx_path.c_str()));
        CHECK_CUDA(cuModuleGetFunction(&kernel_, module_, "dqn_policy_kernel"));
        CHECK_CUDA(cuModuleGetFunction(&reward_kernel_, module_, "reward_score_kernel"));
    }

    ~CudaDqnEngine() {
        if (module_) cuModuleUnload(module_);
        if (context_) cuCtxDestroy(context_);
    }

    std::vector<float> infer(const std::vector<float>& features) {
        if (features.size() != 10) throw std::runtime_error("features size must be 10");
        float host_q[8] = {0};
        CUdeviceptr dev_features = 0;
        CUdeviceptr dev_q = 0;
        CHECK_CUDA(cuCtxSetCurrent(context_));
        CHECK_CUDA(cuMemAlloc(&dev_features, sizeof(float) * 10));
        CHECK_CUDA(cuMemAlloc(&dev_q, sizeof(float) * 8));
        CHECK_CUDA(cuMemcpyHtoD(dev_features, features.data(), sizeof(float) * 10));
        void* args[] = { &dev_features, &dev_q };
        CHECK_CUDA(cuLaunchKernel(kernel_, 1, 1, 1, 1, 1, 1, 0, 0, args, nullptr));
        CHECK_CUDA(cuCtxSynchronize());
        CHECK_CUDA(cuMemcpyDtoH(host_q, dev_q, sizeof(float) * 8));
        cuMemFree(dev_features);
        cuMemFree(dev_q);
        return std::vector<float>(host_q, host_q + 8);
    }


    std::vector<float> reward(const std::vector<float>& features) {
        if (features.size() != 8) throw std::runtime_error("reward features size must be 8");
        float host_reward[6] = {0};
        CUdeviceptr dev_features = 0;
        CUdeviceptr dev_reward = 0;
        CHECK_CUDA(cuCtxSetCurrent(context_));
        CHECK_CUDA(cuMemAlloc(&dev_features, sizeof(float) * 8));
        CHECK_CUDA(cuMemAlloc(&dev_reward, sizeof(float) * 6));
        CHECK_CUDA(cuMemcpyHtoD(dev_features, features.data(), sizeof(float) * 8));
        void* args[] = { &dev_features, &dev_reward };
        CHECK_CUDA(cuLaunchKernel(reward_kernel_, 1, 1, 1, 1, 1, 1, 0, 0, args, nullptr));
        CHECK_CUDA(cuCtxSynchronize());
        CHECK_CUDA(cuMemcpyDtoH(host_reward, dev_reward, sizeof(float) * 6));
        cuMemFree(dev_features);
        cuMemFree(dev_reward);
        return std::vector<float>(host_reward, host_reward + 6);
    }

    std::string device_name() const { return device_name_; }

private:
    CUdevice device_{};
    CUcontext context_{};
    CUmodule module_{};
    CUfunction kernel_{};
    CUfunction reward_kernel_{};
    char device_name_[256]{};
};

static std::string response_json(CudaDqnEngine& engine, const std::string& body) {
    std::vector<float> features(10);
    features[0] = static_cast<float>(json_number(body, "line_side_shortage_qty", 0.0));
    features[1] = json_bool(body, "line_side_material_available_flag", true) ? 1.0f : 0.0f;
    features[2] = static_cast<float>(json_number(body, "delay_risk_score", 0.0));
    features[3] = static_cast<float>(json_number(body, "quality_risk_score", 0.0));
    features[4] = static_cast<float>(json_number(body, "current_oee", 0.0));
    features[5] = json_bool(body, "abnormal_power_flag", false) ? 1.0f : 0.0f;
    features[6] = static_cast<float>(machine_status_code(json_string(body, "machine_status", "NORMAL")));
    features[7] = static_cast<float>(json_number(body, "customer_shortage_risk_score", json_number(body, "shortage_risk_score", 0.0)));
    features[8] = static_cast<float>(json_number(body, "due_date_remaining_hours", 999.0));
    features[9] = static_cast<float>(json_number(body, "avg_power_demand", json_number(body, "power_consumption_level", 0.0)));

    std::vector<float> q = engine.infer(features);
    int best = static_cast<int>(std::max_element(q.begin(), q.end()) - q.begin());
    float max_q = q[best];
    float raw_confidence = 0.55f + (max_q / 3.0f);
    float confidence = raw_confidence;
    if (confidence < 0.55f) confidence = 0.55f;
    if (confidence > 0.98f) confidence = 0.98f;

    std::ostringstream oss;
    oss << "{"
        << "\"engine\":\"CUDA_DRIVER_API_PTX_SERVICE\"," 
        << "\"device\":\"" << engine.device_name() << "\"," 
        << "\"action_index\":" << best << ","
        << "\"action_type\":\"" << ACTION_TYPES[best] << "\"," 
        << "\"action_name\":\"" << ACTION_NAMES[best] << "\"," 
        << "\"confidence\":" << confidence << ","
        << "\"reason\":\"" << ACTION_REASONS[best] << "\"," 
        << "\"q_values\":[";
    for (size_t i = 0; i < q.size(); ++i) {
        if (i) oss << ",";
        oss << q[i];
    }
    oss << "]}";
    return oss.str();
}

static std::string response_reward_json(CudaDqnEngine& engine, const std::string& body) {
    std::vector<float> features(8);
    features[0] = static_cast<float>(json_number(body, "actual_oee", 0.75));
    features[1] = static_cast<float>(json_number(body, "delay_hours", 0.0));
    features[2] = json_bool(body, "shortage_occurred_flag", false) ? 1.0f : 0.0f;
    features[3] = static_cast<float>(json_number(body, "actual_yield_rate", 0.95));
    features[4] = static_cast<float>(json_number(body, "energy_kwh", 1.0));
    features[5] = static_cast<float>(json_number(body, "planned_processing_time", 1.0));
    features[6] = json_bool(body, "machine_down_occurred_flag", false) ? 1.0f : 0.0f;
    features[7] = static_cast<float>(json_number(body, "expected_oee_improvement_rate", 0.0));

    std::vector<float> r = engine.reward(features);
    std::ostringstream oss;
    oss << "{"
        << "\"engine\":\"CUDA_DRIVER_API_PTX_REWARD_SERVICE\","
        << "\"device\":\"" << engine.device_name() << "\","
        << "\"reward_oee_score\":" << r[0] << ","
        << "\"reward_delivery_score\":" << r[1] << ","
        << "\"reward_shortage_score\":" << r[2] << ","
        << "\"reward_quality_score\":" << r[3] << ","
        << "\"reward_energy_score\":" << r[4] << ","
        << "\"total_reward_score\":" << r[5] << ","
        << "\"reason\":\"Reward components calculated by CUDA reward_score_kernel\""
        << "}";
    return oss.str();
}

static void send_http(SOCKET client, int code, const std::string& content_type, const std::string& body) {
    std::string status = code == 200 ? "OK" : (code == 404 ? "Not Found" : "Internal Server Error");
    std::ostringstream oss;
    oss << "HTTP/1.1 " << code << " " << status << "\r\n"
        << "Content-Type: " << content_type << "; charset=utf-8\r\n"
        << "Access-Control-Allow-Origin: *\r\n"
        << "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        << "Access-Control-Allow-Headers: Content-Type\r\n"
        << "Content-Length: " << body.size() << "\r\n"
        << "Connection: close\r\n\r\n"
        << body;

    std::string resp = oss.str();
    const char* data = resp.c_str();
    int remaining = static_cast<int>(resp.size());

    while (remaining > 0) {
        int sent = send(client, data, remaining, 0);
        if (sent == SOCKET_ERROR || sent == 0) {
            break;
        }
        data += sent;
        remaining -= sent;
    }

    // Force the HTTP response to be flushed before closesocket().
    shutdown(client, SD_SEND);
}

int main(int argc, char** argv) {
    int port = 9001;
    std::string ptx_path = "dqn_policy_kernel.ptx";
    if (argc >= 2) port = std::atoi(argv[1]);
    if (argc >= 3) ptx_path = argv[2];

    try {
        CudaDqnEngine engine(ptx_path);
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) throw std::runtime_error("WSAStartup failed");

        SOCKET server_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (server_fd == INVALID_SOCKET) throw std::runtime_error("socket failed");

        BOOL reuse = TRUE;
        setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuse), sizeof(reuse));

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = INADDR_ANY;
        addr.sin_port = htons(static_cast<u_short>(port));

        if (bind(server_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == SOCKET_ERROR) throw std::runtime_error("bind failed");
        if (listen(server_fd, SOMAXCONN) == SOCKET_ERROR) throw std::runtime_error("listen failed");

        std::cout << "CUDA DQN inference service started on http://127.0.0.1:" << port << std::endl;
        std::cout << "GPU Device: " << engine.device_name() << std::endl;
        std::cout << "PTX: " << ptx_path << std::endl;

        while (true) {
            SOCKET client = accept(server_fd, nullptr, nullptr);
            if (client == INVALID_SOCKET) continue;

            DWORD timeout_ms = 3000;
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));

            char buffer[16384];
            int received = recv(client, buffer, sizeof(buffer) - 1, 0);
            if (received <= 0) {
                closesocket(client);
                continue;
            }
            buffer[received] = 0;
            std::string request(buffer, received);

            size_t line_end = request.find("\r\n");
            std::string first_line = line_end == std::string::npos ? request : request.substr(0, line_end);
            size_t body_pos = request.find("\r\n\r\n");
            std::string body = body_pos == std::string::npos ? "" : request.substr(body_pos + 4);

            std::cout << "HTTP request: " << first_line << std::endl;

            try {
                if (first_line.find("OPTIONS ") == 0) {
                    send_http(client, 200, "application/json", "{}");
                } else if (first_line.find("GET /health") == 0) {
                    send_http(client, 200, "application/json", "{\"status\":\"UP\",\"engine\":\"CUDA_DRIVER_API_PTX_SERVICE\",\"dqn_endpoint\":\"/infer\",\"reward_endpoint\":\"/reward\"}");
                } else if (first_line.find("POST /infer") == 0) {
                    send_http(client, 200, "application/json", response_json(engine, body));
                } else if (first_line.find("POST /reward") == 0) {
                    send_http(client, 200, "application/json", response_reward_json(engine, body));
                } else {
                    send_http(client, 404, "application/json", "{\"error\":\"not found\"}");
                }
            } catch (const std::exception& ex) {
                std::string err = std::string("{\"error\":\"") + ex.what() + "\"}";
                send_http(client, 500, "application/json", err);
            }
            closesocket(client);
        }
    } catch (const std::exception& ex) {
        std::cerr << "Fatal: " << ex.what() << std::endl;
        return 1;
    }
    return 0;
}
