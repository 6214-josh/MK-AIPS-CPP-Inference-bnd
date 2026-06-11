from fastapi import APIRouter

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
        return {"success": False, "created": 0, "source_count": 0, "error": f"Reward Log 同步失敗：{exc}"}


@router.get("/latest")
def latest(limit: int = 120):
    try:
        return latest_reward_logs(limit=limit)
    except Exception as exc:
        return [{"reward_log_id": 0, "error": f"Reward Log 查詢失敗：{exc}"}]


@router.get("/dashboard")
def dashboard(limit: int = 120):
    return reward_log_dashboard(limit=limit)


@router.post("/ensure-schema")
def ensure_schema():
    try:
        ensure_reward_log_schema()
        return {"success": True, "message": "aips_dqn_reward_log schema ready"}
    except Exception as exc:
        return {"success": False, "error": f"Reward Log Schema 建立失敗：{exc}"}
