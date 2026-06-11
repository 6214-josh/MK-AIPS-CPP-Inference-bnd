from __future__ import annotations

import json
import random
from datetime import datetime

from app.core.database import fetch_all, fetch_one, execute, execute_returning_id
from app.core.schema_guard import ensure_extra_schema


def _num(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


def _next_erp_work_order_no() -> str:
    row = fetch_one("SELECT nextval('aips_erp_simulator_seq') AS seq")
    seq = int(row["seq"]) if row else random.randint(1, 99999)
    return f"WO-ERP-{datetime.now().strftime('%Y%m%d')}-{seq:05d}"


def ensure_erp_simulator_schema():
    ensure_extra_schema()
    execute("CREATE SEQUENCE IF NOT EXISTS aips_erp_simulator_seq START 1")


def receive_erp_order_demo(source: str = "ERP_SIMULATOR", auto_process_flag: bool = False, cnc_machine_id: str | None = None):
    """
    ERP 模擬器接收新的 ERP 製令資料。
    寫入 work_order_progress_snapshot，狀態為 RECEIVED。
    """
    ensure_erp_simulator_schema()

    idx = random.randint(1, 999)
    work_order_no = _next_erp_work_order_no()
    cnc = cnc_machine_id if cnc_machine_id and cnc_machine_id != "ALL" else f"CNC-{random.randint(1, 14):02d}"
    planned_qty = random.choice([80, 100, 120, 150])
    priority = random.randint(5, 9)
    estimated_hours = random.randint(4, 12)

    snapshot_id = execute_returning_id(
        """
        INSERT INTO work_order_progress_snapshot (
            snapshot_time, work_order_no, sales_order_no, customer_id,
            product_no, product_name, process_code,
            planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
            due_date, priority_level, current_process_status,
            assigned_cnc_machine_id, estimated_remaining_hours, delay_risk_flag
        )
        VALUES (
            NOW(), %s, %s, %s,
            %s, %s, %s,
            %s, 0, 0, 0, %s,
            NOW() + (%s || ' hours')::interval, %s, %s,
            %s, %s, FALSE
        )
        RETURNING snapshot_id
        """,
        (
            work_order_no, f"SO-ERP-{idx:04d}", "ERP-CUSTOMER",
            "MK030001", "ERP 模擬製令零件", "CNC",
            planned_qty, planned_qty,
            24 + estimated_hours, priority,
            "RECEIVED",
            cnc, estimated_hours,
        ),
        "snapshot_id",
    )

    execute(
        """
        INSERT INTO aips_external_integration_log (
            integration_time, target_system, direction, api_name,
            request_json, response_json, status, message
        )
        VALUES (
            NOW(), 'AIPS', 'INBOUND', 'ERP_SIMULATOR_RECEIVE_WORK_ORDER',
            %s::jsonb,
            jsonb_build_object('snapshot_id', %s, 'work_order_no', %s, 'auto_process_flag', %s),
            'SUCCESS',
            'ERP 模擬器送入新製令，AIPS 已接收'
        )
        """,
        (
            json.dumps({
                "source": source,
                "work_order_no": work_order_no,
                "planned_qty": planned_qty,
                "priority_level": priority,
                "assigned_cnc_machine_id": cnc,
                "current_process_status": "RECEIVED",
            }, ensure_ascii=False),
            snapshot_id, work_order_no, auto_process_flag,
        ),
    )

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "work_order_no": work_order_no,
        "planned_qty": planned_qty,
        "assigned_cnc_machine_id": cnc,
        "status": "RECEIVED",
        "message": f"ERP 模擬器已送入新製令 {work_order_no}",
    }


