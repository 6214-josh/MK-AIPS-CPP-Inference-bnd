from app.core.database import fetch_all, fetch_one, execute_returning_id
from app.ai.arima_predictor import ArimaProcessTimePredictor
from app.ai.lstm_predictor import LstmProcessTimePredictor
from app.ai.dqn_scheduler import DqnScheduler
import json

DEFAULT_DETAILS = [
    (1, 'CNC工序01', 'CNC-STEP-01', 'CNC', 'CNC-01', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 1890, 31, 0, False, 0, 4.42, 5.25, 0.068, 2.18, 0.06),
    (2, 'CNC工序02', 'CNC-STEP-02', 'CNC', 'CNC-02', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 1980, 32, 0, False, 0, 4.64, 5.5, 0.076, 2.36, 0.07),
    (3, 'CNC工序03', 'CNC-STEP-03', 'CNC', 'CNC-03', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2070, 33, 0, False, 0, 4.86, 5.75, 0.084, 2.54, 0.08),
    (4, 'CNC工序04', 'CNC-STEP-04', 'CNC', 'CNC-04', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2160, 34, 10, False, 0, 5.08, 6.0, 0.092, 2.72, 0.09),
    (5, 'CNC工序05', 'CNC-STEP-05', 'CNC', 'CNC-05', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2250, 35, 0, True, 5, 5.3, 6.25, 0.1, 2.9, 0.1),
    (6, 'CNC工序06', 'CNC-STEP-06', 'CNC', 'CNC-06', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2340, 36, 0, False, 0, 5.52, 6.5, 0.108, 3.08, 0.11),
    (7, 'CNC工序07', 'CNC-STEP-07', 'CNC', 'CNC-07', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2430, 37, 0, False, 0, 5.74, 6.75, 0.116, 3.26, 0.12),
    (8, 'CNC工序08', 'CNC-STEP-08', 'CNC', 'CNC-08', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2520, 38, 10, False, 0, 5.96, 7.0, 0.124, 3.44, 0.13),
    (9, 'CNC工序09', 'CNC-STEP-09', 'CNC', 'CNC-09', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2610, 39, 0, False, 0, 6.18, 7.25, 0.132, 3.62, 0.14),
    (10, 'CNC工序10', 'CNC-STEP-10', 'CNC', 'CNC-10', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2700, 40, 0, True, 5, 6.4, 7.5, 0.14, 3.8, 0.15),
    (11, 'CNC工序11', 'CNC-STEP-11', 'CNC', 'CNC-11', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2790, 41, 0, False, 0, 6.62, 7.75, 0.148, 3.98, 0.16),
    (12, 'CNC工序12', 'CNC-STEP-12', 'CNC', 'CNC-12', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2880, 42, 10, False, 0, 6.84, 8.0, 0.156, 4.16, 0.17),
    (13, 'CNC工序13', 'CNC-STEP-13', 'CNC', 'CNC-13', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 2970, 43, 0, False, 0, 7.06, 8.25, 0.164, 4.34, 0.18),
    (14, 'CNC工序14', 'CNC-STEP-14', 'CNC', 'CNC-14', 100, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 3060, 44, 0, False, 0, 7.28, 8.5, 0.172, 4.52, 0.19),
]

def _num(value, default=0):
    try:
        return float(value) if value is not None else default
    except Exception:
        return default

def insert_default_details_for_header(run_card_id: int):
    existing = fetch_one("SELECT COUNT(*) AS cnt FROM aips_run_card_detail WHERE run_card_id = %s", (run_card_id,))
    if existing and int(existing["cnt"]) > 0:
        return 0
    created = 0
    for row in DEFAULT_DETAILS:
        execute_returning_id("""
            INSERT INTO aips_run_card_detail (
                run_card_id, sequence_no, station_name, station_sub_name, process_type, cnc_machine_id,
                planned_qty, control_spec_text, measurement_spec_text,
                standard_cycle_time_sec, actual_processing_minutes, delay_minutes,
                shortage_flag, shortage_qty,
                avg_power_kw, max_power_kw, avg_thd_current, energy_kwh,
                quality_risk_score, detail_status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')
            RETURNING run_card_detail_id
        """, (run_card_id, *row), "run_card_detail_id")
        created += 1
    return created

