from fastapi import APIRouter
from app.core.database import fetch_all
from app.core.schema_guard import ensure_extra_schema

router = APIRouter()

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
    FIX42：
    FIX40 直接寫 current_process_status / remaining_qty 條件。
    但使用者現有 DB 可能沒有這兩個欄位，或欄位名稱跟 demo schema 不完全一致，
    SQL 例外被 _safe_scalar 吃掉後就會變成 0 / 0。

    此函式會先檢查 work_order_progress_snapshot 實際欄位，再動態組 SQL。
    若找不到可判斷欄位，至少會回傳：
      processed = 0
      unprocessed = total
    避免畫面明明有 ERP 製令單總數，卻顯示已處理 0 / 未處理 0。
    """
    table_name = "work_order_progress_snapshot"
    total = _safe_count(table_name)
    if total <= 0:
        return 0, 0, 0

    cols = _table_columns(table_name)
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

    # 若完全沒有可判斷欄位：全部視為未處理，至少數字不能 0/0。
    if not conditions:
        return 0, total, total

    where = " OR ".join(f"({c})" for c in conditions)

    processed = _safe_scalar(f"""
        SELECT COUNT(*) AS cnt
        FROM {table_name}
        WHERE {where}
    """)
    processed = max(0, min(processed, total))
    unprocessed = max(0, total - processed)
    return processed, unprocessed, total

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

    try:
        result["latest_actions"] = fetch_all(
            """
            SELECT action_id, action_time, action_name, work_order_no, original_cnc_machine_id,
                   expected_oee_improvement_rate, action_confidence_score, action_reason
            FROM aips_dqn_action_log
            ORDER BY action_id DESC
            LIMIT 10
            """
        )
    except Exception:
        result["latest_actions"] = []

    return result
