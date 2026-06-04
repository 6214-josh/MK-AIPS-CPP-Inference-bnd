from fastapi import APIRouter, HTTPException

from app.services.data_engineering_service import (
    seed_step1_hardware_inputs,
    run_step2_feature_engineering,
    run_full_aips_1_to_10_flow,
    source_summary,
    latest_features,
    downstream_summary,
    feedback_summary,
)

router = APIRouter()


@router.get("/sources")
def sources():
    try:
        return source_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢資料來源失敗：{exc}")


@router.post("/step1-hardware-ingest")
def step1_hardware_ingest():
    try:
        return seed_step1_hardware_inputs()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Step1 模擬硬體資料匯入失敗：{exc}")


@router.post("/step2-feature-engineering")
def step2_feature_engineering():
    try:
        return run_step2_feature_engineering()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Step2 資料工程失敗：{exc}")


@router.post("/run-full-flow")
def run_full_flow():
    try:
        return run_full_aips_1_to_10_flow()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AIPS 1-10 全流程執行失敗：{exc}")


@router.get("/features/latest")
def features_latest(limit: int = 200):
    try:
        return latest_features(limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢資料工程特徵失敗：{exc}")


@router.get("/downstream-summary")
def downstream():
    try:
        return downstream_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 downstream summary 失敗：{exc}")


@router.get("/feedback-summary")
def feedback():
    try:
        return feedback_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查詢 feedback summary 失敗：{exc}")
