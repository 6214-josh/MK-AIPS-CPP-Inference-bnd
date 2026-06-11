from fastapi import APIRouter
from app.core.database import fetch_all, execute
from app.core.schema_guard import ensure_extra_schema
from app.services.erp_simulator_service import erp_summary

router = APIRouter()

DASHBOARD_CNC_CODES = [f"CNC-{i:02d}" for i in range(1, 15)]

@router.get("/health")
def health():
    return {"status": "ok", "message": "AIPS API is running"}

def _safe_count(table_name: str) -> int:
    try:
        return int(fetch_all(f"SELECT COUNT(*) AS cnt FROM {table_name}")[0]["cnt"])
    except Exception:
        return 0

def _safe_scalar(sql: str) -> int:
    try:
        return int(fetch_all(sql)[0]["cnt"])
    except Exception:
        return 0

def _table_columns(table_name: str):
    try:
        rows = fetch_all(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {r["column_name"] for r in rows}
    except Exception:
        return set()

def _work_order_processed_unprocessed():
    """
    FIX67：
    ERP 卡片改用「每張製令最新一筆 snapshot」計算。
    否則同一張 ERP 製令接收一筆、處理完又新增一筆 callback snapshot，
    舊算法會把兩筆都算進去，ERP 已處理 / 未處理會對不起來。
    """
    table_name = "work_order_progress_snapshot"
    total_rows = _safe_count(table_name)
    if total_rows <= 0:
        return 0, 0, 0

    cols = _table_columns(table_name)
    if "work_order_no" not in cols:
        return 0, total_rows, total_rows

    latest_cte = """
        WITH latest AS (
            SELECT DISTINCT ON (work_order_no) *
            FROM work_order_progress_snapshot
            ORDER BY work_order_no, snapshot_id DESC
        )
    """

    conditions = []

    status_candidates = [
        "current_process_status",
        "process_status",
        "work_order_status",
        "order_status",
        "status",
        "doc_status",
    ]
    for col in status_candidates:
        if col in cols:
            conditions.append(
                f"""
                UPPER(COALESCE({col}::text, '')) IN
                ('DONE','COMPLETED','FINISHED','CLOSED','PROCESSED','COMPLETE')
                OR COALESCE({col}::text, '') IN ('已完成','已處理','完成','結案','關閉')
                """
            )
            break

    qty_candidates = ["remaining_qty", "remain_qty", "unprocessed_qty", "left_qty"]
    for col in qty_candidates:
        if col in cols:
            conditions.append(f"COALESCE({col}, 999999) <= 0")
            break

    total = _safe_scalar(latest_cte + " SELECT COUNT(*) AS cnt FROM latest")
    if total <= 0:
        return 0, 0, 0

    if not conditions:
        return 0, total, total

    where = " OR ".join(f"({c})" for c in conditions)
    processed = _safe_scalar(latest_cte + f" SELECT COUNT(*) AS cnt FROM latest WHERE {where}")
    processed = max(0, min(processed, total))
    unprocessed = max(0, total - processed)
    return processed, unprocessed, total

def _ensure_dashboard_actions_14():
    """
    總覽儀表板不可只看到 3 台 CNC。
    若 aips_dqn_action_log 目前缺少 CNC-01 ~ CNC-14 的建議，
    這裡自動補每台 CNC 的 demo 建議，讓「最新建議」可依 14 台 CNC 篩選。
    """
    existing = set()
    try:
        rows = fetch_all(
            """
            SELECT DISTINCT COALESCE(original_cnc_machine_id, suggested_cnc_machine_id) AS cnc
            FROM aips_dqn_action_log
            WHERE COALESCE(original_cnc_machine_id, suggested_cnc_machine_id) IS NOT NULL
            """
        )
        existing = {row["cnc"] for row in rows if row.get("cnc")}
    except Exception:
        existing = set()

    action_templates = [
        ("REQUEST_MATERIAL_REPLENISHMENT", "提前補料", "線邊庫存偏低，建議提前補料避免 CNC 待料。"),
        ("INCREASE_ORDER_PRIORITY", "提高製令單優先順序", "交期壓力偏高，建議提高優先順序。"),
        ("REASSIGN_MACHINE", "更換 CNC 機台", "目前負載較高，建議評估改派可用 CNC。"),
        ("MAINTENANCE_CHECK", "安排預防保養", "電表 THD 或負載波動偏高，建議安排檢查。"),
        ("KEEP_CURRENT_SCHEDULE", "維持目前排程", "目前缺料與延遲風險可控，建議維持原排程。"),
    ]

    for index, cnc in enumerate(DASHBOARD_CNC_CODES, start=1):
        if cnc in existing:
            continue
        action_type, action_name, reason = action_templates[(index - 1) % len(action_templates)]
        target_cnc = DASHBOARD_CNC_CODES[index % len(DASHBOARD_CNC_CODES)]
        execute(
            """
            INSERT INTO aips_dqn_action_log (
                action_time, action_type, action_name, work_order_no, product_no,
                original_cnc_machine_id, suggested_cnc_machine_id,
                expected_delay_reduction_hours, expected_oee_improvement_rate,
                expected_shortage_risk_reduction, action_confidence_score,
                action_status, action_reason, created_at
            )
            VALUES (
                NOW(), %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                'PENDING', %s, NOW()
            )
            """,
            (
                action_type,
                action_name,
                f"WO-DASH-{index:02d}",
                f"MK030{((index - 1) % 5) + 1:03d}",
                cnc,
                target_cnc,
                round(0.5 + (index % 5) * 0.4, 2),
                round(0.01 + (index % 8) * 0.01, 3),
                round(0.08 + (index % 6) * 0.05, 3),
                round(0.78 + (index % 10) * 0.02, 2),
                reason,
            ),
        )


@router.get("/dashboard/summary")
def summary():
    ensure_extra_schema()

    tables = [
        "cnc_meter_raw_data", "cnc_meter_feature", "work_order_progress_snapshot",
        "line_side_inventory_snapshot", "aips_scheduling_state", "aips_dqn_action_log",
        "aips_production_prediction", "aips_reward_result", "aips_exception_event",
    ]

    result = {}
    for table in tables:
        result[table] = _safe_count(table)

    processed, unprocessed, total = _work_order_processed_unprocessed()
    result["erp_processed_count"] = processed
    result["erp_unprocessed_count"] = unprocessed
    result["erp_total_count"] = total
    result["cnc_machine_count"] = 14
    try:
        result["erp_simulator"] = erp_summary()
    except Exception:
        result["erp_simulator"] = {"total_count": 0, "processed_count": 0, "unprocessed_count": 0}

    try:
        _ensure_dashboard_actions_14()
        result["latest_actions"] = fetch_all(
            """
            SELECT action_id, action_time, action_type, action_name, work_order_no, product_no,
                   original_cnc_machine_id, suggested_cnc_machine_id,
                   expected_oee_improvement_rate, action_confidence_score, action_reason
            FROM aips_dqn_action_log
            ORDER BY action_id DESC
            LIMIT 200
            """
        )
    except Exception:
        result["latest_actions"] = []

    return result
