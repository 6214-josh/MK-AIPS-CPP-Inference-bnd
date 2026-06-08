from fastapi import APIRouter, HTTPException

from app.services.cnc_daily_schedule_service import (
    assumptions,
    gantt_rows,
    latest_schedule,
    run_daily_schedule,
    schedule_result,
    seed_process_assumptions,
    summary_by_cnc,
)

router = APIRouter()


@router.post("/assumptions/seed")
def seed_assumptions(reset: bool = False):
    try:
        return seed_process_assumptions(reset=reset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"建立產品 CNC 加工順序假設資料失敗：{exc}")


@router.get("/assumptions")
def list_assumptions():
    try:
        return assumptions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢產品 CNC 加工順序假設資料失敗：{exc}")


@router.post("/run")
def run(schedule_date: str | None = None, reset: bool = True, order_limit: int = 30):
    try:
        return run_daily_schedule(schedule_date=schedule_date, reset=reset, order_limit=order_limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"產生 CNC 日排程失敗：{exc}")


@router.get("/result")
def result(schedule_date: str | None = None):
    try:
        return schedule_result(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 CNC 日排程結果失敗：{exc}")


@router.get("/summary-by-cnc")
def summary(schedule_date: str | None = None):
    try:
        return summary_by_cnc(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 CNC 排程統計失敗：{exc}")


@router.get("/schedule")
def schedule(schedule_date: str | None = None, limit: int = 500):
    try:
        return latest_schedule(schedule_date=schedule_date, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 CNC 排程明細失敗：{exc}")


@router.get("/gantt")
def gantt(schedule_date: str | None = None):
    try:
        return gantt_rows(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 CNC 排程甘特資料失敗：{exc}")
