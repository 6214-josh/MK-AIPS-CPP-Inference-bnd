from fastapi import APIRouter, HTTPException

from app.services.erp_simulator_service import (
    receive_erp_order_demo,
    process_pending_erp_orders,
    latest_erp_orders,
    erp_callbacks,
    erp_summary,
)

router = APIRouter()


@router.get("/summary")
def summary():
    try:
        return erp_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ERP 模擬器統計失敗：{exc}")


@router.post("/receive-demo")
def receive_demo(cnc_machine_id: str | None = None):
    try:
        return receive_erp_order_demo(cnc_machine_id=cnc_machine_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ERP 模擬資料接收失敗：{exc}")


@router.post("/process-pending")
def process_pending(limit: int = 20):
    try:
        return process_pending_erp_orders(limit=limit, callback_source="ERP_SIMULATOR_PAGE")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ERP 模擬資料處理回傳失敗：{exc}")


@router.get("/orders/latest")
def orders_latest(limit: int = 100, cnc_machine_id: str | None = None):
    try:
        rows = latest_erp_orders(limit=limit)
        if cnc_machine_id and cnc_machine_id != "ALL":
            rows = [row for row in rows if row.get("assigned_cnc_machine_id") == cnc_machine_id]
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ERP 模擬資料查詢失敗：{exc}")


@router.get("/callbacks/latest")
def callbacks_latest(limit: int = 100):
    try:
        return erp_callbacks(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ERP 回傳紀錄查詢失敗：{exc}")
