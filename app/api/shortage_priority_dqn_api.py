from fastapi import APIRouter, HTTPException

from app.services.shortage_priority_dqn_service import (
    run_shortage_priority_dqn,
    latest_decisions,
    summary,
    explain,
)

router = APIRouter()


@router.get("/summary")
def get_summary():
    try:
        return summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缺貨優先 DQN 統計失敗：{exc}")


@router.get("/explain")
def get_explain():
    return explain()


@router.post("/run")
def run(limit: int = 12, write_action: bool = True):
    try:
        return run_shortage_priority_dqn(limit=limit, write_action=write_action)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缺貨優先 DQN 執行失敗：{exc}")


@router.get("/decisions/latest")
def decisions_latest(limit: int = 100):
    try:
        return latest_decisions(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢缺貨優先 DQN 決策失敗：{exc}")
