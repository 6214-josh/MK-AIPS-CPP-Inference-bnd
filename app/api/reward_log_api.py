from fastapi import APIRouter, HTTPException

from app.services.reward_log_service import (
    ensure_reward_log_schema,
    latest_reward_logs,
    reward_log_dashboard,
    sync_reward_log_from_reward_result,
)

router = APIRouter()


@router.post("/sync")
def sync(limit: int = 120):
    try:
        return sync_reward_log_from_reward_result(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reward Log 同步失敗：{exc}")


@router.get("/latest")
def latest(limit: int = 120):
    try:
        return latest_reward_logs(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reward Log 查詢失敗：{exc}")


@router.get("/dashboard")
def dashboard(limit: int = 120):
    try:
        return reward_log_dashboard(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reward Log Dashboard 查詢失敗：{exc}")


@router.post("/ensure-schema")
def ensure_schema():
    try:
        ensure_reward_log_schema()
        return {"success": True, "message": "aips_dqn_reward_log schema ready"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reward Log Schema 建立失敗：{exc}")
