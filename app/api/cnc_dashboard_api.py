from fastapi import APIRouter, HTTPException

from app.services.cnc_dashboard_service import cnc_dashboard, simulate_ai_reschedule, preview_ai_reschedule

router = APIRouter()


@router.get("/summary")
def summary(schedule_date: str | None = None):
    try:
        return cnc_dashboard(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 CNC Dashboard 失敗：{exc}")


@router.api_route("/ai-reschedule", methods=["GET", "POST"])
@router.api_route("/ai-reschedule/", methods=["GET", "POST"])
@router.api_route("/reschedule", methods=["GET", "POST"])
@router.api_route("/run", methods=["GET", "POST"])
def ai_reschedule(schedule_date: str | None = None):
    """
    AI 一鍵重排。

    同時支援 GET/POST 與 trailing slash，避免前端或代理伺服器方法/尾斜線不同造成 404 Not Found。
    """
    try:
        return simulate_ai_reschedule(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI 一鍵重排模擬失敗：{exc}")


@router.api_route("/simulate-reschedule", methods=["GET", "POST"])
def simulate_reschedule_preview(schedule_date: str | None = None):
    """重排程模擬運算：只回傳比較結果，不套用 / 不寫入 action log。"""
    try:
        return preview_ai_reschedule(schedule_date=schedule_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重排程模擬失敗：{exc}")
