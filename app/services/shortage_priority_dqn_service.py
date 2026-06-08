from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.core.database import fetch_all, fetch_one, execute, execute_returning_id
from app.services.state_builder_service import build_states


ACTION_NAMES = {
    "KEEP_CURRENT_SCHEDULE": "維持目前排程",
    "REQUEST_MATERIAL_REPLENISHMENT": "優先補線邊庫",
    "INCREASE_ORDER_PRIORITY": "優先生產高缺貨風險品項",
    "REASSIGN_MACHINE": "改派可用 CNC",
    "PAUSE_LOW_PRIORITY_ORDER": "暫緩低優先級工單",
    "MAINTENANCE_CHECK": "安排換刀 / 保養",
    "OVERTIME_PRODUCTION": "啟動加班生產",
    "ADJUST_BATCH_SIZE": "調整批量",
}

ACTION_ORDER = list(ACTION_NAMES.keys())

WEIGHTS = {
    "customer_shortage_penalty": -1000.0,
    "delivery_delay_penalty": -500.0,
    "line_stock_stop_penalty": -300.0,
    "cnc_idle_penalty": -80.0,
    "excess_changeover_penalty": -50.0,
    "energy_high_penalty": -30.0,
    "on_time_delivery_reward": 500.0,
    "avoid_shortage_reward": 800.0,
    "oee_improvement_reward": 100.0,
    "downtime_reduction_reward": 150.0,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("1", "true", "t", "yes", "y")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ensure_shortage_priority_schema() -> None:
    """
    FIX79：
    缺貨優先 DQN 頁面不應每次呼叫都跑完整 ensure_extra_schema()。
    完整 schema 會 ALTER/建立大量 AIPS Demo 表，在 Windows + PostgreSQL 下容易超過前端 30 秒 timeout。
    這裡改成只建立本模組需要的表與欄位，讓 summary / run 能快速回應。
    """
    execute("""
        CREATE TABLE IF NOT EXISTS aips_shortage_priority_decision (
            decision_id BIGSERIAL PRIMARY KEY
        )
    """)
    columns = [
        ("decision_time", "TIMESTAMP DEFAULT NOW()"),
        ("state_id", "BIGINT"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("customer_shortage_risk_score", "NUMERIC(10,4)"),
        ("line_side_shortage_qty", "NUMERIC(14,4)"),
        ("available_stock_qty", "NUMERIC(14,4)"),
        ("demand_qty", "NUMERIC(14,4)"),
        ("shortage_qty", "NUMERIC(14,4)"),
        ("due_date_remaining_hours", "NUMERIC(12,4)"),
        ("avg_oee", "NUMERIC(10,4)"),
        ("avg_power_demand", "NUMERIC(12,4)"),
        ("quality_risk_score", "NUMERIC(10,4)"),
        ("base_q_json", "JSONB"),
        ("adjusted_q_json", "JSONB"),
        ("selected_action_type", "VARCHAR(80)"),
        ("selected_action_name", "VARCHAR(120)"),
        ("selected_q_value", "NUMERIC(14,4)"),
        ("shortage_priority_bonus", "NUMERIC(14,4)"),
        ("shortage_penalty", "NUMERIC(14,4)"),
        ("decision_reason", "TEXT"),
        ("model_version", "VARCHAR(80) DEFAULT 'SHORTAGE_PRIORITY_DQN_V1'"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ]
    for name, ddl in columns:
        execute(f"ALTER TABLE aips_shortage_priority_decision ADD COLUMN IF NOT EXISTS {name} {ddl}")

    execute("CREATE INDEX IF NOT EXISTS ix_shortage_priority_decision_time ON aips_shortage_priority_decision(decision_time)")
    execute("CREATE INDEX IF NOT EXISTS ix_shortage_priority_decision_risk ON aips_shortage_priority_decision(customer_shortage_risk_score)")

    execute("""
        CREATE TABLE IF NOT EXISTS aips_shortage_priority_experience (
            experience_id BIGSERIAL PRIMARY KEY
        )
    """)
    exp_columns = [
        ("state_id", "BIGINT"),
        ("decision_id", "BIGINT"),
        ("action_type", "VARCHAR(80)"),
        ("reward_value", "NUMERIC(14,4)"),
        ("next_state_id", "BIGINT"),
        ("experience_json", "JSONB"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ]
    for name, ddl in exp_columns:
        execute(f"ALTER TABLE aips_shortage_priority_experience ADD COLUMN IF NOT EXISTS {name} {ddl}")

    # 相容：若既有 action 表尚未建立，只建立最小表，後續 schema_guard / 既有模組會再補完整欄位。
    execute("""
        CREATE TABLE IF NOT EXISTS aips_dqn_action_log (
            action_id BIGSERIAL PRIMARY KEY
        )
    """)
    action_columns = [
        ("state_id", "BIGINT"),
        ("action_time", "TIMESTAMP DEFAULT NOW()"),
        ("action_type", "VARCHAR(80)"),
        ("action_name", "VARCHAR(120)"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("original_cnc_machine_id", "VARCHAR(80)"),
        ("suggested_cnc_machine_id", "VARCHAR(80)"),
        ("original_start_time", "TIMESTAMP"),
        ("suggested_start_time", "TIMESTAMP"),
        ("original_finish_time", "TIMESTAMP"),
        ("suggested_finish_time", "TIMESTAMP"),
        ("replenishment_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("maintenance_check_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("expected_delay_reduction_hours", "NUMERIC(12,4)"),
        ("expected_oee_improvement_rate", "NUMERIC(10,4)"),
        ("expected_shortage_risk_reduction", "NUMERIC(10,4)"),
        ("action_confidence_score", "NUMERIC(10,4)"),
        ("action_status", "VARCHAR(40) DEFAULT 'PENDING'"),
        ("action_reason", "TEXT"),
        ("shortage_priority_decision_id", "BIGINT"),
        ("customer_shortage_risk_score", "NUMERIC(10,4)"),
        ("shortage_priority_q_value", "NUMERIC(14,4)"),
        ("shortage_priority_reason", "TEXT"),
    ]
    for name, ddl in action_columns:
        execute(f"ALTER TABLE aips_dqn_action_log ADD COLUMN IF NOT EXISTS {name} {ddl}")


def _ensure_states_exist(limit: int = 12) -> int:
    """
    若缺貨優先頁面沒有 DQN State，先用既有 State Builder 建立少量 State。
    但只在 run 時做，不在 summary/load 時做，避免頁面開啟就卡住。
    """
    try:
        row = fetch_one("SELECT COUNT(*) AS cnt FROM aips_scheduling_state")
        count = int(row.get("cnt") or 0) if row else 0
        if count > 0:
            return count
    except Exception:
        count = 0

    try:
        states = build_states()
        return len(states or [])
    except Exception:
        return 0


def _latest_states(limit: int = 12) -> List[Dict[str, Any]]:
    return fetch_all(
        """
        SELECT *
        FROM aips_scheduling_state
        WHERE state_id IN (
            SELECT MAX(state_id)
            FROM aips_scheduling_state
            GROUP BY work_order_no
        )
        ORDER BY shortage_risk_score DESC, remaining_days_to_due ASC, delay_risk_score DESC, state_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def _bootstrap_decisions_if_empty(limit: int = 8) -> int:
    """
    若缺貨優先表目前沒有資料，則自動用最新 State 建立一批決策，
    避免前端頁面一打開就看到完全空白。
    """
    try:
        row = fetch_one("SELECT COUNT(*) AS cnt FROM aips_shortage_priority_decision") or {}
        current = int(row.get("cnt") or 0)
    except Exception:
        current = 0

    if current > 0:
        return current

    # 先確保至少有 state；若仍沒有資料就直接返回 0。
    _ensure_states_exist(limit)
    states = _latest_states(limit)
    if not states:
        return 0

    for state in states:
        decision = compute_decision_for_state(state)
        decision_id = _insert_decision(decision)
        _insert_action_from_decision(decision, decision_id)
        execute(
            """
            INSERT INTO aips_shortage_priority_experience (
                state_id, decision_id, action_type, reward_value, next_state_id, experience_json
            )
            VALUES (%s, %s, %s, %s, NULL, %s::jsonb)
            """,
            (
                decision.get("state_id"),
                decision_id,
                decision.get("selected_action_type"),
                decision.get("selected_q_value"),
                json.dumps({
                    "state_vector": decision.get("state_vector"),
                    "base_q": decision.get("base_q"),
                    "adjusted_q": decision.get("adjusted_q"),
                    "selected_action": decision.get("selected_action_type"),
                    "reward_design": WEIGHTS,
                    "auto_bootstrap": True,
                }, ensure_ascii=False),
            ),
        )
    return len(states)


def _stock_context(state: Dict[str, Any]) -> Dict[str, float]:
    product_no = state.get("product_no")
    cnc = state.get("cnc_machine_id")

    inventory = fetch_one(
        """
        SELECT
            COALESCE(SUM(available_qty), 0) AS available_qty,
            COALESCE(SUM(current_qty), 0) AS current_qty,
            COALESCE(SUM(reserved_qty), 0) AS reserved_qty,
            COALESCE(SUM(safety_stock_qty), 0) AS safety_stock_qty,
            COALESCE(SUM(shortage_qty), 0) AS shortage_qty,
            BOOL_OR(COALESCE(shortage_flag, FALSE)) AS shortage_flag
        FROM line_side_inventory_snapshot
        WHERE snapshot_id IN (
            SELECT MAX(snapshot_id)
            FROM line_side_inventory_snapshot
            WHERE (%s IS NULL OR material_no = %s OR cnc_machine_id = %s)
            GROUP BY material_no, cnc_machine_id
        )
        """,
        (product_no, product_no, cnc),
    ) or {}

    available = _num(inventory.get("available_qty"), 0)
    safety = _num(inventory.get("safety_stock_qty"), 0)
    stock_shortage = _num(inventory.get("shortage_qty"), 0)
    state_shortage = _num(state.get("line_side_shortage_qty"), 0)

    return {
        "available_stock_qty": available,
        "safety_stock_qty": safety,
        "stock_shortage_qty": max(stock_shortage, state_shortage),
        "line_side_shortage_flag": _bool(inventory.get("shortage_flag")) or state_shortage > 0,
    }


def _work_order_context(state: Dict[str, Any]) -> Dict[str, float]:
    wo = fetch_one(
        """
        SELECT *
        FROM work_order_progress_snapshot
        WHERE work_order_no = %s
        ORDER BY snapshot_id DESC
        LIMIT 1
        """,
        (state.get("work_order_no"),),
    ) or {}

    remaining_qty = _num(wo.get("remaining_qty") or state.get("remaining_order_qty"), 0)
    planned_qty = max(_num(wo.get("planned_qty"), remaining_qty if remaining_qty > 0 else 1), 1)
    demand_qty = max(planned_qty, remaining_qty)

    remaining_hours = _num(state.get("remaining_days_to_due"), 999) * 24
    if remaining_hours > 9000 and wo.get("due_date"):
        try:
            remaining_hours = (wo["due_date"] - datetime.now()).total_seconds() / 3600
        except Exception:
            pass

    return {
        "remaining_qty": remaining_qty,
        "planned_qty": planned_qty,
        "demand_qty": demand_qty,
        "due_date_remaining_hours": remaining_hours,
        "priority_level": _num(wo.get("priority_level"), _num(state.get("order_priority_score"), 0.5) * 10),
        "estimated_remaining_hours": _num(wo.get("estimated_remaining_hours"), _num(state.get("estimated_processing_time"), 1)),
    }


def build_shortage_priority_state(state: Dict[str, Any]) -> Dict[str, Any]:
    stock = _stock_context(state)
    wo = _work_order_context(state)

    available = stock["available_stock_qty"]
    demand = wo["demand_qty"]
    remaining_qty = wo["remaining_qty"]
    committed_or_unfinished = max(remaining_qty, 0)
    shortage_qty = max(0.0, demand - available - max(0.0, demand - committed_or_unfinished))
    shortage_qty = max(shortage_qty, stock["stock_shortage_qty"], _num(state.get("line_side_shortage_qty"), 0))

    due_hours = wo["due_date_remaining_hours"]
    due_pressure = _clamp(1.0 - (due_hours / 72.0)) if due_hours >= 0 else 1.0
    shortage_qty_score = _clamp(shortage_qty / max(demand, 1))
    priority_score = _clamp(wo["priority_level"] / 10.0)
    line_stock_risk = _clamp(_num(state.get("shortage_risk_score"), 0) + (0.25 if stock["line_side_shortage_flag"] else 0))

    customer_shortage_risk = _clamp(
        shortage_qty_score * 0.45 +
        due_pressure * 0.25 +
        priority_score * 0.20 +
        line_stock_risk * 0.10
    )

    avg_oee = _num(state.get("current_oee"), 0.70)
    avg_power = _num(state.get("power_consumption_level"), 0)
    quality = _num(state.get("quality_risk_score"), 0)
    machine_available = _bool(state.get("machine_available_flag"))

    return {
        "state_id": state.get("state_id"),
        "work_order_no": state.get("work_order_no"),
        "product_no": state.get("product_no"),
        "cnc_machine_id": state.get("cnc_machine_id"),
        "customer_shortage_risk_score": customer_shortage_risk,
        "line_side_shortage_qty": _num(state.get("line_side_shortage_qty"), 0),
        "available_stock_qty": available,
        "demand_qty": demand,
        "shortage_qty": shortage_qty,
        "due_date_remaining_hours": due_hours,
        "avg_oee": avg_oee,
        "avg_power_demand": avg_power,
        "quality_risk_score": quality,
        "delay_risk_score": _num(state.get("delay_risk_score"), 0),
        "line_stock_risk": line_stock_risk,
        "machine_available": machine_available,
        "state_vector": {
            "customer_shortage_risk": customer_shortage_risk,
            "due_pressure": due_pressure,
            "finished_stock_level": _clamp(available / max(demand, 1)),
            "line_stock_risk": line_stock_risk,
            "cnc_available": 1.0 if machine_available else 0.0,
            "avg_oee": avg_oee,
            "avg_power_demand": avg_power,
            "quality_risk": quality,
            "priority_score": priority_score,
            "estimated_remaining_hours": wo["estimated_remaining_hours"],
        },
    }


def _base_q(ctx: Dict[str, Any]) -> Dict[str, float]:
    shortage_risk = ctx["customer_shortage_risk_score"]
    line_risk = ctx["line_stock_risk"]
    delay_risk = ctx["delay_risk_score"]
    oee = ctx["avg_oee"]
    quality = ctx["quality_risk_score"]
    power = ctx["avg_power_demand"]

    return {
        "KEEP_CURRENT_SCHEDULE": 0.45 + (1 - shortage_risk) * 0.25 + oee * 0.20 - delay_risk * 0.10,
        "REQUEST_MATERIAL_REPLENISHMENT": 0.20 + line_risk * 1.20 + shortage_risk * 0.75,
        "INCREASE_ORDER_PRIORITY": 0.30 + shortage_risk * 0.85 + delay_risk * 0.65,
        "REASSIGN_MACHINE": 0.25 + (1 - oee) * 0.65 + delay_risk * 0.25,
        "PAUSE_LOW_PRIORITY_ORDER": 0.15 + (1 - shortage_risk) * 0.45 - delay_risk * 0.25,
        "MAINTENANCE_CHECK": 0.20 + quality * 0.70 + _clamp(power / 15.0) * 0.30,
        "OVERTIME_PRODUCTION": 0.25 + shortage_risk * 0.65 + delay_risk * 0.45,
        "ADJUST_BATCH_SIZE": 0.22 + shortage_risk * 0.35 + line_risk * 0.30,
    }


def _apply_shortage_priority_weights(ctx: Dict[str, Any], base_q: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, Any]]:
    shortage_risk = ctx["customer_shortage_risk_score"]
    line_shortage = ctx["line_side_shortage_qty"] > 0 or ctx["line_stock_risk"] >= 0.70
    delay_hours = ctx["due_date_remaining_hours"]
    delay_danger = delay_hours <= 24
    oee_low = ctx["avg_oee"] < 0.60
    quality_high = ctx["quality_risk_score"] >= 0.65

    adjusted = dict(base_q)
    bonus = 0.0
    penalty = 0.0

    # 文件核心：不缺貨 > 準時交貨 > 線邊庫不中斷 > OEE > 能耗
    if shortage_risk >= 0.70:
        adjusted["INCREASE_ORDER_PRIORITY"] += 8.0
        adjusted["OVERTIME_PRODUCTION"] += 6.0
        adjusted["ADJUST_BATCH_SIZE"] += 3.0
        adjusted["KEEP_CURRENT_SCHEDULE"] -= 10.0
        adjusted["PAUSE_LOW_PRIORITY_ORDER"] -= 12.0
        bonus += WEIGHTS["avoid_shortage_reward"]
        penalty += abs(WEIGHTS["customer_shortage_penalty"])

    if line_shortage:
        adjusted["REQUEST_MATERIAL_REPLENISHMENT"] += 9.0
        adjusted["KEEP_CURRENT_SCHEDULE"] -= 5.0
        adjusted["INCREASE_ORDER_PRIORITY"] += 2.0
        bonus += 300.0
        penalty += abs(WEIGHTS["line_stock_stop_penalty"])

    if delay_danger:
        adjusted["INCREASE_ORDER_PRIORITY"] += 5.0
        adjusted["OVERTIME_PRODUCTION"] += 4.0
        adjusted["PAUSE_LOW_PRIORITY_ORDER"] -= 5.0
        bonus += WEIGHTS["on_time_delivery_reward"]
        penalty += abs(WEIGHTS["delivery_delay_penalty"])

    if oee_low and shortage_risk < 0.70:
        adjusted["REASSIGN_MACHINE"] += 2.5
        adjusted["KEEP_CURRENT_SCHEDULE"] -= 1.0

    if quality_high:
        adjusted["MAINTENANCE_CHECK"] += 3.0
        if shortage_risk >= 0.70:
            adjusted["MAINTENANCE_CHECK"] -= 1.5

    best = max(adjusted.items(), key=lambda item: item[1])
    reason_parts = []
    if shortage_risk >= 0.70:
        reason_parts.append("客戶缺貨風險高，套用缺貨優先權重：提高優先生產 / 加班 / 調整批量分數，壓低維持原排程與暫緩工單。")
    if line_shortage:
        reason_parts.append("線邊庫缺料或低於安全庫存，優先補料以避免 CNC 待料停機。")
    if delay_danger:
        reason_parts.append("交期剩餘時間不足，優先提高製令單排序或啟動加班。")
    if not reason_parts:
        reason_parts.append("缺貨與交期風險可控，依 OEE、品質與設備狀態選擇最佳 Action。")

    meta = {
        "selected_action_type": best[0],
        "selected_action_name": ACTION_NAMES[best[0]],
        "selected_q_value": best[1],
        "shortage_priority_bonus": bonus,
        "shortage_penalty": penalty,
        "decision_reason": " ".join(reason_parts),
    }
    return adjusted, meta


def compute_decision_for_state(state: Dict[str, Any]) -> Dict[str, Any]:
    ctx = build_shortage_priority_state(state)
    base = _base_q(ctx)
    adjusted, meta = _apply_shortage_priority_weights(ctx, base)
    return {
        **ctx,
        "base_q": base,
        "adjusted_q": adjusted,
        **meta,
    }


def _insert_decision(decision: Dict[str, Any]) -> int:
    decision_id = execute_returning_id(
        """
        INSERT INTO aips_shortage_priority_decision (
            decision_time, state_id, work_order_no, product_no, cnc_machine_id,
            customer_shortage_risk_score, line_side_shortage_qty, available_stock_qty,
            demand_qty, shortage_qty, due_date_remaining_hours, avg_oee, avg_power_demand,
            quality_risk_score, base_q_json, adjusted_q_json,
            selected_action_type, selected_action_name, selected_q_value,
            shortage_priority_bonus, shortage_penalty, decision_reason, model_version
        )
        VALUES (
            NOW(), %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s::jsonb, %s::jsonb,
            %s, %s, %s,
            %s, %s, %s, 'SHORTAGE_PRIORITY_DQN_V1'
        )
        RETURNING decision_id
        """,
        (
            decision.get("state_id"), decision.get("work_order_no"), decision.get("product_no"), decision.get("cnc_machine_id"),
            decision.get("customer_shortage_risk_score"), decision.get("line_side_shortage_qty"), decision.get("available_stock_qty"),
            decision.get("demand_qty"), decision.get("shortage_qty"), decision.get("due_date_remaining_hours"), decision.get("avg_oee"),
            decision.get("avg_power_demand"), decision.get("quality_risk_score"),
            json.dumps(decision.get("base_q"), ensure_ascii=False),
            json.dumps(decision.get("adjusted_q"), ensure_ascii=False),
            decision.get("selected_action_type"), decision.get("selected_action_name"), decision.get("selected_q_value"),
            decision.get("shortage_priority_bonus"), decision.get("shortage_penalty"), decision.get("decision_reason"),
        ),
        "decision_id",
    )
    return int(decision_id)


def _insert_action_from_decision(decision: Dict[str, Any], decision_id: int) -> int:
    action_type = decision["selected_action_type"]
    action_name = decision["selected_action_name"]
    cnc = decision.get("cnc_machine_id")
    suggested = cnc
    if action_type == "REASSIGN_MACHINE":
        suggested = "CNC-02" if cnc != "CNC-02" else "CNC-03"

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
            action_status, action_reason,
            shortage_priority_decision_id, customer_shortage_risk_score,
            shortage_priority_q_value, shortage_priority_reason
        )
        VALUES (
            %s, NOW(), %s, %s,
            %s, %s,
            %s, %s,
            NOW(), NOW(),
            NOW() + INTERVAL '4 hours', NOW() + INTERVAL '3 hours',
            %s, %s,
            %s, %s,
            %s, %s,
            'PENDING', %s,
            %s, %s,
            %s, %s
        )
        RETURNING action_id
        """,
        (
            decision.get("state_id"), action_type, action_name,
            decision.get("work_order_no"), decision.get("product_no"),
            cnc, suggested,
            action_type == "REQUEST_MATERIAL_REPLENISHMENT",
            action_type == "MAINTENANCE_CHECK",
            4.0 if decision["customer_shortage_risk_score"] >= 0.70 else 1.5,
            0.03 if action_type in ("INCREASE_ORDER_PRIORITY", "OVERTIME_PRODUCTION") else 0.01,
            0.90 if action_type == "REQUEST_MATERIAL_REPLENISHMENT" else (0.70 if decision["customer_shortage_risk_score"] >= 0.70 else 0.20),
            min(1.0, max(0.55, 0.60 + decision["selected_q_value"] / 20.0)),
            decision["decision_reason"],
            decision_id,
            decision["customer_shortage_risk_score"],
            decision["selected_q_value"],
            decision["decision_reason"],
        ),
        "action_id",
    )
    return int(action_id)


def run_shortage_priority_dqn(limit: int = 12, write_action: bool = True) -> Dict[str, Any]:
    ensure_shortage_priority_schema()

    safe_limit = max(1, min(int(limit or 12), 12))
    state_count_before = _ensure_states_exist(safe_limit)
    states = _latest_states(safe_limit)
    decisions = []
    actions = []

    for state in states:
        decision = compute_decision_for_state(state)
        decision_id = _insert_decision(decision)
        decision["decision_id"] = decision_id
        action_id = None
        if write_action:
            action_id = _insert_action_from_decision(decision, decision_id)
            decision["action_id"] = action_id
            actions.append(action_id)

        execute(
            """
            INSERT INTO aips_shortage_priority_experience (
                state_id, decision_id, action_type, reward_value, next_state_id, experience_json
            )
            VALUES (%s, %s, %s, %s, NULL, %s::jsonb)
            """,
            (
                decision.get("state_id"),
                decision_id,
                decision.get("selected_action_type"),
                decision.get("selected_q_value"),
                json.dumps({
                    "state_vector": decision.get("state_vector"),
                    "base_q": decision.get("base_q"),
                    "adjusted_q": decision.get("adjusted_q"),
                    "selected_action": decision.get("selected_action_type"),
                    "reward_design": WEIGHTS,
                }, ensure_ascii=False),
            ),
        )

        decisions.append(decision)

    return {
        "success": True,
        "state_count_before": state_count_before,
        "used_state_count": len(states),
        "created_decisions": len(decisions),
        "created_actions": len(actions),
        "decisions": decisions,
        "weights": WEIGHTS,
        "message": f"缺貨優先 DQN 已完成：使用 {len(states)} 筆 State，新增 {len(decisions)} 筆決策，新增 {len(actions)} 筆 Action。",
    }


def shortage_priority_overlay_for_state(state: Dict[str, Any], inference: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    給既有 DQN 模組使用：將缺貨優先權重套疊到原本 GPU / Python 推論結果上。
    不在這裡寫 decision table，避免每筆既有 DQN action 重複寫太多 decision；
    要完整落地可呼叫 run_shortage_priority_dqn。
    """
    ensure_shortage_priority_schema()
    decision = compute_decision_for_state(state)

    if inference:
        original_action = inference.get("action_type")
        decision["decision_reason"] = (
            f"原始 DQN Action={original_action}；"
            f"套用缺貨優先權重後 Action={decision['selected_action_type']}。"
            f"{decision['decision_reason']}"
        )

    return {
        "engine": "SHORTAGE_PRIORITY_DQN_OVERLAY",
        "action_type": decision["selected_action_type"],
        "action_name": decision["selected_action_name"],
        "confidence": min(1.0, max(0.60, 0.60 + decision["selected_q_value"] / 20.0)),
        "delay_reduction": 4.0 if decision["customer_shortage_risk_score"] >= 0.70 else 1.5,
        "oee_improve": 0.03 if decision["selected_action_type"] in ("INCREASE_ORDER_PRIORITY", "OVERTIME_PRODUCTION") else 0.01,
        "shortage_reduce": 0.90 if decision["selected_action_type"] == "REQUEST_MATERIAL_REPLENISHMENT" else (0.70 if decision["customer_shortage_risk_score"] >= 0.70 else 0.20),
        "replenishment": decision["selected_action_type"] == "REQUEST_MATERIAL_REPLENISHMENT",
        "maintenance": decision["selected_action_type"] == "MAINTENANCE_CHECK",
        "reason": decision["decision_reason"],
        "q_values": decision["adjusted_q"],
        "shortage_priority_decision": decision,
    }


def latest_decisions(limit: int = 100) -> List[Dict[str, Any]]:
    ensure_shortage_priority_schema()
    _bootstrap_decisions_if_empty(min(max(int(limit or 8), 1), 12))
    return fetch_all(
        """
        SELECT *
        FROM aips_shortage_priority_decision
        ORDER BY decision_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def summary() -> Dict[str, Any]:
    ensure_shortage_priority_schema()
    _bootstrap_decisions_if_empty(8)
    row = fetch_one(
        """
        SELECT
            COUNT(*) AS total_count,
            COALESCE(AVG(customer_shortage_risk_score), 0) AS avg_shortage_risk,
            COALESCE(MAX(customer_shortage_risk_score), 0) AS max_shortage_risk,
            COALESCE(SUM(CASE WHEN customer_shortage_risk_score >= 0.7 THEN 1 ELSE 0 END), 0) AS high_risk_count
        FROM aips_shortage_priority_decision
        """
    ) or {}
    latest = fetch_one(
        """
        SELECT selected_action_type, selected_action_name, decision_reason, decision_time
        FROM aips_shortage_priority_decision
        ORDER BY decision_id DESC
        LIMIT 1
        """
    )
    return {
        "total_count": int(row.get("total_count") or 0),
        "avg_shortage_risk": float(row.get("avg_shortage_risk") or 0),
        "max_shortage_risk": float(row.get("max_shortage_risk") or 0),
        "high_risk_count": int(row.get("high_risk_count") or 0),
        "latest": latest,
        "weights": WEIGHTS,
        "priority_order": "不缺貨 > 準時交貨 > 線邊庫不中斷 > OEE提升 > 降低能耗",
    }


def explain() -> Dict[str, Any]:
    return {
        "module_name": "DQN缺貨優先智慧排程計算模組",
        "positioning": [
            "第一優先：避免客戶缺貨與交期延遲",
            "第二優先：避免線邊庫缺料造成 CNC 停機",
            "第三優先：提升 OEE、降低換線、降低能耗",
        ],
        "state_features": [
            "客戶需求缺貨風險", "訂單交期剩餘時間", "成品 / 半成品 / 原料庫存",
            "線邊庫即時庫存", "CNC 機台狀態", "機台負載", "加工剩餘時間",
            "智慧電表需量與 THD", "品質風險", "人工作業掃描紀錄",
        ],
        "actions": [{"action_type": k, "action_name": v} for k, v in ACTION_NAMES.items()],
        "weights": WEIGHTS,
        "formula": "Q_adjusted = Q_base + 避免缺貨加分 + 準時交貨加分 + OEE加分 - 客戶缺貨懲罰 - 交期延遲懲罰 - 線邊庫缺料停機懲罰 - 能耗懲罰",
    }
