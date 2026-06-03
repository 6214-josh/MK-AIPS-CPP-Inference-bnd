from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.model_optimization_service import (
    get_aips_integrated_flow,
    get_model_file_response,
    get_optimization_workflow,
    get_production_deployment_concerns,
    run_optimization_step,
)

router = APIRouter()


@router.get("/concerns")
def concerns():
    return get_production_deployment_concerns()


@router.get("/workflow")
def workflow():
    return get_optimization_workflow()


@router.get("/integrated-flow")
def integrated_flow():
    return get_aips_integrated_flow()


@router.post("/run/{step}")
def run_step(step: str):
    result = run_optimization_step(step)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"模型優化步驟執行失敗：{step}",
                "result": result,
            },
        )

    return result


@router.get("/files/{filename}")
def read_model_file(filename: str):
    try:
        path = get_model_file_response(filename)
        return FileResponse(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
