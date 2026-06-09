from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.core.database import fetch_all, fetch_one

CNC_CODES = ["CNC-01", "CNC-02", "CNC-03"]
WORK_MINUTES = 8 * 60


def _safe_fetch_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        return fetch_all(sql, params)
    except Exception:
        return []


def _safe_fetch_one(sql: str, params: tuple = ()) -> Dict[str, Any]:
    try:
        row = fetch_one(sql, params)
        return dict(row) if row else {}
    except Exception:
        return {}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _status_from_meter(row: Dict[str, Any]) -> str:
    power = _num(row.get("power_kw"), 0)
    demand = _num(row.get("demand_kw"), 0)
    thd = _num(row.get("thd_current") or row.get("thd_voltage"), 0)
    phase = _num(row.get("phase_imbalance_rate"), 0)
    if thd >= 8 or phase >= 0.18:
        return "ALARM"
    if power >= 1 or demand >= 1:
        return "RUNNING"
    return "IDLE"


def latest_meter_by_cnc() -> Dict[str, Dict[str, Any]]:
    rows = _safe_fetch_all(
        """
        WITH latest AS (
            SELECT DISTINCT ON (cnc_machine_id)
                cnc_machine_id, collect_time, power_kw, power_kwh, demand_kw,
                thd_voltage, thd_current, phase_imbalance_rate, voltage_r, voltage_s, voltage_t,
                current_r, current_s, current_t, frequency_hz
            FROM cnc_meter_raw_data
            WHERE cnc_machine_id IS NOT NULL
            ORDER BY cnc_machine_id, collect_time DESC NULLS LAST, meter_data_id DESC
        )
        SELECT * FROM latest
        """
    )
    return {row.get("cnc_machine_id"): row for row in rows if row.get("cnc_machine_id")}


def today_schedule_by_cnc(schedule_date: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
    target = schedule_date or str(date.today())
    rows = _safe_fetch_all(
        """
        SELECT
            schedule_id, schedule_date, work_order_no, product_no, product_name,
            step_no, step_name, cnc_machine_id, sequence_no_on_cnc,
            planned_qty, processing_minutes, setup_minutes, total_minutes,
            start_minute, end_minute,
            TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI') AS start_time_text,
            TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI') AS end_time_text,
            schedule_status, schedule_reason
        FROM aips_cnc_daily_schedule_result
        WHERE schedule_date = %s
        ORDER BY cnc_machine_id, sequence_no_on_cnc, start_minute
        """,
        (target,),
    )
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("cnc_machine_id"), []).append(row)
    return grouped


def summary_by_cnc(schedule_date: str | None = None) -> List[Dict[str, Any]]:
    target = schedule_date or str(date.today())
    rows = _safe_fetch_all(
        """
        SELECT
            cnc_machine_id,
            COUNT(*) AS job_count,
            COALESCE(SUM(CASE WHEN schedule_status = 'SCHEDULED' THEN total_minutes ELSE 0 END), 0) AS scheduled_minutes,
            COALESCE(SUM(total_minutes), 0) AS total_planned_minutes,
            COALESCE(SUM(CASE WHEN schedule_status <> 'SCHEDULED' THEN total_minutes ELSE 0 END), 0) AS over_capacity_minutes
        FROM aips_cnc_daily_schedule_result
        WHERE schedule_date = %s
        GROUP BY cnc_machine_id
        ORDER BY cnc_machine_id
        """,
        (target,),
    )
    by_cnc = {row.get("cnc_machine_id"): row for row in rows}
    result = []
    for cnc in CNC_CODES:
        row = by_cnc.get(cnc, {})
        scheduled = _num(row.get("scheduled_minutes"), 0)
        over = _num(row.get("over_capacity_minutes"), 0)
        result.append({
            "cnc_machine_id": cnc,
            "job_count": int(_num(row.get("job_count"), 0)),
            "scheduled_minutes": round(scheduled, 2),
            "scheduled_hours": round(scheduled / 60, 2),
            "idle_hours": round(max(0, WORK_MINUTES - scheduled) / 60, 2),
            "utilization_rate": round(scheduled / WORK_MINUTES * 100, 1),
            "over_capacity_minutes": round(over, 2),
            "over_capacity_hours": round(over / 60, 2),
            "capacity_hours": 8,
        })
    return result


def _current_job(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    scheduled = [row for row in rows if row.get("schedule_status") == "SCHEDULED"]
    if scheduled:
        return scheduled[0]
    return rows[0] if rows else None


def cnc_dashboard(schedule_date: str | None = None) -> Dict[str, Any]:
    target = schedule_date or str(date.today())
    meters = latest_meter_by_cnc()
    schedules = today_schedule_by_cnc(target)
    summaries = {row["cnc_machine_id"]: row for row in summary_by_cnc(target)}

    cards = []
    alerts = []
    for cnc in CNC_CODES:
        meter = meters.get(cnc, {})
        sched_rows = schedules.get(cnc, [])
        current_job = _current_job(sched_rows)
        summary = summaries.get(cnc, {})
        status = _status_from_meter(meter) if meter else ("SCHEDULED" if current_job else "NO_DATA")
        thd = _num(meter.get("thd_current") or meter.get("thd_voltage"), 0)
        phase = _num(meter.get("phase_imbalance_rate"), 0)
        over_hours = _num(summary.get("over_capacity_hours"), 0)
        alert_level = "NORMAL"
        alert_reason = "狀態正常"
        if status == "ALARM":
            alert_level = "HIGH"
            alert_reason = "電表 THD 或三相不平衡偏高"
        elif over_hours > 0:
            alert_level = "MEDIUM"
            alert_reason = "今日排程超過 8 小時產能"
        elif status == "NO_DATA":
            alert_level = "LOW"
            alert_reason = "目前沒有最新電表或排程資料"

        if alert_level != "NORMAL":
            alerts.append({
                "cnc_machine_id": cnc,
                "alert_level": alert_level,
                "alert_reason": alert_reason,
                "status": status,
            })

        cards.append({
            "cnc_machine_id": cnc,
            "status": status,
            "alert_level": alert_level,
            "alert_reason": alert_reason,
            "power_kw": round(_num(meter.get("power_kw"), 0), 3),
            "demand_kw": round(_num(meter.get("demand_kw"), 0), 3),
            "power_kwh": round(_num(meter.get("power_kwh"), 0), 3),
            "thd": round(thd, 3),
            "phase_imbalance_rate": round(phase, 3),
            "collect_time": str(meter.get("collect_time") or ""),
            "current_work_order_no": current_job.get("work_order_no") if current_job else "",
            "current_product_no": current_job.get("product_no") if current_job else "",
            "current_step_name": current_job.get("step_name") if current_job else "",
            "current_start_time": current_job.get("start_time_text") if current_job else "",
            "current_end_time": current_job.get("end_time_text") if current_job else "",
            "job_count": summary.get("job_count", 0),
            "scheduled_hours": summary.get("scheduled_hours", 0),
            "idle_hours": summary.get("idle_hours", 0),
            "utilization_rate": summary.get("utilization_rate", 0),
            "over_capacity_hours": summary.get("over_capacity_hours", 0),
        })

    return {
        "schedule_date": target,
        "cards": cards,
        "summary_by_cnc": list(summaries.values()),
        "alerts": alerts,
        "description": "CNC Dashboard 顯示即時設備狀態、電表狀態、目前工單與產能風險；CNC 日排程統計則用來檢查一天 8 小時排程結果。",
    }
