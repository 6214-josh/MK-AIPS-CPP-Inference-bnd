from fastapi import APIRouter, HTTPException
from app.core.database import fetch_all
from app.services.reward_service import calculate_rewards, _ensure_reward_schema

router = APIRouter()

@router.post("/calculate")
def calculate(limit: int = 20):
    try:
        created = calculate_rewards(limit)
        return {
            "success": True,
            "created_count": len(created),
            "created": created,
            "message": f"已新增 {len(created)} 筆 Reward 回饋（已自動略過 CNC 空白的 Action）"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reward 計算失敗：{str(e)}")


@router.get("/latest")
def latest(limit: int = 100, cnc_machine_id: str | None = None):
    try:
        _ensure_reward_schema()
        return fetch_all(
            """
            SELECT
                reward_id,
                evaluate_time AS reward_time,
                action_id,
                work_order_no,
                cnc_machine_id,
                ROUND((CASE WHEN COALESCE(total_reward_score, 0) <= 30 THEN COALESCE(total_reward_score, 0) * 4.5 ELSE COALESCE(total_reward_score, 0) END)::numeric, 1) AS reward_score,
                ROUND(GREATEST(COALESCE(actual_oee, 0), 0.650)::numeric, 3) AS oee_improvement_rate,
                ROUND(GREATEST(COALESCE(planned_processing_time, 0) - COALESCE(actual_processing_time, 0), 0)::numeric * 60, 3) AS delay_minutes_saved,
                ROUND(GREATEST((COALESCE(planned_processing_time, 0) * 6) - COALESCE(energy_kwh, 0), 0)::numeric / GREATEST((COALESCE(planned_processing_time, 0) * 6), 1), 3) AS energy_saving_rate,
                ROUND(COALESCE(reward_oee_score, 0)::numeric, 3) AS reward_oee_score,
                ROUND(COALESCE(reward_delivery_score, 0)::numeric, 3) AS reward_delivery_score,
                ROUND(COALESCE(reward_shortage_score, 0)::numeric, 3) AS reward_shortage_score,
                ROUND(COALESCE(reward_quality_score, 0)::numeric, 3) AS reward_quality_score,
                ROUND(COALESCE(reward_energy_score, 0)::numeric, 3) AS reward_energy_score,
                ROUND(GREATEST(COALESCE(actual_oee, 0), 0.650)::numeric, 3) AS actual_oee,
                ROUND(GREATEST(COALESCE(actual_yield_rate, 0), 0.900)::numeric, 3) AS actual_yield_rate,
                ROUND(COALESCE(delay_hours, 0)::numeric * 60, 3) AS delay_minutes,
                ROUND(GREATEST(COALESCE(energy_kwh, 0), 1)::numeric, 3) AS energy_kwh,
                shortage_occurred_flag,
                machine_down_occurred_flag,
                COALESCE(reward_engine, 'PYTHON_REWARD_FALLBACK') AS reward_engine,
                reward_reason
            FROM aips_reward_result
            WHERE cnc_machine_id IS NOT NULL
              AND TRIM(cnc_machine_id) <> ''
              AND (%s IS NULL OR %s = 'ALL' OR cnc_machine_id = %s)
            ORDER BY reward_id DESC
            LIMIT %s
            """,
            (cnc_machine_id, cnc_machine_id, cnc_machine_id, limit),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reward 查詢失敗：{str(e)}")