def ensure_default_details_for_all_headers():
    headers = fetch_all("""
        SELECT h.run_card_id
        FROM aips_run_card_header h
        LEFT JOIN aips_run_card_detail d ON h.run_card_id = d.run_card_id
        GROUP BY h.run_card_id
        HAVING COUNT(d.run_card_detail_id) = 0
        ORDER BY h.run_card_id
        LIMIT 100
    """)
    created = 0
    for h in headers:
        created += insert_default_details_for_header(h["run_card_id"])
    return {"success": True, "created_detail_count": created}

def _load_detail_rows(limit=500):
    return fetch_all("""
        SELECT
            h.run_card_id,
            h.work_order_no,
            h.product_no,
            h.due_date,
            h.priority_level,
            d.run_card_detail_id,
            d.sequence_no,
            d.station_name,
            d.cnc_machine_id,
            d.standard_cycle_time_sec,
            d.actual_processing_minutes,
            d.delay_minutes,
            d.shortage_flag,
            d.shortage_qty,
            d.avg_power_kw,
            d.avg_thd_current,
            d.quality_risk_score
        FROM aips_run_card_header h
        JOIN aips_run_card_detail d ON h.run_card_id = d.run_card_id
        ORDER BY h.run_card_id, d.sequence_no
        LIMIT %s
    """, (limit,))

def generate_run_card_ai_features():
    auto = ensure_default_details_for_all_headers()
    all_rows = _load_detail_rows(1000)

    pending_rows = [r for r in all_rows if not fetch_one(
        "SELECT 1 FROM aips_run_card_ai_feature WHERE run_card_detail_id = %s LIMIT 1",
        (r["run_card_detail_id"],)
    )]

    arima = ArimaProcessTimePredictor()
    lstm = LstmProcessTimePredictor()

    created = 0
    for row in pending_rows:
        same_station_series = [
            _num(r.get("actual_processing_minutes"))
            for r in all_rows
            if r.get("station_name") == row.get("station_name") and _num(r.get("actual_processing_minutes")) > 0
        ]
        arima_pred = arima.predict_next_minutes(same_station_series)

        same_station_features = [
            dict(r) for r in all_rows
            if r.get("station_name") == row.get("station_name")
        ]
        lstm_pred = lstm.predict_next_minutes(same_station_features)

        delay = _num(row.get("delay_minutes"))
        shortage_risk = 0.9 if row.get("shortage_flag") else 0.1
        quality_risk = _num(row.get("quality_risk_score"), 0.1)
        thd = _num(row.get("avg_thd_current"))
        power_risk = 0.8 if thd >= 15 else 0.2 if thd else 0.1
        delay_risk = min(1.0, round((delay / 60.0) + shortage_risk * 0.4 + quality_risk * 0.3 + power_risk * 0.2, 4))

        state = {
            "algorithm": {
                "arima_mode": arima.last_mode,
                "lstm_mode": lstm.last_mode,
                "dqn_ready": True,
            },
            "work_order_no": row.get("work_order_no"),
            "product_no": row.get("product_no"),
            "station_name": row.get("station_name"),
            "cnc_machine_id": row.get("cnc_machine_id"),
            "sequence_no": row.get("sequence_no"),
            "arima_predicted_minutes": arima_pred,
            "lstm_predicted_minutes": lstm_pred,
            "delay_risk_score": delay_risk,
            "shortage_risk_score": shortage_risk,
            "quality_risk_score": quality_risk,
            "power_risk_score": power_risk,
        }

        execute_returning_id("""
            INSERT INTO aips_run_card_ai_feature (
                run_card_id, run_card_detail_id, work_order_no, product_no,
                station_name, cnc_machine_id, sequence_no,
                actual_processing_minutes, moving_avg_processing_minutes,
                arima_predicted_minutes, lstm_predicted_minutes,
                predicted_finish_time, delay_risk_score, shortage_risk_score,
                quality_risk_score, power_risk_score, dqn_state_json
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                NOW() + (%s || ' minutes')::interval, %s, %s,
                %s, %s, %s::jsonb
            )
            RETURNING feature_id
        """, (
            row.get("run_card_id"), row.get("run_card_detail_id"), row.get("work_order_no"), row.get("product_no"),
            row.get("station_name"), row.get("cnc_machine_id"), row.get("sequence_no"),
            _num(row.get("actual_processing_minutes")), _num(row.get("actual_processing_minutes")),
            arima_pred, lstm_pred,
            lstm_pred, delay_risk, shortage_risk,
            quality_risk, power_risk, json.dumps(state, ensure_ascii=False)
        ), "feature_id")
        created += 1

    return {
        "success": True,
        "created": created,
        "auto_created_detail_count": auto.get("created_detail_count", 0),
        "algorithm": {
            "arima": "statsmodels ARIMA if enough data, fallback moving average if not",
            "lstm": "PyTorch torch.nn.LSTM if enough data, fallback weighted average if not",
        },
        "message": f"已自動補單身 {auto.get('created_detail_count', 0)} 筆，並產生真 AI 架構特徵 {created} 筆"
    }

