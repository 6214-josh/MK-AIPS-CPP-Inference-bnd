from fastapi import APIRouter
from app.core.database import fetch_all
from app.services.dqn_service import generate_actions
from app.services.gpu_inference_client import check_gpu_inference_health

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
