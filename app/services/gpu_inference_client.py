import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

GPU_INFERENCE_ENABLED = os.getenv("AIPS_GPU_INFERENCE_ENABLED", "true").lower() in ("1", "true", "yes", "y")
GPU_INFERENCE_URL = os.getenv("AIPS_GPU_INFERENCE_URL", "http://127.0.0.1:9001/infer")
GPU_HEALTH_URL = os.getenv("AIPS_GPU_HEALTH_URL", "http://127.0.0.1:9001/health")
GPU_INFERENCE_TIMEOUT = float(os.getenv("AIPS_GPU_INFERENCE_TIMEOUT", "2"))


class GpuInferenceUnavailable(RuntimeError):
    pass


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
    呼叫獨立 C++ CUDA Driver API 推論服務。

    回傳格式範例：
    {
      "engine": "CUDA_DRIVER_API_PTX_SERVICE",
      "action_type": "REQUEST_MATERIAL_REPLENISHMENT",
      "action_name": "提前補料",
      "confidence": 0.9,
      "reason": "...",
      "q_values": [...]
    }

    若服務未啟動或發生錯誤，丟出 GpuInferenceUnavailable，讓上層降級使用 Python 規則。
    """
    if not GPU_INFERENCE_ENABLED:
        return None

    payload = {
        "state_id": state.get("state_id"),
        "work_order_no": state.get("work_order_no"),
        "product_no": state.get("product_no"),
        "cnc_machine_id": state.get("cnc_machine_id"),
        "line_side_shortage_qty": float(state.get("line_side_shortage_qty") or 0),
        "line_side_material_available_flag": bool(state.get("line_side_material_available_flag")),
        "delay_risk_score": float(state.get("delay_risk_score") or 0),
        "quality_risk_score": float(state.get("quality_risk_score") or 0),
        "current_oee": float(state.get("current_oee") or 0),
        "abnormal_power_flag": bool(state.get("abnormal_power_flag")),
        "machine_status": state.get("machine_status") or "NORMAL",
    }

    try:
        return _post_json(GPU_INFERENCE_URL, payload, GPU_INFERENCE_TIMEOUT)
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
            return data
    except Exception as exc:
        return {
            "enabled": True,
            "status": "DOWN",
            "url": GPU_INFERENCE_URL,
            "error": str(exc),
        }