def generate_dqn_suggestion():
    feature_result = generate_run_card_ai_features()

    features = fetch_all("""
        SELECT *
        FROM aips_run_card_ai_feature
        ORDER BY feature_id DESC
        LIMIT 80
    """)

    dqn = DqnScheduler()
    results = dqn.choose_action([dict(f) for f in features[:30]])

    suggestions = []
    for item in results:
        f = item["feature"]
        action_type = item["action_type"]
        action_name = item["action_name"]
        reason = item["reason"]
        confidence = item["confidence"]

        action_id = execute_returning_id("""
            INSERT INTO aips_dqn_action_log (
                state_id, action_type, action_name, work_order_no, product_no,
                original_cnc_machine_id, suggested_cnc_machine_id,
                expected_delay_reduction_hours, expected_oee_improvement_rate,
                expected_shortage_risk_reduction, action_confidence_score,
                action_status, action_reason
            )
            VALUES (
                NULL, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                'PENDING', %s
            )
            RETURNING action_id
        """, (
            action_type, action_name, f.get("work_order_no"), f.get("product_no"),
            f.get("cnc_machine_id"), f.get("cnc_machine_id"),
            round(_num(f.get("delay_risk_score")) * 2, 2),
            round((1 - _num(f.get("delay_risk_score"))) * 0.1, 4),
            round(_num(f.get("shortage_risk_score")) * 0.8, 4),
            confidence,
            reason + f"｜DQN 模式：{dqn.last_mode}｜Q={json.dumps(item.get('q_values'), ensure_ascii=False)}"
        ), "action_id")

        suggestions.append({
            "action_id": action_id,
            "work_order_no": f.get("work_order_no"),
            "station_name": f.get("station_name"),
            "cnc_machine_id": f.get("cnc_machine_id"),
            "action_type": action_type,
            "action_name": action_name,
            "reason": reason,
            "q_values": item.get("q_values"),
            "dqn_mode": dqn.last_mode,
            "confidence": confidence,
        })

    created = len(suggestions)

    return {
        "success": True,
        "created": created,
        "created_count": created,
        "feature_created": feature_result.get("created", 0),
        "auto_created_detail_count": feature_result.get("auto_created_detail_count", 0),
        "feature_result": feature_result,
        "dqn_mode": dqn.last_mode,
        "suggestions": suggestions,
        "message": (
            f"已處理 AI 特徵，新增 {created} 筆 DQN 建議"
            f"（本次新增 AI 特徵 {feature_result.get('created', 0)} 筆，"
            f"自動補單身 {feature_result.get('auto_created_detail_count', 0)} 筆）"
        )
    }
