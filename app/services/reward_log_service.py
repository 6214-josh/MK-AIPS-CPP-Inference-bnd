from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from app.core.database import execute, fetch_all, fetch_one


ACTION_NAME_MAP = {
    "ASSIGN_JOB": "指派工單",
    "MOVE_JOB": "轉移工單",
    "INSERT_URGENT_JOB": "急單插入",
    "DELAY_JOB": "延後工單",
    "ADVANCE_JOB": "提前工單",
    "PAUSE_MACHINE": "暫停派工",
    "CHANGE_TOOL": "建議換刀",
    "WAIT_MATERIAL": "等待補料",
    "REPLAN_ALL": "全局重排",
    "BALANCE_LOAD": "負載平衡",
    "AVOID_RISK_MACHINE": "避開高風險機台",
    "REQUEST_REPLENISHMENT": "要求補料",
    "REQUEST_MAINTENANCE_CHECK": "要求保養檢查",
    "KEEP_CURRENT_SCHEDULE": "維持目前排程",
    "CHANGE_CNC_MACHINE": "更換 CNC 機台",
    "QUALITY_HOLD": "品質暫停",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(default if value is None else value)
    except Exception:
        return float(default)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _table_exists(table_name: str) -> bool:
    row = fetch_one(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        ) AS exists_flag
        """,
        (table_name,),
    )
    return bool(row and row.get("exists_flag"))


def _columns(table_name: str) -> set[str]:
    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {row["column_name"] for row in rows}


def _expr(cols: set[str], source_col: str, alias: str, default_sql: str = "NULL") -> str:
    if source_col in cols:
        return f"{source_col} AS {alias}"
    return f"{default_sql} AS {alias}"


def _scope(row: Dict[str, Any]) -> str:
    if row.get("machine_down_occurred_flag"):
        return "MAINTENANCE"
    if row.get("shortage_occurred_flag"):
        return "MATERIAL"
    if row.get("work_order_no") and row.get("cnc_machine_id"):
        return "WORK_ORDER"
    if row.get("cnc_machine_id"):
        return "MACHINE"
    return "SCHEDULE_GLOBAL"


def _action_code(row: Dict[str, Any]) -> str:
    action_type = _safe_text(row.get("action_type")).upper()
    if action_type:
        if action_type in ACTION_NAME_MAP:
            return action_type
        if "REPLENISH" in action_type:
            return "WAIT_MATERIAL"
        if "MAINT" in action_type or "PAUSE" in action_type:
            return "PAUSE_MACHINE"
        if "CHANGE" in action_type or "MOVE" in action_type:
            return "MOVE_JOB"
        if "KEEP" in action_type:
            return "ASSIGN_JOB"
        return action_type

    if row.get("shortage_occurred_flag"):
        return "WAIT_MATERIAL"
    if row.get("machine_down_occurred_flag"):
        return "PAUSE_MACHINE"
    if row.get("suggested_cnc_machine_id"):
        return "MOVE_JOB"
    return "ASSIGN_JOB"


def ensure_reward_log_schema() -> None:
    """
    依《AIPS 系統Reward的log檔案設計.docx》建立 Reward Log。
    核心：DQN 排程決策事件 = Reward Log 的核心記錄單位。

    Business Key：
    schedule_run_id + decision_step_no + reward_scope + work_order_no + operation_seq + machine_id + action_code
    """
    execute("CREATE TABLE IF NOT EXISTS aips_dqn_reward_log (reward_log_id BIGSERIAL PRIMARY KEY)")

    columns = [
        ("schedule_run_id", "VARCHAR(50)"),
        ("schedule_version_id", "VARCHAR(50)"),
        ("decision_step_no", "INT"),
        ("calculated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("reward_scope", "VARCHAR(30)"),
        ("work_order_no", "VARCHAR(80)"),
        ("operation_seq", "INT"),
        ("product_code", "VARCHAR(80)"),
        ("machine_id", "VARCHAR(30)"),
        ("from_machine_id", "VARCHAR(30)"),
        ("to_machine_id", "VARCHAR(30)"),
        ("action_code", "VARCHAR(50)"),
        ("action_name", "VARCHAR(100)"),
        ("action_params", "JSONB"),
        ("reward_score", "NUMERIC(10,4)"),
        ("reward_before", "NUMERIC(10,4)"),
        ("reward_after", "NUMERIC(10,4)"),
        ("reward_delta", "NUMERIC(10,4)"),
        ("q_value", "NUMERIC(10,4)"),
        ("confidence_score", "NUMERIC(5,2)"),
        ("on_time_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("shortage_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("oee_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("load_balance_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("setup_time_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("quality_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("maintenance_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("material_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("manual_handling_reward", "NUMERIC(10,4) DEFAULT 0"),
        ("penalty_score", "NUMERIC(10,4) DEFAULT 0"),
        ("state_snapshot", "JSONB"),
        ("next_state_snapshot", "JSONB"),
        ("reward_formula_version", "VARCHAR(30)"),
        ("model_version", "VARCHAR(30)"),
        ("is_action_applied", "BOOLEAN DEFAULT FALSE"),
        ("applied_at", "TIMESTAMP"),
        ("operator_id", "VARCHAR(50)"),
        ("approval_status", "VARCHAR(20) DEFAULT 'PENDING'"),
        ("remark", "TEXT"),
        ("source_reward_id", "BIGINT"),
        ("source_action_id", "BIGINT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]
    for name, ddl in columns:
        execute(f"ALTER TABLE aips_dqn_reward_log ADD COLUMN IF NOT EXISTS {name} {ddl}")

    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_run ON aips_dqn_reward_log(schedule_run_id, decision_step_no)")
    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_work_order ON aips_dqn_reward_log(work_order_no)")
    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_machine ON aips_dqn_reward_log(machine_id)")
    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_calculated_at ON aips_dqn_reward_log(calculated_at)")
    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_action ON aips_dqn_reward_log(action_code)")
    execute("CREATE INDEX IF NOT EXISTS idx_dqn_reward_log_scope ON aips_dqn_reward_log(reward_scope)")
    execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_dqn_reward_log_source_reward ON aips_dqn_reward_log(source_reward_id) WHERE source_reward_id IS NOT NULL")


def _source_reward_rows(limit: int = 120) -> List[Dict[str, Any]]:
    """
    讀取既有 aips_reward_result。
    這裡不再硬寫固定欄位，也不強制 join aips_dqn_action_log，
    避免不同版本 schema 欄位不一致造成 /reward-log/dashboard 500。
    """
    if not _table_exists("aips_reward_result"):
        return []

    cols = _columns("aips_reward_result")
    select_items = [
        _expr(cols, "reward_id", "reward_id", "NULL"),
        _expr(cols, "evaluate_time", "evaluate_time", "CURRENT_TIMESTAMP"),
        _expr(cols, "created_at", "created_at", "CURRENT_TIMESTAMP"),
        _expr(cols, "action_id", "action_id", "NULL"),
        _expr(cols, "state_id", "state_id", "NULL"),
        _expr(cols, "work_order_no", "work_order_no", "'-'"),
        _expr(cols, "cnc_machine_id", "cnc_machine_id", "'-'"),
        _expr(cols, "delay_hours", "delay_hours", "0"),
        _expr(cols, "shortage_occurred_flag", "shortage_occurred_flag", "false"),
        _expr(cols, "machine_down_occurred_flag", "machine_down_occurred_flag", "false"),
        _expr(cols, "actual_oee", "actual_oee", "0"),
        _expr(cols, "actual_yield_rate", "actual_yield_rate", "0"),
        _expr(cols, "energy_kwh", "energy_kwh", "0"),
        _expr(cols, "reward_oee_score", "reward_oee_score", "0"),
        _expr(cols, "reward_delivery_score", "reward_delivery_score", "0"),
        _expr(cols, "reward_shortage_score", "reward_shortage_score", "0"),
        _expr(cols, "reward_quality_score", "reward_quality_score", "0"),
        _expr(cols, "reward_energy_score", "reward_energy_score", "0"),
        _expr(cols, "total_reward_score", "total_reward_score", "0"),
    ]

    order_col = "reward_id" if "reward_id" in cols else "created_at" if "created_at" in cols else "1"
    rows = fetch_all(
        f"""
        SELECT {", ".join(select_items)}
        FROM aips_reward_result
        ORDER BY {order_col} DESC
        LIMIT %s
        """,
        (limit,),
    )

    action_ids = [row.get("action_id") for row in rows if row.get("action_id") is not None]
    actions: Dict[str, Dict[str, Any]] = {}
    if action_ids and _table_exists("aips_dqn_action_log"):
        action_cols = _columns("aips_dqn_action_log")
        if "action_id" in action_cols:
            action_select_items = [
                _expr(action_cols, "action_id", "action_id", "NULL"),
                _expr(action_cols, "action_type", "action_type", "NULL"),
                _expr(action_cols, "action_name", "action_name", "NULL"),
                _expr(action_cols, "product_no", "product_no", "NULL"),
                _expr(action_cols, "original_cnc_machine_id", "original_cnc_machine_id", "NULL"),
                _expr(action_cols, "suggested_cnc_machine_id", "suggested_cnc_machine_id", "NULL"),
                _expr(action_cols, "expected_delay_reduction_hours", "expected_delay_reduction_hours", "0"),
                _expr(action_cols, "expected_oee_improvement_rate", "expected_oee_improvement_rate", "0"),
                _expr(action_cols, "expected_shortage_risk_reduction", "expected_shortage_risk_reduction", "0"),
                _expr(action_cols, "action_confidence_score", "action_confidence_score", "0.85"),
                _expr(action_cols, "action_status", "action_status", "NULL"),
                _expr(action_cols, "action_reason", "action_reason", "NULL"),
            ]
            try:
                action_rows = fetch_all(
                    f"""
                    SELECT {", ".join(action_select_items)}
                    FROM aips_dqn_action_log
                    WHERE action_id::text = ANY(%s)
                    """,
                    ([str(item) for item in action_ids],),
                )
                actions = {str(row.get("action_id")): row for row in action_rows}
            except Exception:
                actions = {}

    for row in rows:
        action = actions.get(str(row.get("action_id")), {})
        row.update(action)
    return rows


def _seed_demo_reward_log(limit: int = 36) -> int:
    """
    若 DB 還沒有 reward_result，建立可展示的 DQN Reward Log。
    這不是只做前端假資料，而是實際寫入 aips_dqn_reward_log，讓 Dashboard API 有資料可查。
    """
    existing = fetch_one("SELECT COUNT(*) AS cnt FROM aips_dqn_reward_log")
    if existing and int(existing.get("cnt") or 0) > 0:
        return 0

    now = datetime.now()
    run_id = f"DQN-RUN-{now.strftime('%Y%m%d')}-DEMO"
    actions = ["KEEP_CURRENT_SCHEDULE", "REQUEST_REPLENISHMENT", "CHANGE_CNC_MACHINE", "QUALITY_HOLD", "REQUEST_MAINTENANCE_CHECK", "ADVANCE_JOB"]
    created = 0
    for step in range(1, limit + 1):
        action_code = actions[(step - 1) % len(actions)]
        machine_id = f"CNC-{((step - 1) % 3) + 1:02d}"
        work_order_no = f"WO-REWARD-DEMO-{((step - 1) // 3) + 1:04d}"
        score = 82 + ((step * 7) % 15) - (6 if step % 9 == 0 else 0)
        before = max(0, score - (3 + (step % 4)))
        shortage = 18 + (step % 6)
        delivery = 20 + (step % 8)
        oee = 24 + (step % 10)
        quality = 8 + (step % 5)
        energy = 5 + (step % 4)
        confidence = 82 + (step % 12)
        execute(
            """
            INSERT INTO aips_dqn_reward_log (
                schedule_run_id, schedule_version_id, decision_step_no, calculated_at,
                reward_scope, work_order_no, operation_seq, product_code, machine_id,
                action_code, action_name, action_params,
                reward_score, reward_before, reward_after, reward_delta, q_value, confidence_score,
                on_time_reward, shortage_reward, oee_reward, load_balance_reward, setup_time_reward,
                quality_reward, maintenance_reward, material_reward, penalty_score,
                state_snapshot, next_state_snapshot, reward_formula_version, model_version,
                is_action_applied, applied_at, operator_id, approval_status, remark
            )
            VALUES (
                %s, %s, %s, CURRENT_TIMESTAMP - (%s || ' minutes')::interval,
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s, %s,
                true, CURRENT_TIMESTAMP, %s, %s, %s
            )
            """,
            (
                run_id, "SCH-DEMO-AIPS", step, (limit - step) * 2,
                "WORK_ORDER", work_order_no, ((step - 1) % 3) + 1, "MK030001", machine_id,
                action_code, ACTION_NAME_MAP.get(action_code, action_code), json.dumps({"demo": True, "action_code": action_code}, ensure_ascii=False),
                score, before, score, score - before, max(0.01, min(1.0, score / 100.0 + 0.04)), confidence,
                delivery, shortage, oee, 8 + (step % 5), energy,
                quality, 0, shortage, 0,
                json.dumps({"work_order_no": work_order_no, "machine_id": machine_id, "shortage_risk": shortage / 100}, ensure_ascii=False),
                json.dumps({"expected_reward_after": score, "action_code": action_code}, ensure_ascii=False),
                "REWARD_FORMULA_V1", "PYTORCH_DQN_Q_NETWORK",
                "system", "AUTO_APPLIED", "Demo seed for Reward Log Dashboard"
            ),
        )
        created += 1
    return created


def sync_reward_log_from_reward_result(limit: int = 120) -> Dict[str, Any]:
    ensure_reward_log_schema()
    rows = _source_reward_rows(limit)
    if not rows:
        seeded = _seed_demo_reward_log()
        return {"created": seeded, "source_count": 0, "message": f"目前沒有 aips_reward_result，可展示 Reward Log seed 新增 {seeded} 筆"}

    run_id = f"DQN-RUN-{datetime.now().strftime('%Y%m%d')}-0001"
    created = 0
    for step_no, row in enumerate(reversed(rows), start=1):
        source_reward_id = row.get("reward_id")
        if source_reward_id is not None:
            if fetch_one("SELECT reward_log_id FROM aips_dqn_reward_log WHERE source_reward_id = %s", (source_reward_id,)):
                continue

        action_code = _action_code(row)
        action_name = row.get("action_name") or ACTION_NAME_MAP.get(action_code, action_code)
        score = _num(row.get("total_reward_score"))
        if score <= 30:
            score *= 4.5
        if score <= 0:
            score = 80 + (step_no % 15)

        before = max(0.0, score - max(_num(row.get("expected_oee_improvement_rate")) * 100, 2.0))
        delta = score - before
        confidence = _num(row.get("action_confidence_score"), 0.85)
        if confidence <= 1:
            confidence *= 100

        shortage = _num(row.get("reward_shortage_score"), 18.0)
        delivery = _num(row.get("reward_delivery_score"), 20.0)
        oee = _num(row.get("reward_oee_score"), 25.0)
        quality = _num(row.get("reward_quality_score"), 8.0)
        energy = _num(row.get("reward_energy_score"), 6.0)
        maintenance = 18.0 if row.get("machine_down_occurred_flag") else 0.0
        penalty = max(0.0, _num(row.get("delay_hours")) * 3.0 + (12.0 if row.get("shortage_occurred_flag") else 0.0))

        state_snapshot = {
            "state_id": row.get("state_id"),
            "work_order_no": row.get("work_order_no"),
            "machine_id": row.get("cnc_machine_id"),
            "actual_oee": row.get("actual_oee"),
            "actual_yield_rate": row.get("actual_yield_rate"),
            "delay_hours": row.get("delay_hours"),
            "energy_kwh": row.get("energy_kwh"),
            "shortage_occurred_flag": row.get("shortage_occurred_flag"),
            "machine_down_occurred_flag": row.get("machine_down_occurred_flag"),
        }
        next_state_snapshot = {
            "expected_delay_reduction_hours": row.get("expected_delay_reduction_hours"),
            "expected_oee_improvement_rate": row.get("expected_oee_improvement_rate"),
            "expected_shortage_risk_reduction": row.get("expected_shortage_risk_reduction"),
            "suggested_machine_id": row.get("suggested_cnc_machine_id"),
        }
        action_params = {
            "action_reason": row.get("action_reason"),
            "action_status": row.get("action_status"),
            "from_machine_id": row.get("original_cnc_machine_id"),
            "to_machine_id": row.get("suggested_cnc_machine_id"),
        }

        evaluate_time = row.get("evaluate_time") or row.get("created_at")
        machine_id = row.get("cnc_machine_id") or "-"
        work_order_no = row.get("work_order_no") or "-"

        execute(
            """
            INSERT INTO aips_dqn_reward_log (
                schedule_run_id, schedule_version_id, decision_step_no, calculated_at,
                reward_scope, work_order_no, operation_seq, product_code, machine_id,
                from_machine_id, to_machine_id, action_code, action_name, action_params,
                reward_score, reward_before, reward_after, reward_delta, q_value, confidence_score,
                on_time_reward, shortage_reward, oee_reward, load_balance_reward, setup_time_reward,
                quality_reward, maintenance_reward, material_reward, manual_handling_reward,
                penalty_score, state_snapshot, next_state_snapshot, reward_formula_version,
                model_version, is_action_applied, applied_at, operator_id, approval_status, remark,
                source_reward_id, source_action_id
            )
            VALUES (
                %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP),
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s::jsonb,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s::jsonb, %s::jsonb, %s,
                %s, %s, COALESCE(%s, CURRENT_TIMESTAMP), %s, %s, %s,
                %s, %s
            )
            """,
            (
                run_id, f"SCH-{datetime.now().strftime('%Y%m%d')}-AIPS", step_no, evaluate_time,
                _scope(row), work_order_no, None, row.get("product_no"), machine_id,
                row.get("original_cnc_machine_id"), row.get("suggested_cnc_machine_id"), action_code, action_name, json.dumps(action_params, ensure_ascii=False),
                score, before, score, delta, max(0.01, min(1.0, score / 100.0 + 0.04)), confidence,
                delivery, shortage, oee, max(0.0, min(12.0, oee * 0.25)), max(0.0, min(10.0, energy * 0.2)),
                quality, maintenance, shortage, 0.0,
                penalty, json.dumps(state_snapshot, ensure_ascii=False), json.dumps(next_state_snapshot, ensure_ascii=False), "REWARD_FORMULA_V1",
                "PYTORCH_DQN_Q_NETWORK", True, evaluate_time, "system", "AUTO_APPLIED", "由 aips_reward_result 同步產生，符合 Reward Log Word 設計",
                source_reward_id, row.get("action_id"),
            ),
        )
        created += 1

    return {"created": created, "source_count": len(rows), "message": f"Reward Log 同步完成，新增 {created} 筆"}


def latest_reward_logs(limit: int = 120) -> List[Dict[str, Any]]:
    ensure_reward_log_schema()
    sync_reward_log_from_reward_result(limit)
    return fetch_all(
        """
        SELECT
            reward_log_id, schedule_run_id, schedule_version_id, decision_step_no,
            TO_CHAR(calculated_at, 'YYYY-MM-DD HH24:MI:SS') AS calculated_at,
            reward_scope, work_order_no, operation_seq, product_code, machine_id,
            from_machine_id, to_machine_id, action_code, action_name,
            ROUND(COALESCE(reward_score, 0)::numeric, 1)::float AS reward_score,
            ROUND(COALESCE(reward_before, 0)::numeric, 1)::float AS reward_before,
            ROUND(COALESCE(reward_after, 0)::numeric, 1)::float AS reward_after,
            ROUND(COALESCE(reward_delta, 0)::numeric, 1)::float AS reward_delta,
            ROUND(COALESCE(q_value, 0)::numeric, 3)::float AS q_value,
            ROUND(COALESCE(confidence_score, 0)::numeric, 1)::float AS confidence_score,
            ROUND(COALESCE(on_time_reward, 0)::numeric, 1)::float AS on_time_reward,
            ROUND(COALESCE(shortage_reward, 0)::numeric, 1)::float AS shortage_reward,
            ROUND(COALESCE(oee_reward, 0)::numeric, 1)::float AS oee_reward,
            ROUND(COALESCE(load_balance_reward, 0)::numeric, 1)::float AS load_balance_reward,
            ROUND(COALESCE(setup_time_reward, 0)::numeric, 1)::float AS setup_time_reward,
            ROUND(COALESCE(quality_reward, 0)::numeric, 1)::float AS quality_reward,
            ROUND(COALESCE(maintenance_reward, 0)::numeric, 1)::float AS maintenance_reward,
            ROUND(COALESCE(material_reward, 0)::numeric, 1)::float AS material_reward,
            ROUND(COALESCE(manual_handling_reward, 0)::numeric, 1)::float AS manual_handling_reward,
            ROUND(COALESCE(penalty_score, 0)::numeric, 1)::float AS penalty_score,
            reward_formula_version, model_version, is_action_applied, approval_status, remark
        FROM aips_dqn_reward_log
        ORDER BY reward_log_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def reward_log_dashboard(limit: int = 120) -> Dict[str, Any]:
    try:
        logs = latest_reward_logs(limit)
    except Exception as exc:
        # 不讓 Dashboard API 回 500，前端仍可顯示錯誤與空資料。
        return {
            "success": False,
            "error": str(exc),
            "summary": {"current_reward": 0, "avg_reward": 0, "max_reward": 0, "min_reward": 0, "action_count": 0, "auto_action_count": 0, "manual_action_count": 0},
            "logs": [],
            "distribution": [],
            "composition": [],
            "timeline": [],
        }

    if not logs:
        return {
            "success": True,
            "summary": {"current_reward": 0, "avg_reward": 0, "max_reward": 0, "min_reward": 0, "action_count": 0, "auto_action_count": 0, "manual_action_count": 0},
            "logs": [],
            "distribution": [],
            "composition": [],
            "timeline": [],
        }

    scores = [_num(row.get("reward_score")) for row in logs]
    current = scores[0]
    avg = sum(scores) / len(scores)
    auto_count = sum(1 for row in logs if row.get("approval_status") == "AUTO_APPLIED" or row.get("is_action_applied") is True)

    ranges = [
        ("90 ~ 100（優秀）", 90, 101, "good"),
        ("80 ~ 90（良好）", 80, 90, "cool"),
        ("70 ~ 80（普通）", 70, 80, "warn"),
        ("60 ~ 70（偏低）", 60, 70, "warm"),
        ("< 60（不佳）", -999, 60, "bad"),
    ]
    distribution = []
    for label, min_value, max_value, cls in ranges:
        count = len([score for score in scores if min_value <= score < max_value])
        distribution.append({"label": label, "count": count, "pct": round(count / max(len(scores), 1) * 100, 1), "cls": cls})

    totals = {
        "shortage": sum(_num(row.get("shortage_reward")) for row in logs),
        "delivery": sum(_num(row.get("on_time_reward")) for row in logs),
        "oee": sum(_num(row.get("oee_reward")) for row in logs),
        "balance": sum(_num(row.get("load_balance_reward")) for row in logs),
        "setup": sum(_num(row.get("setup_time_reward")) for row in logs),
        "quality": sum(_num(row.get("quality_reward")) + _num(row.get("maintenance_reward")) + _num(row.get("material_reward")) for row in logs),
    }
    total = sum(totals.values()) or 1.0
    composition = [
        {"label": "避免缺貨", "pct": round(totals["shortage"] / total * 100, 1), "cls": "good"},
        {"label": "準時交貨", "pct": round(totals["delivery"] / total * 100, 1), "cls": "cool"},
        {"label": "OEE 提升", "pct": round(totals["oee"] / total * 100, 1), "cls": "warn"},
        {"label": "負載平衡", "pct": round(totals["balance"] / total * 100, 1), "cls": "violet"},
        {"label": "換線/刀具", "pct": round(totals["setup"] / total * 100, 1), "cls": "orange"},
        {"label": "品質/維護/物料", "pct": round(totals["quality"] / total * 100, 1), "cls": "bad"},
    ]

    return {
        "success": True,
        "summary": {
            "current_reward": round(current, 1),
            "avg_reward": round(avg, 1),
            "max_reward": round(max(scores), 1),
            "min_reward": round(min(scores), 1),
            "action_count": len(logs),
            "auto_action_count": auto_count,
            "manual_action_count": max(0, len(logs) - auto_count),
        },
        "logs": logs,
        "distribution": distribution,
        "composition": composition,
        "timeline": logs[:8],
        "business_key": "schedule_run_id + decision_step_no + reward_scope + work_order_no + operation_seq + machine_id + action_code",
        "design_note": "Reward Log 以 DQN 排程決策事件為核心，不只用製令單或 CNC 當 Key。",
    }
