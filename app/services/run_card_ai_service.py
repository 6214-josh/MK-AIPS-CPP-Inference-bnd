from app.core.database import fetch_all, fetch_one, execute_returning_id
from app.ai.arima_predictor import ArimaProcessTimePredictor
from app.ai.lstm_predictor import LstmProcessTimePredictor
from app.ai.dqn_scheduler import DqnScheduler
import json

DEFAULT_DETAILS = [
    (1, '磨床', None, 'GRINDING', 'GRIND-01', 100, '厚度 111(+0.01/0)', '人工量測', 3600, 60, 0, False, 0, 4.2, 4.8, 5.2, 1.5, 0.10),
    (2, 'CNC銑床', 'O3391', 'CNC', 'CNC-01', 100, 'G1F-01 / G1H-01 / G1H-02', '機台自動帶入量測值', 2700, 45, 0, False, 0, 6.2, 7.0, 7.5, 4.6, 0.12),
    (3, 'CNC銑床', 'O3392', 'CNC', 'CNC-02', 100, 'G4F-02 / G4F-03', '機台自動帶入量測值', 3300, 55, 15, True, 15, 3.1, 3.6, 8.1, 3.1, 0.20),
    (4, '手工處理', None, 'MANUAL', None, 100, '去毛邊 / 外觀處理', '人工確認', 1800, 30, 0, False, 0, None, None, None, None, 0.08),
    (5, '拋光', None, 'POLISH', None, 100, '第一段 / 第二段 / 轉速', '人工確認', 2400, 40, 0, False, 0, None, None, None, None, 0.10),
    (6, '成品檢驗', None, 'QC', None, 100, '外觀 / 三次元', 'QC 量測', 3000, 50, 0, False, 0, None, None, None, None, 0.15),
    (7, '清洗包裝', None, 'CLEAN_PACK', None, 100, '純水 / 超音波 / 烘乾', '人工確認', 2100, 35, 0, False, 0, None, None, None, None, 0.05),
    (8, '成品入庫', None, 'WAREHOUSE', None, 100, '成品入庫', '入庫確認', 1200, 20, 0, False, 0, None, None, None, None, 0.03),
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

    return {
        "success": True,
        "feature_result": feature_result,
        "dqn_mode": dqn.last_mode,
        "suggestions": suggestions
    }
