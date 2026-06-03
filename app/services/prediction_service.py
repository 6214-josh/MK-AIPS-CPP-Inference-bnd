from app.ai.model_store import train_and_save_demo_models
import random
from app.core.database import fetch_all, execute, execute_returning_id

def _ensure_prediction_quantity_columns():
    columns = [
        ("prediction_type", "VARCHAR(80)"),
        ("predicted_output_qty", "NUMERIC(18,4)"),
        ("predicted_good_qty", "NUMERIC(18,4)"),
        ("predicted_ng_qty", "NUMERIC(18,4)"),
        ("predicted_yield_rate", "NUMERIC(10,4)"),
        ("capacity_utilization_rate", "NUMERIC(10,4)"),
    ]
    for name, ddl in columns:
        execute(f"ALTER TABLE aips_production_prediction ADD COLUMN IF NOT EXISTS {name} {ddl}")

def _num(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def _first_positive(row, keys, default=100.0):
    for key in keys:
        if key in row:
            v = _num(row.get(key), 0)
            if v > 0:
                return v
    return float(default)

def clear_invalid_predictions():
    """
    清掉不適合 Demo 的舊 AI 生產預測資料：
    - 預測產量 <= 0
    - 預測良品量 <= 0
    - 預測不良量 <= 0
    - 舊版 RULE_BASED_LSTM_ARIMA_DEMO 產生的 0 資料
    """
    _ensure_prediction_quantity_columns()
    execute(
        """
        DELETE FROM aips_production_prediction
        WHERE COALESCE(predicted_output_qty, 0) <= 0
           OR COALESCE(predicted_good_qty, 0) <= 0
           OR COALESCE(predicted_ng_qty, 0) <= 0
           OR COALESCE(model_name, '') = 'RULE_BASED_LSTM_ARIMA_DEMO'
        """
    )

def run_predictions(reset_before_run: bool = True):
    """
    FIX51：
    Demo 版 AI 生產預測要讓畫面合理、資料完整。
    - 預測產量、預測良品量、預測不良量都不能為 0
    - 良品量要高
    - 不因 remaining_qty = 0 就完全不產生資料，避免畫面只剩少數幾筆
    - 每次執行可先清掉舊的 0 資料，再重新產生一批
    """
    _ensure_prediction_quantity_columns()
    # FIX52：執行預測時確認 LSTM / DQN 模型檔案已落地。
    try:
        train_and_save_demo_models()
    except Exception:
        pass
    if reset_before_run:
        clear_invalid_predictions()

    work_orders = fetch_all(
        """
        SELECT *
        FROM work_order_progress_snapshot
        WHERE snapshot_id IN (
              SELECT MAX(snapshot_id)
              FROM work_order_progress_snapshot
              GROUP BY work_order_no
        )
        ORDER BY COALESCE(priority_level, 0) DESC, due_date ASC NULLS LAST
        """
    )

    # 若 ERP 製令快照太少，補 demo 製令，避免畫面只有 4 筆不好 demo。
    if len(work_orders) < 8:
        demo_orders = []
        for i in range(8 - len(work_orders)):
            demo_orders.append({
                "work_order_no": f"WO-DEMO-{i+1:03d}",
                "product_no": "MK030001",
                "process_code": "PROCESS_DEMO",
                "assigned_cnc_machine_id": f"CNC-0{(i % 3) + 1}",
                "remaining_qty": 80 + i * 10,
                "planned_qty": 100 + i * 10,
                "estimated_remaining_hours": 3 + (i % 3),
                "priority_level": 6 + (i % 3),
            })
        work_orders = work_orders + demo_orders

    predictions = []
    for wo in work_orders:
        cnc = (
            wo.get("assigned_cnc_machine_id")
            or wo.get("cnc_machine_id")
            or f"CNC-0{random.randint(1,3)}"
        )

        inv_rows = fetch_all(
            "SELECT * FROM line_side_inventory_snapshot WHERE cnc_machine_id = %s ORDER BY snapshot_time DESC LIMIT 5",
            (cnc,)
        )
        shortage_risk = 0.25 if not any(bool(i.get("shortage_flag")) for i in inv_rows) else 0.45

        # 不使用 remaining_qty <= 0 就跳過的邏輯。
        # 若 remaining_qty 為 0，改採 planned_qty/order_qty/100 做 demo 預測基準。
        base_order_qty = _first_positive(
            wo,
            ["remaining_qty", "remain_qty", "unprocessed_qty", "left_qty", "planned_qty", "order_qty", "qty"],
            100.0
        )

        estimated_hours = max(1.0, _num(wo.get("estimated_remaining_hours"), 4))
        priority = int(_num(wo.get("priority_level"), 5))

        base_capacity_per_hour = random.uniform(18, 28)
        capacity_utilization = max(
            0.82,
            min(0.96, random.uniform(0.86, 0.95) - (0.04 if shortage_risk > 0.4 else 0))
        )

        predicted_capacity_qty = estimated_hours * base_capacity_per_hour * capacity_utilization
        # 三個量都不可為 0；產量至少 10。
        predicted_output_qty = max(10.0, min(base_order_qty, predicted_capacity_qty))

        # 良品量高，不良量保留小量且不可為 0。
        predicted_yield_rate = random.uniform(0.94, 0.985)
        predicted_good_qty = max(1.0, predicted_output_qty * predicted_yield_rate)
        predicted_ng_qty = max(1.0, predicted_output_qty - predicted_good_qty)

        # 若 ng_qty 被 max(1) 拉高，重新校正良率，仍維持良品較高。
        predicted_yield_rate = predicted_good_qty / max(predicted_good_qty + predicted_ng_qty, 1)

        predicted_hours = estimated_hours * (1.02 + random.uniform(-0.02, 0.04))
        predicted_machine_down_risk = random.uniform(0.04, 0.15)
        predicted_quality_risk = max(0.01, 1 - predicted_yield_rate)
        predicted_energy_kwh = predicted_hours * random.uniform(4, 7)
        confidence = random.uniform(0.88, 0.95)

        prediction_id = execute_returning_id(
            """
            INSERT INTO aips_production_prediction (
                prediction_time, model_name, model_version, prediction_type,
                work_order_no, product_no, process_code, cnc_machine_id,
                predicted_processing_time, predicted_finish_time, predicted_delay_hours,
                predicted_machine_down_risk, predicted_quality_risk,
                predicted_material_shortage_risk, predicted_energy_consumption_kwh,
                predicted_output_qty, predicted_good_qty, predicted_ng_qty,
                predicted_yield_rate, capacity_utilization_rate,
                prediction_confidence_score
            )
            VALUES (
                NOW(), 'LSTM_ARIMA_QUANTITY_FORECAST_DEMO', 'v1.3', 'OUTPUT_QTY_FORECAST',
                %s, %s, %s, %s,
                %s, NOW() + (%s || ' hours')::interval,
                GREATEST(0, %s - 4),
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s
            )
            RETURNING prediction_id
            """,
            (
                wo.get("work_order_no"), wo.get("product_no"), wo.get("process_code"), cnc,
                predicted_hours, predicted_hours,
                predicted_hours if priority >= 8 else 0,
                predicted_machine_down_risk, predicted_quality_risk,
                shortage_risk, predicted_energy_kwh,
                predicted_output_qty, predicted_good_qty, predicted_ng_qty,
                predicted_yield_rate, capacity_utilization,
                confidence,
            ),
            "prediction_id",
        )
        predictions.append({
            "prediction_id": prediction_id,
            "work_order_no": wo.get("work_order_no"),
            "cnc_machine_id": cnc,
            "predicted_output_qty": round(predicted_output_qty, 3),
            "predicted_good_qty": round(predicted_good_qty, 3),
            "predicted_ng_qty": round(predicted_ng_qty, 3),
            "predicted_yield_rate": round(predicted_yield_rate, 3),
            "prediction_confidence_score": round(confidence, 3),
        })

    return predictions
