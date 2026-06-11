from fastapi import APIRouter, HTTPException

from app.services.cnc_dashboard_service import cnc_dashboard

router = APIRouter()


@router.get("/summary")
def summary(schedule_date: str | None = None):
    try:
        return cnc_dashboard(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CNC Dashboard 載入失敗：{exc}")
