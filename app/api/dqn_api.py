from fastapi import APIRouter
from app.core.database import fetch_all
from app.services.dqn_service import generate_actions
from app.services.gpu_inference_client import check_gpu_inference_health

from fastapi import HTTPException
from app.services.shortage_priority_dqn_service import run_shortage_priority_dqn, latest_decisions as shortage_latest_decisions, summary as shortage_summary, explain as shortage_explain
router = APIRouter()

@router.post("/generate-actions")
def generate():
    return {"created": generate_actions()}

@router.get("/actions/latest")
def latest(limit: int = 100):
    return fetch_all("SELECT * FROM aips_dqn_action_log ORDER BY action_id DESC LIMIT %s", (limit,))

@router.get("/gpu-health")
def gpu_health():
    return check_gpu_inference_health()


# FIX78：缺貨優先 DQN 相容路由
# 有些部署只覆蓋 dqn_api.py / 前端，main.py 尚未載入 shortage_priority_dqn_api 時，
# /api/aips/shortage-priority-dqn/* 會出現 404 Not found。
# 因此前端也支援呼叫 /api/aips/dqn/shortage-priority/*，這裡提供同等 API。
@router.get("/shortage-priority/summary")
def shortage_priority_summary_alias():
    try:
        return shortage_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缺貨優先 DQN 統計失敗：{exc}")


@router.get("/shortage-priority/explain")
def shortage_priority_explain_alias():
    return shortage_explain()


@router.get("/shortage-priority/decisions/latest")
def shortage_priority_decisions_latest_alias(limit: int = 100):
    try:
        return shortage_latest_decisions(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢缺貨優先 DQN 決策失敗：{exc}")


@router.post("/shortage-priority/run")
def shortage_priority_run_alias(limit: int = 12, write_action: bool = True):
    try:
        return run_shortage_priority_dqn(limit=limit, write_action=write_action)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缺貨優先 DQN 執行失敗：{exc}")
