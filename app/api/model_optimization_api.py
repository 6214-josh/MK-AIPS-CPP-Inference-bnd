from fastapi import APIRouter

from app.services.model_optimization_service import (
    get_optimization_workflow,
    get_production_deployment_concerns,
)

router = APIRouter()


@router.get("/concerns")
def concerns():
    return get_production_deployment_concerns()


@router.get("/workflow")
def workflow():
    return get_optimization_workflow()
