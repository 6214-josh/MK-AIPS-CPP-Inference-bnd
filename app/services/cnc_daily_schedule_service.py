from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Tuple

from app.core.database import fetch_all, fetch_one, execute, execute_returning_id


CNC_CODES = ["CNC-01", "CNC-02", "CNC-03"]
WORK_START = time(8, 0)
WORK_MINUTES = 8 * 60


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def _parse_day(schedule_date: str | None = None) -> date:
    if not schedule_date:
        return date.today()
    try:
        return datetime.strptime(schedule_date, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _dt(day: date, minute_offset: int) -> datetime:
    return datetime.combine(day, WORK_START) + timedelta(minutes=int(minute_offset))


def ensure_cnc_daily_schedule_schema() -> None:
    execute("""
        CREATE TABLE IF NOT EXISTS aips_product_cnc_process_assumption (
            assumption_id BIGSERIAL PRIMARY KEY
        )
    """)
    assumption_columns = [
        ("product_no", "VARCHAR(80)"),
        ("product_name", "VARCHAR(120)"),
        ("step_no", "INT"),
        ("step_name", "VARCHAR(120)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("processing_minutes", "INT"),
        ("setup_minutes", "INT DEFAULT 0"),
        ("sequence_note", "TEXT"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ]
    for name, ddl in assumption_columns:
        execute(f"ALTER TABLE aips_product_cnc_process_assumption ADD COLUMN IF NOT EXISTS {name} {ddl}")

    execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_product_cnc_process_step
        ON aips_product_cnc_process_assumption(product_no, step_no)
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS aips_cnc_daily_schedule_result (
            schedule_id BIGSERIAL PRIMARY KEY
        )
    """)
    result_columns = [
        ("schedule_date", "DATE"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("product_name", "VARCHAR(120)"),
        ("step_no", "INT"),
        ("step_name", "VARCHAR(120)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("sequence_no_on_cnc", "INT"),
        ("planned_qty", "NUMERIC(14,4)"),
        ("processing_minutes", "INT"),
        ("setup_minutes", "INT DEFAULT 0"),
        ("total_minutes", "INT"),
        ("start_minute", "INT"),
        ("end_minute", "INT"),
        ("start_time", "TIMESTAMP"),
        ("end_time", "TIMESTAMP"),
        ("schedule_status", "VARCHAR(40) DEFAULT 'SCHEDULED'"),
        ("schedule_reason", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ]
    for name, ddl in result_columns:
        execute(f"ALTER TABLE aips_cnc_daily_schedule_result ADD COLUMN IF NOT EXISTS {name} {ddl}")

    execute("CREATE INDEX IF NOT EXISTS ix_cnc_daily_schedule_date ON aips_cnc_daily_schedule_result(schedule_date)")
    execute("CREATE INDEX IF NOT EXISTS ix_cnc_daily_schedule_cnc ON aips_cnc_daily_schedule_result(cnc_machine_id, schedule_date)")


def seed_process_assumptions(reset: bool = False) -> Dict[str, Any]:
    ensure_cnc_daily_schedule_schema()
    if reset:
        execute("DELETE FROM aips_product_cnc_process_assumption")

    row = fetch_one("SELECT COUNT(*) AS cnt FROM aips_product_cnc_process_assumption")
    existing = int(row.get("cnt") or 0) if row else 0
    if existing > 0 and not reset:
        return {"created": 0, "existing": existing, "message": "產品 CNC 加工順序假設資料已存在"}

    # 原則：每個產品不超過 3 個加工步驟，最多透過 CNC-01 / CNC-02 / CNC-03。
    demo_rows = [
        ("MK030001", "精密零件 A", 1, "CNC粗加工", "CNC-01", 60, 10, "先粗加工，再精修，最後檢測"),
        ("MK030001", "精密零件 A", 2, "CNC精修", "CNC-02", 75, 8, "承接 Step1"),
        ("MK030001", "精密零件 A", 3, "CNC尺寸檢測", "CNC-03", 45, 5, "最後 CNC 檢測"),
        ("MK030002", "精密零件 B", 1, "CNC銑削", "CNC-02", 55, 8, "以 CNC-02 為主"),
        ("MK030002", "精密零件 B", 2, "CNC鑽孔", "CNC-03", 65, 6, "承接銑削"),
        ("MK030003", "精密零件 C", 1, "CNC粗加工", "CNC-01", 70, 10, "單件先粗加工"),
        ("MK030003", "精密零件 C", 2, "CNC二次加工", "CNC-03", 50, 6, "CNC-03 二次加工"),
        ("MK030004", "精密零件 D", 1, "CNC加工", "CNC-02", 90, 12, "單步製程"),
        ("MK030005", "精密零件 E", 1, "CNC粗加工", "CNC-01", 80, 10, "高優先品項"),
        ("MK030005", "精密零件 E", 2, "CNC精加工", "CNC-02", 55, 8, "高優先品項"),
        ("MK030005", "精密零件 E", 3, "CNC完工檢測", "CNC-03", 40, 5, "高優先品項"),
    ]

    created = 0
    for row in demo_rows:
        execute(
            """
            INSERT INTO aips_product_cnc_process_assumption (
                product_no, product_name, step_no, step_name, cnc_machine_id,
                processing_minutes, setup_minutes, sequence_note, enabled_flag
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
            ON CONFLICT (product_no, step_no)
            DO UPDATE SET
                product_name = EXCLUDED.product_name,
                step_name = EXCLUDED.step_name,
                cnc_machine_id = EXCLUDED.cnc_machine_id,
                processing_minutes = EXCLUDED.processing_minutes,
                setup_minutes = EXCLUDED.setup_minutes,
                sequence_note = EXCLUDED.sequence_note,
                enabled_flag = TRUE
            """,
            row,
        )
        created += 1

    return {"created": created, "existing": existing, "message": f"已建立 {created} 筆產品 CNC 加工順序假設資料"}


def assumptions() -> List[Dict[str, Any]]:
    ensure_cnc_daily_schedule_schema()
    seed_process_assumptions(reset=False)
    return fetch_all(
        """
        SELECT *
        FROM aips_product_cnc_process_assumption
        WHERE enabled_flag = TRUE
        ORDER BY product_no, step_no
        """
    )


def _candidate_orders(limit: int = 30) -> List[Dict[str, Any]]:
    """
    FIX84：
    work_order_progress_snapshot 可能同一張製令有多筆歷史快照。
    日排程不能把同一張製令的歷史快照全部拿來排，否則同一成品代號看起來會超過三個步驟。
    這裡改成每個 work_order_no + product_no 只取最新一筆。
    """
    rows = fetch_all(
        """
        WITH latest_snapshot AS (
            SELECT DISTINCT ON (work_order_no, product_no)
                work_order_no,
                product_no,
                COALESCE(product_name, product_no) AS product_name,
                COALESCE(planned_qty, remaining_qty, 1) AS planned_qty,
                COALESCE(remaining_qty, planned_qty, 1) AS remaining_qty,
                COALESCE(priority_level, 5) AS priority_level,
                due_date,
                snapshot_id
            FROM work_order_progress_snapshot
            WHERE COALESCE(remaining_qty, planned_qty, 1) > 0
              AND work_order_no IS NOT NULL
              AND product_no IS NOT NULL
            ORDER BY work_order_no, product_no, snapshot_id DESC
        )
        SELECT *
        FROM latest_snapshot
        ORDER BY COALESCE(priority_level, 5) DESC, due_date ASC NULLS LAST, snapshot_id DESC
        LIMIT %s
        """,
        (limit,),
    )

    if rows:
        return rows

    demo = [
        {"work_order_no": "WO-SCH-001", "product_no": "MK030001", "product_name": "精密零件 A", "planned_qty": 100, "remaining_qty": 100, "priority_level": 8},
        {"work_order_no": "WO-SCH-002", "product_no": "MK030005", "product_name": "精密零件 E", "planned_qty": 80, "remaining_qty": 80, "priority_level": 9},
        {"work_order_no": "WO-SCH-003", "product_no": "MK030002", "product_name": "精密零件 B", "planned_qty": 70, "remaining_qty": 70, "priority_level": 7},
        {"work_order_no": "WO-SCH-004", "product_no": "MK030003", "product_name": "精密零件 C", "planned_qty": 60, "remaining_qty": 60, "priority_level": 6},
        {"work_order_no": "WO-SCH-005", "product_no": "MK030004", "product_name": "精密零件 D", "planned_qty": 90, "remaining_qty": 90, "priority_level": 5},
    ]
    return demo

def _assumption_map() -> Dict[str, List[Dict[str, Any]]]:
    rows = assumptions()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row["product_no"], []).append(row)
    for product_no in result:
        result[product_no] = sorted(result[product_no], key=lambda x: _int(x.get("step_no")))
    return result


def run_daily_schedule(schedule_date: str | None = None, reset: bool = True, order_limit: int = 30) -> Dict[str, Any]:
    ensure_cnc_daily_schedule_schema()
    seed_process_assumptions(reset=False)

    day = _parse_day(schedule_date)
    if reset:
        execute("DELETE FROM aips_cnc_daily_schedule_result WHERE schedule_date = %s", (day,))

    process_map = _assumption_map()
    orders = _candidate_orders(order_limit)

    machine_available: Dict[str, int] = {cnc: 0 for cnc in CNC_CODES}
    machine_sequence: Dict[str, int] = {cnc: 0 for cnc in CNC_CODES}
    product_previous_end: Dict[Tuple[str, str], int] = {}
    scheduled_rows: List[Dict[str, Any]] = []
    skipped_rows: List[Dict[str, Any]] = []
    processed_order_products = set()

    for order in orders:
        product_no = order.get("product_no")
        order_product_key = (order.get("work_order_no"), product_no)
        if order_product_key in processed_order_products:
            continue
        processed_order_products.add(order_product_key)

        steps = process_map.get(product_no)

        # 若產品不在假設表，套用中性最多 3 步 CNC 假設，避免完全無法排。
        if not steps:
            steps = [
                {"product_no": product_no, "product_name": order.get("product_name") or product_no, "step_no": 1, "step_name": "CNC加工 Step1", "cnc_machine_id": "CNC-01", "processing_minutes": 60, "setup_minutes": 8},
                {"product_no": product_no, "product_name": order.get("product_name") or product_no, "step_no": 2, "step_name": "CNC加工 Step2", "cnc_machine_id": "CNC-02", "processing_minutes": 50, "setup_minutes": 6},
                {"product_no": product_no, "product_name": order.get("product_name") or product_no, "step_no": 3, "step_name": "CNC加工 Step3", "cnc_machine_id": "CNC-03", "processing_minutes": 40, "setup_minutes": 5},
            ]

        for step in steps[:3]:
            cnc = step.get("cnc_machine_id") or "CNC-01"
            if cnc not in machine_available:
                machine_available[cnc] = 0
                machine_sequence[cnc] = 0

            key = (order.get("work_order_no"), product_no)
            previous_end = product_previous_end.get(key, 0)
            processing = _int(step.get("processing_minutes"), 60)
            setup = _int(step.get("setup_minutes"), 0)
            total = processing + setup
            start_min = max(machine_available[cnc], previous_end)
            end_min = start_min + total

            status = "SCHEDULED" if end_min <= WORK_MINUTES else "OVER_CAPACITY"
            reason = "排入 8 小時日排程" if status == "SCHEDULED" else "超過 8 小時產能，列為超載但保留供檢查"

            machine_sequence[cnc] += 1
            machine_available[cnc] = end_min
            product_previous_end[key] = end_min

            schedule_id = execute_returning_id(
                """
                INSERT INTO aips_cnc_daily_schedule_result (
                    schedule_date, work_order_no, product_no, product_name,
                    step_no, step_name, cnc_machine_id, sequence_no_on_cnc,
                    planned_qty, processing_minutes, setup_minutes, total_minutes,
                    start_minute, end_minute, start_time, end_time,
                    schedule_status, schedule_reason
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING schedule_id
                """,
                (
                    day, order.get("work_order_no"), product_no, order.get("product_name") or product_no,
                    _int(step.get("step_no"), 1), step.get("step_name"), cnc, machine_sequence[cnc],
                    _num(order.get("planned_qty"), 1), processing, setup, total,
                    start_min, end_min, _dt(day, start_min), _dt(day, end_min),
                    status, reason,
                ),
                "schedule_id",
            )

            row = {
                "schedule_id": schedule_id,
                "schedule_date": str(day),
                "work_order_no": order.get("work_order_no"),
                "product_no": product_no,
                "product_name": order.get("product_name") or product_no,
                "step_no": _int(step.get("step_no"), 1),
                "step_name": step.get("step_name"),
                "cnc_machine_id": cnc,
                "sequence_no_on_cnc": machine_sequence[cnc],
                "planned_qty": _num(order.get("planned_qty"), 1),
                "processing_minutes": processing,
                "setup_minutes": setup,
                "total_minutes": total,
                "start_minute": start_min,
                "end_minute": end_min,
                "start_time": _dt(day, start_min),
                "end_time": _dt(day, end_min),
                "schedule_status": status,
                "schedule_reason": reason,
            }
            scheduled_rows.append(row)
            if status != "SCHEDULED":
                skipped_rows.append(row)

    return {
        "success": True,
        "schedule_date": str(day),
        "work_start": "08:00",
        "work_hours": 8,
        "created": len(scheduled_rows),
        "over_capacity": len(skipped_rows),
        "message": f"已產生 {day} CNC 8 小時日排程：{len(scheduled_rows)} 筆，超載 {len(skipped_rows)} 筆；同一製令 + 成品代號最多只排 3 個 CNC 加工步驟。",
        "summary_by_cnc": summary_by_cnc(str(day)),
        "schedule_rows": latest_schedule(str(day), limit=500),
    }


def latest_schedule(schedule_date: str | None = None, limit: int = 500) -> List[Dict[str, Any]]:
    ensure_cnc_daily_schedule_schema()
    day = _parse_day(schedule_date)
    return fetch_all(
        """
        SELECT
            schedule_id, schedule_date, work_order_no, product_no, product_name,
            COUNT(*) OVER (PARTITION BY work_order_no, product_no) AS product_step_count,
            step_no, step_name, cnc_machine_id, sequence_no_on_cnc,
            planned_qty, processing_minutes, setup_minutes, total_minutes,
            start_minute, end_minute,
            TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI') AS start_time_text,
            TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI') AS end_time_text,
            schedule_status, schedule_reason
        FROM aips_cnc_daily_schedule_result
        WHERE schedule_date = %s
        ORDER BY cnc_machine_id, sequence_no_on_cnc, start_minute
        LIMIT %s
        """,
        (day, limit),
    )


def summary_by_cnc(schedule_date: str | None = None) -> List[Dict[str, Any]]:
    ensure_cnc_daily_schedule_schema()
    day = _parse_day(schedule_date)
    rows = fetch_all(
        """
        SELECT
            cnc_machine_id,
            COUNT(*) AS job_count,
            COALESCE(SUM(CASE WHEN schedule_status = 'SCHEDULED' THEN total_minutes ELSE 0 END), 0) AS scheduled_minutes,
            COALESCE(SUM(total_minutes), 0) AS total_planned_minutes,
            COALESCE(SUM(CASE WHEN schedule_status <> 'SCHEDULED' THEN total_minutes ELSE 0 END), 0) AS over_capacity_minutes,
            MIN(start_minute) AS first_start_minute,
            MAX(end_minute) AS last_end_minute
        FROM aips_cnc_daily_schedule_result
        WHERE schedule_date = %s
        GROUP BY cnc_machine_id
        ORDER BY cnc_machine_id
        """,
        (day,),
    )

    result = []
    existing = {row["cnc_machine_id"]: row for row in rows}
    for cnc in CNC_CODES:
        row = existing.get(cnc, {"cnc_machine_id": cnc, "job_count": 0, "scheduled_minutes": 0, "total_planned_minutes": 0, "over_capacity_minutes": 0})
        scheduled = _num(row.get("scheduled_minutes"), 0)
        total_planned = _num(row.get("total_planned_minutes"), 0)
        over = _num(row.get("over_capacity_minutes"), 0)
        idle = max(0, WORK_MINUTES - scheduled)
        result.append({
            "cnc_machine_id": cnc,
            "job_count": _int(row.get("job_count"), 0),
            "scheduled_minutes": round(scheduled, 2),
            "scheduled_hours": round(scheduled / 60, 2),
            "idle_minutes": round(idle, 2),
            "idle_hours": round(idle / 60, 2),
            "utilization_rate": round(scheduled / WORK_MINUTES * 100, 1),
            "total_planned_minutes": round(total_planned, 2),
            "over_capacity_minutes": round(over, 2),
            "capacity_minutes": WORK_MINUTES,
            "capacity_hours": 8,
        })
    return result


def gantt_rows(schedule_date: str | None = None) -> List[Dict[str, Any]]:
    rows = latest_schedule(schedule_date, limit=500)
    result = []
    for row in rows:
        start = _num(row.get("start_minute"), 0)
        total = max(_num(row.get("total_minutes"), 1), 1)
        result.append({
            **row,
            "left_percent": round(start / WORK_MINUTES * 100, 2),
            "width_percent": round(total / WORK_MINUTES * 100, 2),
        })
    return result


def schedule_result(schedule_date: str | None = None) -> Dict[str, Any]:
    day = _parse_day(schedule_date)
    rows = latest_schedule(str(day), limit=500)
    # 第一次進頁面若沒有資料，先產生今天的排程，避免空白。
    if not rows:
        return run_daily_schedule(str(day), reset=True, order_limit=30)

    return {
        "success": True,
        "schedule_date": str(day),
        "work_start": "08:00",
        "work_hours": 8,
        "summary_by_cnc": summary_by_cnc(str(day)),
        "schedule_rows": rows,
        "gantt_rows": gantt_rows(str(day)),
        "assumptions": assumptions(),
    }
