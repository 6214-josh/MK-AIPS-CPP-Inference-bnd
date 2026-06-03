# CUDA Driver API DQN 推論服務

此資料夾是獨立 C++ CUDA Driver API 推論服務範例，給 FastAPI 後端呼叫。

## 架構

React 前端 → FastAPI `/api/aips/dqn/generate-actions` → `gpu_inference_client.py` → C++ 服務 `POST http://127.0.0.1:9001/infer` → CUDA Driver API 載入 `dqn_policy_kernel.ptx` → GPU 計算 Q values。

## 編譯

在 Windows 直接執行：

```bat
build_cuda_dqn_service.bat
```

或手動：

```bat
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd /d C:\你的專案\tools\cuda_inference_service
nvcc -ptx dqn_policy_kernel.cu -o dqn_policy_kernel.ptx
nvcc cuda_dqn_inference_service.cpp -o cuda_dqn_inference_service.exe -I"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\include" -L"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\lib\x64" -lcuda -lws2_32
```

## 啟動

```bat
run_cuda_dqn_service.bat
```

預設服務：

```text
http://127.0.0.1:9001
```

健康檢查：

```bat
curl http://127.0.0.1:9001/health
```

推論測試：

```bat
curl -X POST http://127.0.0.1:9001/infer -H "Content-Type: application/json" -d "{\"line_side_shortage_qty\":5,\"line_side_material_available_flag\":false,\"delay_risk_score\":0.8,\"quality_risk_score\":0.2,\"current_oee\":0.75,\"abnormal_power_flag\":false,\"machine_status\":\"NORMAL\"}"
```

## 後端環境變數

FastAPI 可用以下環境變數控制：

```text
AIPS_GPU_INFERENCE_ENABLED=true
AIPS_GPU_INFERENCE_URL=http://127.0.0.1:9001/infer
AIPS_GPU_INFERENCE_TIMEOUT=2
```

如果 C++ 服務未啟動，後端會自動降級使用原本 Python 規則邏輯，不會讓前端整個壞掉。
