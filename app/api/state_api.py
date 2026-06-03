from fastapi import APIRouter
from app.core.database import fetch_all
from app.core.schema_guard import ensure_extra_schema
from app.services.state_builder_service import build_states

router = APIRouter()

@router.post("/build")
def build():
    ensure_extra_schema()
    return {"created": build_states()}

@router.get("/latest")
def latest(limit: int = 100):
    ensure_extra_schema()
    return fetch_all("SELECT * FROM aips_scheduling_state ORDER BY state_id DESC LIMIT %s", (limit,))
