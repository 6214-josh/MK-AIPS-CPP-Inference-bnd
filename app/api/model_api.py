from fastapi import APIRouter, HTTPException
from app.ai.model_store import get_model_status, train_and_save_demo_models

router = APIRouter()

@router.get("/status")
def status():
    return get_model_status()

@router.post("/train-demo")
def train_demo():
    try:
        return train_and_save_demo_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型檔案產生失敗：{str(e)}")
