from app.core.database import fetch_all, execute_returning_id
from app.services.gpu_inference_client import GpuInferenceUnavailable, call_gpu_dqn_service

ACTION_NAMES = {
    "KEEP_CURRENT_SCHEDULE": "維持目前排程",
    "REQUEST_MATERIAL_REPLENISHMENT": "提前補料",
    "INCREASE_ORDER_PRIORITY": "提高製令單優先順序",
    "REASSIGN_MACHINE": "更換 CNC 機台",
    "PAUSE_WORK_ORDER": "暫停製令單",
    "INSERT_URGENT_WORK_ORDER": "緊急插單",
    "MAINTENANCE_CHECK": "安排預防保養",
}

def _python_rule_inference(state):
    shortage_qty = float(state["line_side_shortage_qty"] or 0)
    material_available = bool(state["line_side_material_available_flag"])
    delay_risk = float(state["delay_risk_score"] or 0)
    quality_risk = float(state["quality_risk_score"] or 0)
    oee = float(state["current_oee"] or 0)
    abnormal_power = bool(state["abnormal_power_flag"])
    machine_status = state["machine_status"]

    action_type = "KEEP_CURRENT_SCHEDULE"
    confidence = 0.70
    delay_reduction = 0.2
    oee_improve = 0.01
    shortage_reduce = 0.10
    replenishment = False
    maintenance = False
    reason = "目前缺料、延遲與設備風險不高，建議維持原排程。"

    if (not material_available) or shortage_qty > 0:
        action_type = "REQUEST_MATERIAL_REPLENISHMENT"
        confidence = 0.90
        delay_reduction = min(4.0, shortage_qty / 5.0 + 0.5)
        oee_improve = 0.05
        shortage_reduce = 0.85
        replenishment = True
        reason = "線邊庫可用量低於安全庫存，建議提前補料，避免 CNC 待料停機。"
    elif delay_risk >= 0.70 and oee >= 0.65:
        action_type = "INCREASE_ORDER_PRIORITY"
        confidence = 0.86
        delay_reduction = 3.0
        oee_improve = 0.04
        shortage_reduce = 0.20
        reason = "交期延遲風險偏高且設備狀態可加工，建議提高製令單優先順序。"
    elif machine_status in ("STOPPED", "ABNORMAL") or abnormal_power or quality_risk >= 0.65:
        action_type = "MAINTENANCE_CHECK"
        confidence = 0.82
        delay_reduction = 1.5
        oee_improve = 0.06
        shortage_reduce = 0.10
        maintenance = True
        reason = "設備或電力特徵異常，建議安排預防保養或機台檢查。"
    elif oee < 0.60:
        action_type = "REASSIGN_MACHINE"
        confidence = 0.78
        delay_reduction = 2.5
        oee_improve = 0.08
        shortage_reduce = 0.25
        reason = "目前 OEE 偏低，建議評估更換 CNC 機台或調整加工順序。"

    return {
        "engine": "PYTHON_RULE_FALLBACK",
        "action_type": action_type,
        "action_name": ACTION_NAMES[action_type],
        "confidence": confidence,
        "delay_reduction": delay_reduction,
        "oee_improve": oee_improve,
        "shortage_reduce": shortage_reduce,
        "replenishment": replenishment,
        "maintenance": maintenance,
        "reason": reason,
    }


def _normalize_gpu_inference(state, gpu_result):
    action_type = gpu_result.get("action_type") or "KEEP_CURRENT_SCHEDULE"
    if action_type not in ACTION_NAMES:
        action_type = "KEEP_CURRENT_SCHEDULE"

    shortage_qty = float(state["line_side_shortage_qty"] or 0)

    return {
        "engine": gpu_result.get("engine") or "CUDA_DRIVER_API_SERVICE",
        "device": gpu_result.get("device"),
        "q_values": gpu_result.get("q_values"),
        "action_type": action_type,
        "action_name": gpu_result.get("action_name") or ACTION_NAMES[action_type],
        "confidence": float(gpu_result.get("confidence") or 0.80),
        "delay_reduction": 3.0 if action_type in ("INCREASE_ORDER_PRIORITY", "INSERT_URGENT_WORK_ORDER") else (min(4.0, shortage_qty / 5.0 + 0.5) if action_type == "REQUEST_MATERIAL_REPLENISHMENT" else 1.5),
        "oee_improve": 0.08 if action_type == "REASSIGN_MACHINE" else (0.06 if action_type == "MAINTENANCE_CHECK" else 0.04),
        "shortage_reduce": 0.85 if action_type == "REQUEST_MATERIAL_REPLENISHMENT" else 0.20,
        "replenishment": action_type == "REQUEST_MATERIAL_REPLENISHMENT",
        "maintenance": action_type == "MAINTENANCE_CHECK",
        "reason": gpu_result.get("reason") or "由 CUDA Driver API 獨立推論服務產生排程建議。",
    }


def generate_actions():
    states = fetch_all(
        """
        SELECT *
        FROM aips_scheduling_state
        WHERE state_id IN (
            SELECT MAX(state_id)
            FROM aips_scheduling_state
            GROUP BY work_order_no
        )
        ORDER BY delay_risk_score DESC, line_side_shortage_qty DESC
        """
    )

    actions = []
    for state in states:
        try:
            gpu_result = call_gpu_dqn_service(state)
            inference = _normalize_gpu_inference(state, gpu_result) if gpu_result else _python_rule_inference(state)
        except GpuInferenceUnavailable as exc:
            inference = _python_rule_inference(state)
            inference["reason"] = f"GPU 推論服務未啟動或連線失敗，已降級 Python 規則。原始原因：{exc}；{inference['reason']}"

        action_type = inference["action_type"]
        action_id = execute_returning_id(
            """
            INSERT INTO aips_dqn_action_log (
                state_id, action_time, action_type, action_name,
                work_order_no, product_no,
                original_cnc_machine_id, suggested_cnc_machine_id,
                original_start_time, suggested_start_time,
                original_finish_time, suggested_finish_time,
                replenishment_required_flag, maintenance_check_required_flag,
                expected_delay_reduction_hours, expected_oee_improvement_rate,
                expected_shortage_risk_reduction, action_confidence_score,
                action_status, action_reason
            )
            VALUES (
                %s, NOW(), %s, %s,
                %s, %s,
                %s, %s,
                NOW(), NOW(),
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                'PENDING', %s
            )
            RETURNING action_id
            """,
            (
                state["state_id"], action_type, inference["action_name"],
                state["work_order_no"], state["product_no"],
                state["cnc_machine_id"], state["cnc_machine_id"],
                state["estimated_finish_time"], state["estimated_finish_time"],
                inference["replenishment"], inference["maintenance"],
                inference["delay_reduction"], inference["oee_improve"],
                inference["shortage_reduce"], inference["confidence"],
                inference["reason"],
            ),
            "action_id",
        )
        actions.append({
            "action_id": action_id,
            "action_type": action_type,
            "reason": inference["reason"],
            "engine": inference.get("engine"),
            "device": inference.get("device"),
            "q_values": inference.get("q_values"),
        })

    return actions
