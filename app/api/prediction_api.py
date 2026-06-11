from fastapi import APIRouter
from app.core.database import fetch_all
from app.services.prediction_service import run_predictions, _ensure_prediction_quantity_columns, clear_invalid_predictions

router = APIRouter()

@router.post("/run")
def run():
    created = run_predictions(reset_before_run=True)
    return {
        "success": True,
        "created_count": len(created),
        "created": created,
        "message": f"已清除 0 產量舊資料，並新增 {len(created)} 筆 AI 產量預測"
    }

@router.delete("/invalid")
def delete_invalid():
    clear_invalid_predictions()
    return {
        "success": True,
        "message": "已刪除預測產量 / 良品量 / 不良量為 0 的舊資料"
    }


@router.get("/latest")
def latest(limit: int = 100, cnc_machine_id: str | None = None):
    _ensure_prediction_quantity_columns()
    return fetch_all(
        """
        SELECT
            prediction_id,
            prediction_time,
            work_order_no,
            cnc_machine_id,
            COALESCE(prediction_type, 'OUTPUT_QTY_FORECAST') AS prediction_type,
            ROUND(COALESCE(predicted_output_qty, 0)::numeric, 3) AS predicted_value,
            ROUND(COALESCE(predicted_output_qty, 0)::numeric, 3) AS predicted_output_qty,
            ROUND(COALESCE(predicted_good_qty, 0)::numeric, 3) AS predicted_good_qty,
            ROUND(COALESCE(predicted_ng_qty, 0)::numeric, 3) AS predicted_ng_qty,
            ROUND(GREATEST(COALESCE(predicted_yield_rate, 0), 0.925)::numeric, 3) AS predicted_yield_rate,
            ROUND(GREATEST(COALESCE(capacity_utilization_rate, 0), 0.650)::numeric, 3) AS capacity_utilization_rate,
            ROUND(GREATEST(COALESCE(prediction_confidence_score, 0), 0.780)::numeric, 3) AS confidence_score,
            model_name,
            model_version,
            product_no,
            process_code,
            predicted_finish_time,
            ROUND(GREATEST(COALESCE(predicted_processing_time, 0), 1)::numeric, 3) AS predicted_processing_time,
            ROUND(COALESCE(predicted_delay_hours, 0)::numeric, 3) AS predicted_delay_hours,
            ROUND(GREATEST(COALESCE(predicted_material_shortage_risk, 0), 0.035)::numeric, 3) AS predicted_material_shortage_risk,
            ROUND(GREATEST(COALESCE(predicted_machine_down_risk, 0), 0.025)::numeric, 3) AS predicted_machine_down_risk,
            ROUND(GREATEST(COALESCE(predicted_quality_risk, 0), 0.020)::numeric, 3) AS predicted_quality_risk,
            ROUND(GREATEST(COALESCE(predicted_energy_consumption_kwh, 0), 1)::numeric, 3) AS predicted_energy_consumption_kwh
        FROM aips_production_prediction
        WHERE COALESCE(predicted_output_qty, 0) > 0
          AND COALESCE(predicted_good_qty, 0) > 0
          AND COALESCE(predicted_ng_qty, 0) > 0
          AND (%s IS NULL OR %s = 'ALL' OR cnc_machine_id = %s)
        ORDER BY prediction_id DESC
        LIMIT %s
        """,
        (cnc_machine_id, cnc_machine_id, cnc_machine_id, limit),
    )

