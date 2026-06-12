import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

GPU_INFERENCE_ENABLED = os.getenv("AIPS_GPU_INFERENCE_ENABLED", "true").lower() in ("1", "true", "yes", "y")
GPU_INFERENCE_URL = os.getenv("AIPS_GPU_INFERENCE_URL", "http://127.0.0.1:9001/infer")
GPU_REWARD_URL = os.getenv("AIPS_GPU_REWARD_URL", "http://127.0.0.1:9001/reward")
GPU_HEALTH_URL = os.getenv("AIPS_GPU_HEALTH_URL", "http://127.0.0.1:9001/health")
GPU_INFERENCE_TIMEOUT = float(os.getenv("AIPS_GPU_INFERENCE_TIMEOUT", "2"))


class GpuInferenceUnavailable(RuntimeError):
    pass


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(default if value is None else value)
    except Exception:
        return float(default)


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def call_gpu_dqn_service(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    呼叫獨立 C++ CUDA Driver API DQN 推論服務。

    /infer 用於 DQN action / q_values。
    若服務未啟動或發生錯誤，丟出 GpuInferenceUnavailable，讓上層降級使用 Python 規則。
    """
    if not GPU_INFERENCE_ENABLED:
        return None

    payload = {
        "state_id": state.get("state_id"),
        "work_order_no": state.get("work_order_no"),
        "product_no": state.get("product_no"),
        "cnc_machine_id": state.get("cnc_machine_id"),
        "line_side_shortage_qty": _safe_float(state.get("line_side_shortage_qty"), 0),
        "line_side_material_available_flag": bool(state.get("line_side_material_available_flag")),
        "delay_risk_score": _safe_float(state.get("delay_risk_score"), 0),
        "quality_risk_score": _safe_float(state.get("quality_risk_score"), 0),
        "current_oee": _safe_float(state.get("current_oee"), 0),
        "abnormal_power_flag": bool(state.get("abnormal_power_flag")),
        "machine_status": state.get("machine_status") or "NORMAL",
        "customer_shortage_risk_score": _safe_float(state.get("customer_shortage_risk_score") or state.get("shortage_risk_score"), 0),
        "due_date_remaining_hours": _safe_float(state.get("remaining_days_to_due"), 999) * 24,
        "avg_power_demand": _safe_float(state.get("power_consumption_level"), 0),
    }

    try:
        return _post_json(GPU_INFERENCE_URL, payload, GPU_INFERENCE_TIMEOUT)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise GpuInferenceUnavailable(str(exc)) from exc


def call_gpu_reward_service(reward_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    FIX117：
    呼叫同一個 C++ CUDA Driver API 服務的 /reward endpoint。

    /reward 用於 Reward components / total_reward_score：
    - reward_oee_score
    - reward_delivery_score
    - reward_shortage_score
    - reward_quality_score
    - reward_energy_score
    - total_reward_score

    若 CUDA service 沒啟動，上層會降級 Python Reward。
    """
    if not GPU_INFERENCE_ENABLED:
        return None

    payload = {
        "action_id": reward_payload.get("action_id"),
        "state_id": reward_payload.get("state_id"),
        "work_order_no": reward_payload.get("work_order_no"),
        "cnc_machine_id": reward_payload.get("cnc_machine_id"),
        "planned_processing_time": _safe_float(reward_payload.get("planned_processing_time"), 1),
        "actual_processing_time": _safe_float(reward_payload.get("actual_processing_time"), 1),
        "delay_hours": _safe_float(reward_payload.get("delay_hours"), 0),
        "shortage_occurred_flag": bool(reward_payload.get("shortage_occurred_flag")),
        "machine_down_occurred_flag": bool(reward_payload.get("machine_down_occurred_flag")),
        "ng_qty": _safe_float(reward_payload.get("ng_qty"), 0),
        "good_qty": _safe_float(reward_payload.get("good_qty"), 1),
        "actual_yield_rate": _safe_float(reward_payload.get("actual_yield_rate"), 0.95),
        "actual_oee": _safe_float(reward_payload.get("actual_oee"), 0.75),
        "energy_kwh": _safe_float(reward_payload.get("energy_kwh"), 1),
        "expected_oee_improvement_rate": _safe_float(reward_payload.get("expected_oee_improvement_rate"), 0),
        "expected_delay_reduction_hours": _safe_float(reward_payload.get("expected_delay_reduction_hours"), 0),
        "expected_shortage_risk_reduction": _safe_float(reward_payload.get("expected_shortage_risk_reduction"), 0),
    }

    try:
        return _post_json(GPU_REWARD_URL, payload, GPU_INFERENCE_TIMEOUT)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise GpuInferenceUnavailable(str(exc)) from exc


def check_gpu_inference_health() -> Dict[str, Any]:
    if not GPU_INFERENCE_ENABLED:
        return {"enabled": False, "status": "DISABLED"}

    request = urllib.request.Request(GPU_HEALTH_URL, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=GPU_INFERENCE_TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            data["enabled"] = True
            data["url"] = GPU_INFERENCE_URL
            data["reward_url"] = GPU_REWARD_URL
            return data
    except Exception as exc:
        return {
            "enabled": True,
            "status": "DOWN",
            "url": GPU_INFERENCE_URL,
            "reward_url": GPU_REWARD_URL,
            "error": str(exc),
        }
