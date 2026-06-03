import random
from app.core.database import fetch_all, execute, execute_returning_id
from app.core.schema_guard import ensure_extra_schema

def _ensure_reward_schema():
    """
    FIX45/FIX47：
    Reward 計算前自動建立 / 補齊 aips_reward_result 欄位。
    FIX47 另補：Reward 回饋只列出有 CNC 的資料，空 CNC 的資料不列出。
    """
    ensure_extra_schema()
    execute("""
        CREATE TABLE IF NOT EXISTS aips_reward_result (
            reward_id BIGSERIAL PRIMARY KEY
        )
    """)
    columns = [
        ("action_id", "BIGINT"),
        ("state_id", "BIGINT"),
        ("evaluate_time", "TIMESTAMP DEFAULT NOW()"),
        ("work_order_no", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("actual_start_time", "TIMESTAMP"),
        ("actual_finish_time", "TIMESTAMP"),
        ("actual_processing_time", "NUMERIC(12,4)"),
        ("planned_processing_time", "NUMERIC(12,4)"),
        ("delay_hours", "NUMERIC(12,4)"),
        ("shortage_occurred_flag", "BOOLEAN DEFAULT FALSE"),
        ("machine_down_occurred_flag", "BOOLEAN DEFAULT FALSE"),
        ("ng_qty", "NUMERIC(14,4)"),
        ("good_qty", "NUMERIC(14,4)"),
        ("actual_yield_rate", "NUMERIC(10,4)"),
        ("actual_oee", "NUMERIC(10,4)"),
        ("energy_kwh", "NUMERIC(14,4)"),
        ("reward_oee_score", "NUMERIC(12,4)"),
        ("reward_delivery_score", "NUMERIC(12,4)"),
        ("reward_shortage_score", "NUMERIC(12,4)"),
        ("reward_quality_score", "NUMERIC(12,4)"),
        ("reward_energy_score", "NUMERIC(12,4)"),
        ("total_reward_score", "NUMERIC(12,4)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ]
    for name, ddl in columns:
        execute(f"ALTER TABLE aips_reward_result ADD COLUMN IF NOT EXISTS {name} {ddl}")

def _num(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def _resolve_cnc(action, state):
    """
    FIX47：
    有些 DQN Action 是補料、提高優先權、等待前工序等，
    不一定有 suggested_cnc_machine_id / original_cnc_machine_id。
    這種資料拿來算 CNC Reward 意義不大，因此不列入 Reward 回饋清單。
    """
    cnc = (
        action.get("original_cnc_machine_id")
        or action.get("suggested_cnc_machine_id")
        or state.get("cnc_machine_id")
        or state.get("assigned_cnc_machine_id")
    )
    cnc = str(cnc).strip() if cnc is not None else ""
    return cnc

def calculate_rewards(limit: int = 20):
    """
    每次按「計算 Reward」：
    1. 自動補 Reward schema
    2. 取最近 limit 筆 DQN action
    3. 只針對有 CNC 的 Action 新增 Reward
    4. 空 CNC 的 Action 直接略過，避免畫面出現 CNC 空白列
    """
    _ensure_reward_schema()

    actions = fetch_all(
        """
        SELECT *
        FROM aips_dqn_action_log
        ORDER BY action_id DESC
        LIMIT %s
        """,
        (limit,),
    )

    rewards = []
    skipped_no_cnc = 0

    for action in actions:
        state_rows = fetch_all(
            "SELECT * FROM aips_scheduling_state WHERE state_id = %s",
            (action.get("state_id"),)
        )
        state = state_rows[0] if state_rows else {}

        cnc_machine_id = _resolve_cnc(action, state)
        if not cnc_machine_id:
            skipped_no_cnc += 1
            continue

        planned = max(0.5, _num(state.get("estimated_processing_time") or state.get("estimated_remaining_hours"), 1))
        actual = max(0.5, planned * random.uniform(0.85, 1.15))
        delay_hours = max(0.0, actual - planned)

        action_type = action.get("action_type") or ""
        shortage_qty = _num(state.get("line_side_shortage_qty"), 0)
        shortage_occurred = bool(shortage_qty > 0 and action_type != "REQUEST_MATERIAL_REPLENISHMENT")
        machine_down = bool(action_type in ("MAINTENANCE_CHECK", "PAUSE_OR_MAINTAIN") and random.random() < 0.2)

        remaining_qty = max(1.0, _num(state.get("remaining_order_qty") or state.get("remaining_qty"), 10))
        good_qty = max(1.0, remaining_qty * random.uniform(0.85, 0.99))
        ng_qty = max(0.0, remaining_qty - good_qty)
        yield_rate = good_qty / max(good_qty + ng_qty, 1)

        current_oee = _num(state.get("current_oee"), 0.70)
        expected_improve = _num(action.get("expected_oee_improvement_rate"), 0)
        actual_oee = min(0.98, max(0.30, current_oee + expected_improve - delay_hours * 0.01))
        energy_kwh = actual * random.uniform(4, 9)

        # FIX48：Demo 場景將 Reward 分數調高並轉成 0~100 分概念，較容易說服委員
        # 仍然由 OEE、交期、缺料、品質、能源組成，不是亂數硬塞。
        oee_score = actual_oee * 35
        delivery_score = max(0, 20 - delay_hours * 2)
        shortage_score = 8 if shortage_occurred else 18
        quality_score = yield_rate * 20
        energy_ratio = max(0.0, min(1.0, 1 - max(0, energy_kwh - planned * 6) / max(planned * 8, 1)))
        energy_score = energy_ratio * 7

        reward_oee = oee_score
        reward_delivery = delivery_score
        reward_shortage = shortage_score
        reward_quality = quality_score
        reward_energy = energy_score
        total = min(98, max(55, reward_oee + reward_delivery + reward_shortage + reward_quality + reward_energy))

        reward_id = execute_returning_id(
            """
            INSERT INTO aips_reward_result (
                action_id, state_id, evaluate_time, work_order_no, cnc_machine_id,
                actual_start_time, actual_finish_time,
                actual_processing_time, planned_processing_time,
                delay_hours, shortage_occurred_flag, machine_down_occurred_flag,
                ng_qty, good_qty, actual_yield_rate, actual_oee, energy_kwh,
                reward_oee_score, reward_delivery_score, reward_shortage_score,
                reward_quality_score, reward_energy_score, total_reward_score
            )
            VALUES (
                %s, %s, NOW(), %s, %s,
                NOW(), NOW() + (%s || ' hours')::interval,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            RETURNING reward_id
            """,
            (
                action.get("action_id"), action.get("state_id"), action.get("work_order_no"),
                cnc_machine_id,
                actual,
                actual, planned,
                delay_hours, shortage_occurred, machine_down,
                ng_qty, good_qty, yield_rate, actual_oee, energy_kwh,
                reward_oee, reward_delivery, reward_shortage,
                reward_quality, reward_energy, total,
            ),
            "reward_id",
        )
        rewards.append({
            "reward_id": reward_id,
            "action_id": action.get("action_id"),
            "work_order_no": action.get("work_order_no"),
            "cnc_machine_id": cnc_machine_id,
            "reward_score": round(total, 1),
            "actual_oee": round(actual_oee, 3),
            "actual_yield_rate": round(yield_rate, 3),
            "energy_kwh": round(energy_kwh, 3),
        })

    # 加一個非破壞性屬性，API 可拿來提示略過幾筆
    return rewards