def process_pending_erp_orders(limit: int = 20, callback_source: str = "AIPS_FULL_FLOW"):
    """
    模擬 AIPS 對 ERP 製令資料完成處理後，回傳 ERP 模擬器。
    做法：
    1. 找每張 ERP 製令最新狀態
    2. 若仍非 COMPLETED / PROCESSED / CLOSED，新增一筆最新 snapshot，狀態改 PROCESSED
    3. 寫入 aips_external_integration_log OUTBOUND，代表回傳 ERP 模擬器
    """
    ensure_erp_simulator_schema()

    rows = fetch_all(
        """
        WITH latest AS (
            SELECT DISTINCT ON (work_order_no) *
            FROM work_order_progress_snapshot
            WHERE work_order_no LIKE 'WO-ERP-%%'
            ORDER BY work_order_no, snapshot_id DESC
        )
        SELECT *
        FROM latest
        WHERE UPPER(COALESCE(current_process_status, '')) NOT IN ('PROCESSED','COMPLETED','DONE','CLOSED')
          AND COALESCE(remaining_qty, 0) > 0
        ORDER BY snapshot_id DESC
        LIMIT %s
        """,
        (limit,),
    )

    processed = []
    for row in rows:
        planned = max(1.0, _num(row.get("planned_qty"), 1))
        good = max(1.0, planned * random.uniform(0.92, 0.99))
        ng = max(0.0, planned - good)
        snapshot_id = execute_returning_id(
            """
            INSERT INTO work_order_progress_snapshot (
                snapshot_time, work_order_no, sales_order_no, customer_id,
                product_no, product_name, process_code,
                planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
                due_date, priority_level, current_process_status,
                assigned_cnc_machine_id, estimated_remaining_hours, delay_risk_flag
            )
            VALUES (
                NOW(), %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, 0,
                %s, %s, 'PROCESSED',
                %s, 0, FALSE
            )
            RETURNING snapshot_id
            """,
            (
                row.get("work_order_no"), row.get("sales_order_no"), row.get("customer_id"),
                row.get("product_no"), row.get("product_name"), row.get("process_code"),
                row.get("planned_qty"), row.get("planned_qty"), good, ng,
                row.get("due_date"), row.get("priority_level"),
                row.get("assigned_cnc_machine_id"),
            ),
            "snapshot_id",
        )

        execute(
            """
            INSERT INTO aips_external_integration_log (
                integration_time, target_system, direction, api_name,
                request_json, response_json, status, message
            )
            VALUES (
                NOW(), 'ERP_SIMULATOR', 'OUTBOUND', 'AIPS_RETURN_WORK_ORDER_RESULT',
                %s::jsonb,
                jsonb_build_object('new_snapshot_id', %s, 'result_status', 'PROCESSED'),
                'SUCCESS',
                'AIPS 已完成 ERP 製令資料處理，並回傳 ERP 模擬器'
            )
            """,
            (
                json.dumps({
                    "callback_source": callback_source,
                    "work_order_no": row.get("work_order_no"),
                    "old_snapshot_id": row.get("snapshot_id"),
                    "new_snapshot_id": snapshot_id,
                    "processed_status": "PROCESSED",
                    "remaining_qty": 0,
                }, ensure_ascii=False),
                snapshot_id,
            ),
        )

        processed.append({
            "work_order_no": row.get("work_order_no"),
            "old_snapshot_id": row.get("snapshot_id"),
            "new_snapshot_id": snapshot_id,
            "status": "PROCESSED",
        })

    return {
        "success": True,
        "processed_count": len(processed),
        "processed": processed,
        "message": f"AIPS 已回傳 ERP 模擬器 {len(processed)} 筆處理結果",
    }


def latest_erp_orders(limit: int = 100):
    ensure_erp_simulator_schema()
    return fetch_all(
        """
        WITH latest AS (
            SELECT DISTINCT ON (work_order_no) *
            FROM work_order_progress_snapshot
            WHERE work_order_no LIKE 'WO-ERP-%%'
            ORDER BY work_order_no, snapshot_id DESC
        )
        SELECT *
        FROM latest
        ORDER BY snapshot_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def erp_callbacks(limit: int = 100):
    ensure_erp_simulator_schema()
    return fetch_all(
        """
        SELECT integration_id, integration_time, target_system, direction, api_name,
               status, message, request_json, response_json
        FROM aips_external_integration_log
        WHERE api_name IN ('ERP_SIMULATOR_RECEIVE_WORK_ORDER', 'AIPS_RETURN_WORK_ORDER_RESULT')
        ORDER BY integration_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def erp_summary():
    ensure_erp_simulator_schema()
    row = fetch_one(
        """
        WITH latest AS (
            SELECT DISTINCT ON (work_order_no) *
            FROM work_order_progress_snapshot
            WHERE work_order_no LIKE 'WO-ERP-%%'
            ORDER BY work_order_no, snapshot_id DESC
        )
        SELECT
            COUNT(*) AS total_count,
            SUM(CASE
                WHEN UPPER(COALESCE(current_process_status, '')) IN ('PROCESSED','COMPLETED','DONE','CLOSED')
                  OR COALESCE(remaining_qty, 0) <= 0
                THEN 1 ELSE 0 END) AS processed_count,
            SUM(CASE
                WHEN UPPER(COALESCE(current_process_status, '')) NOT IN ('PROCESSED','COMPLETED','DONE','CLOSED')
                 AND COALESCE(remaining_qty, 0) > 0
                THEN 1 ELSE 0 END) AS unprocessed_count
        FROM latest
        """
    )
    return {
        "total_count": int(row.get("total_count") or 0) if row else 0,
        "processed_count": int(row.get("processed_count") or 0) if row else 0,
        "unprocessed_count": int(row.get("unprocessed_count") or 0) if row else 0,
    }
