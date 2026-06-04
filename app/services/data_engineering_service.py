from __future__ import annotations

import json
import random
from typing import Any, Dict, List

from app.core.database import fetch_all, fetch_one, execute, execute_returning_id
from app.core.schema_guard import ensure_extra_schema
from app.services.feature_engineering_service import calculate_meter_features
from app.services.state_builder_service import build_states
from app.services.prediction_service import run_predictions
from app.services.run_card_ai_service import generate_run_card_ai_features, generate_dqn_suggestion
from app.services.reward_service import calculate_rewards
from app.services.erp_simulator_service import receive_erp_order_demo, process_pending_erp_orders


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


def _norm(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return round(max(0.0, min(1.0, value / max_value)), 6)


def _count(table: str) -> int:
    row = fetch_one(f"SELECT COUNT(*) AS cnt FROM {table}")
    return int(row["cnt"]) if row else 0


def _latest_created_at(table: str):
    try:
        row = fetch_one(f"SELECT created_at FROM {table} ORDER BY created_at DESC NULLS LAST LIMIT 1")
        return row.get("created_at") if row else None
    except Exception:
        return None





def _sanitize_legacy_non_cnc_rows() -> None:
    """
    FIX72：
    現場目前只有 CNC，沒有磨床，也不要讓 CNC 欄位空白。
    將舊 demo 遺留的 GRIND / 磨床 / 空白 CNC 轉為 CNC-01~03，避免表格再出現 GRIND-01 或空白。
    """
    execute("""
        UPDATE aips_run_card_detail
        SET
            station_name = CASE
                WHEN station_name = '磨床' THEN 'CNC銑床'
                WHEN COALESCE(station_name, '') = '' THEN 'CNC加工'
                ELSE station_name
            END,
            station_sub_name = COALESCE(station_sub_name, 'CNC-AUTO'),
            process_type = 'CNC',
            cnc_machine_id = CASE
                WHEN cnc_machine_id IS NULL OR cnc_machine_id = '' OR cnc_machine_id LIKE 'GRIND%%' THEN
                    CASE MOD(run_card_detail_id, 3)
                        WHEN 0 THEN 'CNC-01'
                        WHEN 1 THEN 'CNC-02'
                        ELSE 'CNC-03'
                    END
                ELSE cnc_machine_id
            END,
            avg_power_kw = COALESCE(avg_power_kw, 4.8),
            avg_thd_current = COALESCE(avg_thd_current, 5.8)
        WHERE COALESCE(process_type, '') <> 'CNC'
           OR COALESCE(station_name, '') = '磨床'
           OR COALESCE(cnc_machine_id, '') = ''
           OR cnc_machine_id LIKE 'GRIND%%'
    """)

    execute("""
        UPDATE aips_dqn_action_log
        SET
            original_cnc_machine_id = CASE
                WHEN original_cnc_machine_id IS NULL OR original_cnc_machine_id = '' OR original_cnc_machine_id LIKE 'GRIND%%' THEN 'CNC-01'
                ELSE original_cnc_machine_id
            END,
            suggested_cnc_machine_id = CASE
                WHEN suggested_cnc_machine_id IS NULL OR suggested_cnc_machine_id = '' OR suggested_cnc_machine_id LIKE 'GRIND%%' THEN
                    CASE
                        WHEN original_cnc_machine_id IN ('CNC-02','CNC-03') THEN original_cnc_machine_id
                        ELSE 'CNC-01'
                    END
                ELSE suggested_cnc_machine_id
            END
        WHERE COALESCE(original_cnc_machine_id, '') = ''
           OR COALESCE(suggested_cnc_machine_id, '') = ''
           OR original_cnc_machine_id LIKE 'GRIND%%'
           OR suggested_cnc_machine_id LIKE 'GRIND%%'
    """)

    execute("""
        UPDATE aips_reward_result
        SET cnc_machine_id = CASE
            WHEN cnc_machine_id IS NULL OR cnc_machine_id = '' OR cnc_machine_id LIKE 'GRIND%%' THEN 'CNC-01'
            ELSE cnc_machine_id
        END
        WHERE COALESCE(cnc_machine_id, '') = ''
           OR cnc_machine_id LIKE 'GRIND%%'
    """)


def _create_demo_run_card_for_flow() -> Dict[str, Any]:
    """
    FIX69/FIX70：
    AIPS 1-10 全流程每次執行都補一張新的 MES 製令流程卡。
    FIX70 另外回傳 run_card_no / work_order_no，讓前端能直接聚焦「本次執行」資料。
    """
    epoch_row = fetch_one("SELECT EXTRACT(EPOCH FROM NOW())::bigint AS epoch_no")
    epoch_no = str(epoch_row.get("epoch_no") if epoch_row else "")
    run_card_no = f"MK-FLOW-{epoch_no}"
    work_order_no = f"WO-FLOW-{epoch_no}"

    run_card_id = execute_returning_id("""
        INSERT INTO aips_run_card_header (
            run_card_no, production_batch_no, work_order_no, sales_order_no, customer_name,
            product_no, material_no, piece_id, serial_no, process_name, process_level, unit,
            size_length, size_width, planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
            due_date, priority_level, run_card_status, source_system, source_file_name, created_by
        )
        VALUES (
            %s,
            'MK20260111003',
            %s,
            'SO-AIPS-FLOW',
            'UMC',
            'MK030001',
            '3D10-260318-11',
            'A123-456-789',
            '20260401 ZH-260318',
            'CNC 加工',
            '低階',
            'mm',
            130, 130, 100, 0, 0, 0, 100,
            NOW() + INTERVAL '24 hours',
            8,
            'OPEN',
            'AIPS_1_TO_10_FLOW',
            'AIPS 1-10 全流程自動建立',
            'admin'
        )
        RETURNING run_card_id
    """, (run_card_no, work_order_no), "run_card_id")

    demo_details = [
        (1, 'CNC加工', 'CNC-STEP-01', 'CNC', 'CNC-01', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 45, 0, False, 0, 6.2, 7.5, 0.12, 'PENDING'),
        (2, 'CNC加工', 'CNC-STEP-02', 'CNC', 'CNC-02', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 55, 15, True, 15, 3.1, 8.1, 0.20, 'PENDING'),
        (3, 'CNC加工', 'CNC-STEP-03', 'CNC', 'CNC-03', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 50, 5, False, 0, 5.8, 6.9, 0.11, 'PENDING'),
        (4, 'CNC加工', 'CNC-STEP-04', 'CNC', 'CNC-01', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 42, 0, False, 0, 5.5, 6.6, 0.10, 'PENDING'),
        (5, 'CNC加工', 'CNC-STEP-05', 'CNC', 'CNC-02', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 48, 0, False, 0, 4.9, 6.1, 0.09, 'PENDING'),
        (6, 'CNC加工', 'CNC-STEP-06', 'CNC', 'CNC-03', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 36, 0, False, 0, 4.7, 5.8, 0.08, 'PENDING'),
        (7, 'CNC加工', 'CNC-STEP-07', 'CNC', 'CNC-01', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 30, 0, False, 0, 3.8, 5.0, 0.06, 'PENDING'),
        (8, 'CNC加工', 'CNC-STEP-08', 'CNC', 'CNC-02', 100, 0, 'CNC 製程參數檢查', 'CNC 自動量測回傳', 25, 0, False, 0, 3.5, 4.8, 0.05, 'PENDING'),
    ]

    detail_count = 0
    for d in demo_details:
        execute_returning_id("""
            INSERT INTO aips_run_card_detail (
                run_card_id, sequence_no, station_name, station_sub_name, process_type,
                cnc_machine_id, planned_qty, completed_qty, control_spec_text, measurement_spec_text,
                standard_cycle_time_sec, delay_minutes, shortage_flag, shortage_qty,
                avg_power_kw, avg_thd_current, quality_risk_score, detail_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING run_card_detail_id
        """, (run_card_id, *d), "run_card_detail_id")
        detail_count += 1

    return {
        "run_card_id": run_card_id,
        "run_card_no": run_card_no,
        "work_order_no": work_order_no,
        "detail_count": detail_count,
        "message": f"已建立 AIPS 1-10 流程卡 {run_card_no} / {work_order_no}，單身 {detail_count} 筆",
    }


def _insert_engineering_feature(
    *,
    category: str,
    source_table: str,
    source_pk: Any,
    feature_name: str,
    raw_value: Any,
    cleaned_value: Any,
    normalized_value: float,
    time_bucket: str,
    downstream_stage: str,
    cnc_machine_id: str | None = None,
    work_order_no: str | None = None,
    material_no: str | None = None,
    vector: Dict[str, Any] | None = None,
    engineering_step: str = "STEP2_FEATURE_ENGINEERING",
) -> int:
    return execute_returning_id(
        """
        INSERT INTO aips_data_engineering_feature (
            feature_time, feature_category, source_table, source_pk,
            cnc_machine_id, work_order_no, material_no,
            feature_name, raw_value, cleaned_value, normalized_value,
            time_bucket, feature_vector_json, engineering_step,
            downstream_stage, created_at
        )
        VALUES (
            NOW(), %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s::jsonb, %s,
            %s, NOW()
        )
        RETURNING data_feature_id
        """,
        (
            category, source_table, str(source_pk) if source_pk is not None else None,
            cnc_machine_id, work_order_no, material_no,
            feature_name, str(raw_value) if raw_value is not None else None,
            str(cleaned_value) if cleaned_value is not None else None,
            normalized_value, time_bucket, json.dumps(vector or {}, ensure_ascii=False),
            engineering_step, downstream_stage,
        ),
        "data_feature_id",
    )


def source_summary() -> List[Dict[str, Any]]:
    ensure_extra_schema()
    tables = [
        ("aips_sim_cnc_smart_meter", "Step1 模擬 CNC 智慧電表設備"),
        ("cnc_meter_raw_data", "Step1 智慧電表原始資料"),
        ("aips_scan_event", "Step1 PDA / NFC / QR Code 掃描事件"),
        ("aips_sim_line_side_logistics", "Step1 線邊庫人工物流事件"),
        ("line_side_inventory_snapshot", "Step1 WMS 線邊庫庫存"),
        ("work_order_progress_snapshot", "Step1 ERP 製令進度"),
        ("aips_run_card_detail", "Step1 MES 製令流程卡單身"),
        ("cnc_meter_feature", "Step2 智慧電表特徵"),
        ("aips_data_engineering_feature", "Step2 資料工程特徵池"),
        ("aips_production_prediction", "Step3/4 LSTM / ARIMA 預測"),
        ("aips_scheduling_state", "Step5/6 Fusion + DQN State"),
        ("aips_dqn_action_log", "Step7/8 DQN Q-Network + Action"),
        ("aips_reward_result", "Step10 Reward 回饋"),
    ]
    rows = []
    for table, description in tables:
        try:
            rows.append({
                "source_table": table,
                "description": description,
                "record_count": _count(table),
                "latest_created_at": _latest_created_at(table),
            })
        except Exception as exc:
            rows.append({
                "source_table": table,
                "description": description,
                "record_count": 0,
                "latest_created_at": None,
                "error": str(exc),
            })
    return rows


def seed_step1_hardware_inputs() -> Dict[str, Any]:
    """
    Step1：從模擬硬體抓出資料。
    寫入：CNC 智慧電表 raw、PDA/NFC scan、線邊庫物流、WMS snapshot、ERP work order。
    這些會回饋到 Step2 資料工程。
    """
    ensure_extra_schema()

    erp_received = receive_erp_order_demo(source="AIPS_STEP1_HARDWARE_SOFTWARE_SIMULATOR")

    meters = fetch_all("SELECT * FROM aips_sim_cnc_smart_meter ORDER BY cnc_machine_id LIMIT 10")
    if not meters:
        for idx in range(1, 4):
            execute(
                """
                INSERT INTO aips_sim_cnc_smart_meter (
                    cnc_machine_id, meter_id, device_ip, protocol_type, modbus_unit_id, mqtt_topic,
                    voltage_v, current_a, power_kw, demand_kw, thd_current,
                    machine_status, online_flag, last_collect_time
                )
                VALUES (%s, %s, %s, 'MODBUS_TCP', %s, %s, 220, %s, %s, %s, %s, 'RUNNING', TRUE, NOW())
                """,
                (
                    f"CNC-0{idx}", f"METER-CNC-0{idx}", f"192.168.1.20{idx}", idx,
                    f"AIPS/CNC/CNC-0{idx}/METER", 10 + idx, 4 + idx, 5 + idx, 3 + idx,
                ),
            )
        meters = fetch_all("SELECT * FROM aips_sim_cnc_smart_meter ORDER BY cnc_machine_id LIMIT 10")

    raw_created = 0
    meter_feature_created = 0
    for meter in meters:
        cnc = meter.get("cnc_machine_id")
        power = max(0.5, _num(meter.get("power_kw"), 5) + random.uniform(-0.5, 0.8))
        current = max(0.5, _num(meter.get("current_a"), 10) + random.uniform(-1.0, 1.0))
        thd = max(0.2, _num(meter.get("thd_current"), 4) + random.uniform(-0.4, 0.6))
        meter_data_id = execute_returning_id(
            """
            INSERT INTO cnc_meter_raw_data (
                meter_id, cnc_machine_id, device_ip, mqtt_topic, collect_time,
                voltage_r, voltage_s, voltage_t,
                current_r, current_s, current_t,
                power_kw, power_kwh, power_factor, frequency_hz,
                demand_kw, thd_voltage, thd_current, phase_imbalance_rate, raw_payload
            )
            VALUES (
                %s, %s, %s, %s, NOW(),
                220, 220, 220,
                %s, %s, %s,
                %s, 1000 + EXTRACT(EPOCH FROM NOW()) / 3600, 0.92, 60,
                %s, 2.5, %s, 1.2,
                jsonb_build_object('source','hardware_simulator','step','STEP1','feedback_loop','STEP10_TO_STEP1_TO_STEP2')
            )
            RETURNING meter_data_id
            """,
            (meter.get("meter_id"), cnc, meter.get("device_ip"), meter.get("mqtt_topic"), current, current, current, power, power, thd),
            "meter_data_id",
        )
        raw_created += 1
        feature = calculate_meter_features(cnc)
        if feature:
            meter_feature_created += 1
        execute(
            """
            INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
            VALUES ('MODBUS', 'CNC_METER_DATA', 'INFO', %s,
                    jsonb_build_object('cnc_machine_id', %s, 'meter_data_id', %s, 'power_kw', %s, 'thd_current', %s),
                    'PROCESSED')
            """,
            (meter.get("mqtt_topic"), cnc, meter_data_id, power, thd),
        )

    scan_event_id = execute_returning_id(
        """
        INSERT INTO aips_scan_event (
            scan_time, scan_type, scan_code, operator_id,
            work_order_no, material_no, cnc_machine_id,
            event_status, event_message
        )
        VALUES (
            NOW(), 'PDA_NFC_QRCODE', 'QR-WO-202606-001', 'operator01',
            'WO-202606-001', 'MAT-AL-6061', 'CNC-01',
            'SUCCESS', 'Step1 模擬 PDA / NFC / QR Code 掃描，提供 Step2 資料工程使用'
        )
        RETURNING scan_event_id
        """,
        (),
        "scan_event_id",
    )

    logistics_id = execute_returning_id(
        """
        INSERT INTO aips_sim_line_side_logistics (
            event_time, cart_code, operator_id, work_order_no, material_no,
            from_location, to_location, logistics_action, qty, event_status
        )
        VALUES (
            NOW(), 'CART-001', 'operator01', 'WO-202606-001', 'MAT-AL-6061',
            '倉庫-A', 'LS-CNC-01', 'REPLENISH', 30, 'DONE'
        )
        RETURNING logistics_id
        """,
        (),
        "logistics_id",
    )

    inventory_snapshot_id = execute_returning_id(
        """
        INSERT INTO line_side_inventory_snapshot (
            snapshot_time, cnc_machine_id, line_side_location_id,
            material_no, material_name, lot_no,
            current_qty, reserved_qty, available_qty, safety_stock_qty,
            shortage_flag, shortage_qty, replenishment_required_flag,
            last_scan_time, source_system
        )
        VALUES (
            NOW(), 'CNC-01', 'LS-CNC-01',
            'MAT-AL-6061', '鋁材 6061', 'LOT-A1',
            80, 20, 60, 30,
            FALSE, 0, FALSE,
            NOW(), 'HARDWARE_SIMULATOR'
        )
        RETURNING snapshot_id
        """,
        (),
        "snapshot_id",
    )

    # 若 ERP 製令不足，補 demo 製令，確保 Step3~10 可跑。
    if _count("work_order_progress_snapshot") < 5:
        for idx in range(1, 6):
            execute(
                """
                INSERT INTO work_order_progress_snapshot (
                    snapshot_time, work_order_no, sales_order_no, customer_id,
                    product_no, product_name, process_code,
                    planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
                    due_date, priority_level, current_process_status,
                    assigned_cnc_machine_id, estimated_remaining_hours, delay_risk_flag
                )
                VALUES (
                    NOW(), %s, %s, 'CUS-DEMO',
                    'MK030001', 'CNC 零件 DEMO', 'CNC',
                    %s, %s, %s, 1, %s,
                    NOW() + (%s || ' hours')::interval, %s, 'RUNNING',
                    %s, %s, FALSE
                )
                """,
                (
                    f"WO-202606-00{idx}", f"SO-202606-00{idx}",
                    100 + idx * 10, idx * 5, idx * 5, 100 + idx * 10 - idx * 5,
                    24 + idx * 4, 5 + idx, f"CNC-0{((idx - 1) % 3) + 1}", 4 + idx,
                ),
            )

    return {
        "erp_received": erp_received,
        "raw_meter_created": raw_created,
        "meter_feature_created": meter_feature_created,
        "scan_event_id": scan_event_id,
        "logistics_id": logistics_id,
        "inventory_snapshot_id": inventory_snapshot_id,
        "message": f"Step1 已從軟硬體模擬器產生資料，ERP 新製令 {erp_received.get('work_order_no')} 已接收，下一步可進 Step2 資料工程。",
    }


def run_step2_feature_engineering() -> Dict[str, Any]:
    """
    Step2：資料工程，將 Step1 資料清洗、標準化、正規化、形成特徵池。
    特徵池會往後塞給 Step3~10，也接收 Step10 Reward 回饋後再流回 Step1/2。
    """
    ensure_extra_schema()
    created_ids: list[int] = []

    # CNC meter feature -> Step3 LSTM / Step6 DQN State
    meter_features = fetch_all("SELECT * FROM cnc_meter_feature ORDER BY feature_id DESC LIMIT 200")
    for row in meter_features:
        power = _num(row.get("avg_power_kw_5min"))
        thd = _num(row.get("thd_current_avg"))
        vector = {
            "cnc_machine_id": row.get("cnc_machine_id"),
            "avg_power_kw_5min": power,
            "thd_current_avg": thd,
            "energy_kwh_1hr": _num(row.get("energy_kwh_1hr")),
            "machine_status": row.get("estimated_machine_status"),
            "machine_abnormal_power_flag": bool(row.get("machine_abnormal_power_flag")),
        }
        created_ids.append(_insert_engineering_feature(
            category="CNC_METER",
            source_table="cnc_meter_feature",
            source_pk=row.get("feature_id"),
            feature_name="power_load_norm",
            raw_value=row.get("avg_power_kw_5min"),
            cleaned_value=round(power, 4),
            normalized_value=_norm(power, 15),
            time_bucket="LATEST_5MIN",
            downstream_stage="STEP3_LSTM_STEP6_DQN_STATE",
            cnc_machine_id=row.get("cnc_machine_id"),
            vector=vector,
        ))
        created_ids.append(_insert_engineering_feature(
            category="CNC_METER",
            source_table="cnc_meter_feature",
            source_pk=row.get("feature_id"),
            feature_name="thd_risk_norm",
            raw_value=row.get("thd_current_avg"),
            cleaned_value=round(thd, 4),
            normalized_value=_norm(thd, 30),
            time_bucket="LATEST_5MIN",
            downstream_stage="STEP4_ARIMA_STEP6_DQN_STATE",
            cnc_machine_id=row.get("cnc_machine_id"),
            vector=vector,
        ))

    # WMS line-side inventory -> Step6 DQN State / Step8 Action
    inventory_rows = fetch_all("SELECT * FROM line_side_inventory_snapshot ORDER BY snapshot_id DESC LIMIT 200")
    for row in inventory_rows:
        available = _num(row.get("available_qty"))
        safety = max(1.0, _num(row.get("safety_stock_qty"), 1))
        shortage_qty = _num(row.get("shortage_qty"))
        shortage_risk = 1.0 if bool(row.get("shortage_flag")) else max(0.0, min(1.0, 1 - available / safety))
        vector = {
            "available_qty": available,
            "safety_stock_qty": safety,
            "shortage_qty": shortage_qty,
            "shortage_risk": shortage_risk,
        }
        created_ids.append(_insert_engineering_feature(
            category="WMS_INVENTORY",
            source_table="line_side_inventory_snapshot",
            source_pk=row.get("snapshot_id"),
            feature_name="material_shortage_risk",
            raw_value=shortage_qty,
            cleaned_value=round(shortage_risk, 4),
            normalized_value=round(shortage_risk, 6),
            time_bucket="LATEST",
            downstream_stage="STEP6_DQN_STATE_STEP8_ACTION",
            cnc_machine_id=row.get("cnc_machine_id"),
            material_no=row.get("material_no"),
            vector=vector,
        ))

    # ERP order -> Step3 / Step6
    work_orders = fetch_all("SELECT * FROM work_order_progress_snapshot ORDER BY snapshot_id DESC LIMIT 200")
    for row in work_orders:
        planned = max(1.0, _num(row.get("planned_qty"), 1))
        remaining = _num(row.get("remaining_qty"))
        progress_rate = max(0.0, min(1.0, 1 - remaining / planned))
        priority = _num(row.get("priority_level"), 5)
        vector = {
            "planned_qty": planned,
            "remaining_qty": remaining,
            "progress_rate": progress_rate,
            "priority_level": priority,
            "estimated_remaining_hours": _num(row.get("estimated_remaining_hours")),
        }
        created_ids.append(_insert_engineering_feature(
            category="ERP_WORK_ORDER",
            source_table="work_order_progress_snapshot",
            source_pk=row.get("snapshot_id"),
            feature_name="order_progress_norm",
            raw_value=remaining,
            cleaned_value=round(progress_rate, 4),
            normalized_value=round(progress_rate, 6),
            time_bucket="LATEST",
            downstream_stage="STEP3_LSTM_STEP5_FUSION_STEP6_DQN_STATE",
            cnc_machine_id=row.get("assigned_cnc_machine_id"),
            work_order_no=row.get("work_order_no"),
            vector=vector,
        ))
        created_ids.append(_insert_engineering_feature(
            category="ERP_WORK_ORDER",
            source_table="work_order_progress_snapshot",
            source_pk=row.get("snapshot_id"),
            feature_name="priority_norm",
            raw_value=priority,
            cleaned_value=round(priority, 4),
            normalized_value=_norm(priority, 10),
            time_bucket="LATEST",
            downstream_stage="STEP6_DQN_STATE_STEP8_ACTION",
            cnc_machine_id=row.get("assigned_cnc_machine_id"),
            work_order_no=row.get("work_order_no"),
            vector=vector,
        ))

    # MES run-card -> Step3 / Step4 / Step6
    run_card_rows = fetch_all("SELECT * FROM aips_run_card_detail ORDER BY run_card_detail_id DESC LIMIT 200")
    for row in run_card_rows:
        actual_minutes = _num(row.get("actual_processing_minutes"))
        delay_minutes = _num(row.get("delay_minutes"))
        quality_risk = _num(row.get("quality_risk_score"), 0.1)
        vector = {
            "actual_processing_minutes": actual_minutes,
            "delay_minutes": delay_minutes,
            "quality_risk_score": quality_risk,
            "shortage_flag": bool(row.get("shortage_flag")),
            "energy_kwh": _num(row.get("energy_kwh")),
        }
        created_ids.append(_insert_engineering_feature(
            category="MES_RUN_CARD",
            source_table="aips_run_card_detail",
            source_pk=row.get("run_card_detail_id"),
            feature_name="process_time_delay_norm",
            raw_value=delay_minutes,
            cleaned_value=round(delay_minutes, 4),
            normalized_value=_norm(delay_minutes, 180),
            time_bucket="LATEST",
            downstream_stage="STEP3_LSTM_STEP4_ARIMA_STEP6_DQN_STATE",
            cnc_machine_id=row.get("cnc_machine_id"),
            vector=vector,
        ))
        created_ids.append(_insert_engineering_feature(
            category="MES_RUN_CARD",
            source_table="aips_run_card_detail",
            source_pk=row.get("run_card_detail_id"),
            feature_name="quality_risk_norm",
            raw_value=quality_risk,
            cleaned_value=round(quality_risk, 4),
            normalized_value=max(0.0, min(1.0, quality_risk)),
            time_bucket="LATEST",
            downstream_stage="STEP3_LSTM_STEP10_REWARD",
            cnc_machine_id=row.get("cnc_machine_id"),
            vector=vector,
        ))

    # Step10 Reward feedback -> Step1/2 loop
    reward_rows = fetch_all("SELECT * FROM aips_reward_result ORDER BY reward_id DESC LIMIT 100")
    for row in reward_rows:
        reward = _num(row.get("total_reward_score"))
        vector = {
            "reward_score": reward,
            "actual_oee": _num(row.get("actual_oee")),
            "actual_yield_rate": _num(row.get("actual_yield_rate")),
            "delay_hours": _num(row.get("delay_hours")),
            "energy_kwh": _num(row.get("energy_kwh")),
            "feedback_loop": "STEP10_TO_STEP1_TO_STEP2",
        }
        created_ids.append(_insert_engineering_feature(
            category="REWARD_FEEDBACK",
            source_table="aips_reward_result",
            source_pk=row.get("reward_id"),
            feature_name="reward_feedback_score",
            raw_value=reward,
            cleaned_value=round(reward, 4),
            normalized_value=_norm(reward, 100),
            time_bucket="LATEST",
            downstream_stage="STEP1_DATA_INPUT_STEP2_FEATURE_ENGINEERING_STEP6_DQN_STATE",
            cnc_machine_id=row.get("cnc_machine_id"),
            work_order_no=row.get("work_order_no"),
            vector=vector,
            engineering_step="STEP10_FEEDBACK_TO_STEP1_STEP2",
        ))

    execute(
        """
        INSERT INTO aips_data_sync_log (sync_time, source_system, target_table, sync_type, sync_status, record_count, message)
        VALUES (NOW(), 'AIPS_DATA_ENGINEERING', 'aips_data_engineering_feature', 'FEATURE_ENGINEERING', 'SUCCESS', %s,
                'Step2 資料工程完成，特徵已往後提供 Step3~10，Reward 也已回饋 Step1/2')
        """,
        (len(created_ids),),
    )

    return {
        "success": True,
        "created_count": len(created_ids),
        "created_ids": created_ids[-20:],
        "message": f"Step2 已建立 {len(created_ids)} 筆資料工程特徵，並可往後餵給 Step3~10。",
    }


def latest_features(limit: int = 200) -> List[Dict[str, Any]]:
    ensure_extra_schema()
    return fetch_all(
        """
        SELECT *
        FROM aips_data_engineering_feature
        ORDER BY data_feature_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def downstream_summary() -> List[Dict[str, Any]]:
    ensure_extra_schema()
    return fetch_all(
        """
        SELECT
            COALESCE(downstream_stage, 'UNKNOWN') AS downstream_stage,
            COUNT(*) AS feature_count,
            MAX(feature_time) AS latest_feature_time
        FROM aips_data_engineering_feature
        GROUP BY COALESCE(downstream_stage, 'UNKNOWN')
        ORDER BY feature_count DESC, downstream_stage
        """
    )


def feedback_summary() -> Dict[str, Any]:
    ensure_extra_schema()
    total = fetch_one("SELECT COUNT(*) AS cnt FROM aips_data_engineering_feature WHERE feature_category = 'REWARD_FEEDBACK'")
    latest = fetch_one(
        """
        SELECT *
        FROM aips_data_engineering_feature
        WHERE feature_category = 'REWARD_FEEDBACK'
        ORDER BY data_feature_id DESC
        LIMIT 1
        """
    )
    return {
        "feedback_count": int(total["cnt"]) if total else 0,
        "latest_feedback": latest,
        "loop": "STEP10 Reward → STEP1 資料輸入 → STEP2 資料工程 → STEP3~10",
    }



def _ids(rows: List[Dict[str, Any]], key: str) -> List[int]:
    values = []
    for row in rows or []:
        try:
            value = row.get(key)
            if value is not None:
                values.append(int(value))
        except Exception:
            pass
    return values


def _fetch_by_ids(table: str, pk: str, ids: List[int], order_by: str | None = None) -> List[Dict[str, Any]]:
    if not ids:
        return []
    sql = f"""
        SELECT *
        FROM {table}
        WHERE {pk} = ANY(%s)
        ORDER BY {order_by or pk} DESC
    """
    return fetch_all(sql, (ids,))


def _fetch_current_run_rows(
    *,
    predictions: List[Dict[str, Any]],
    states: List[Dict[str, Any]],
    dqn_result: Dict[str, Any],
    rewards: List[Dict[str, Any]],
    run_card_demo: Dict[str, Any],
) -> Dict[str, Any]:
    """
    FIX71：回傳本次執行實際新增的表格資料，讓前端 Step3~10 直接顯示本次 rows。
    """
    prediction_ids = _ids(predictions, "prediction_id")
    state_ids = _ids(states, "state_id")
    action_ids = _ids(dqn_result.get("suggestions", []), "action_id")
    reward_ids = _ids(rewards, "reward_id")

    run_card_work_order_no = run_card_demo.get("work_order_no")
    run_card_id = run_card_demo.get("run_card_id")

    run_card_features = []
    if run_card_work_order_no:
        run_card_features = fetch_all(
            """
            SELECT *
            FROM aips_run_card_ai_feature
            WHERE work_order_no = %s
            ORDER BY feature_id DESC
            """,
            (run_card_work_order_no,),
        )

    run_card_details = []
    if run_card_id:
        run_card_details = fetch_all(
            """
            SELECT *
            FROM aips_run_card_detail
            WHERE run_card_id = %s
            ORDER BY run_card_detail_id DESC
            """,
            (run_card_id,),
        )

    current = {
        "predictions": _fetch_by_ids("aips_production_prediction", "prediction_id", prediction_ids, "prediction_id"),
        "run_card_features": run_card_features,
        "states": _fetch_by_ids("aips_scheduling_state", "state_id", state_ids, "state_id"),
        "actions": _fetch_by_ids("aips_dqn_action_log", "action_id", action_ids, "action_id"),
        "rewards": _fetch_by_ids("aips_reward_result", "reward_id", reward_ids, "reward_id"),
        "run_card_details": run_card_details,
        "prediction_ids": prediction_ids,
        "state_ids": state_ids,
        "action_ids": action_ids,
        "reward_ids": reward_ids,
        "run_card_work_order_no": run_card_work_order_no,
        "run_card_id": run_card_id,
    }
    current["changed_table_counts"] = {
        "Step3_LSTM_predictions": len(current["predictions"]),
        "Step4_ARIMA_run_card_features": len(current["run_card_features"]),
        "Step6_DQN_states": len(current["states"]),
        "Step7_8_DQN_actions": len(current["actions"]),
        "Step9_MES_details": len(current["run_card_details"]),
        "Step10_rewards": len(current["rewards"]),
    }
    return current


def run_full_aips_1_to_10_flow() -> Dict[str, Any]:
    """
    一鍵跑 AIPS 1-10：
    Step1 硬體資料 → Step2 資料工程 → Step3 LSTM → Step4 ARIMA
    → Step5 Fusion → Step6 DQN State → Step7 Q-Network
    → Step8 Action → Step9 MES 執行展示 → Step10 Reward → 回饋 Step1/2
    """
    step1 = seed_step1_hardware_inputs()
    run_card_demo = _create_demo_run_card_for_flow()
    step2 = run_step2_feature_engineering()
    predictions = run_predictions(reset_before_run=False)
    run_card_features = generate_run_card_ai_features()
    states = build_states()
    dqn = generate_dqn_suggestion()
    rewards = calculate_rewards(limit=30)
    erp_callback = process_pending_erp_orders(limit=20, callback_source="AIPS_1_TO_10_FULL_FLOW")
    feedback = run_step2_feature_engineering()
    _sanitize_legacy_non_cnc_rows()

    current_run = _fetch_current_run_rows(
        predictions=predictions,
        states=states,
        dqn_result=dqn,
        rewards=rewards,
        run_card_demo=run_card_demo,
    )

    stages = [
        {"step_no": 1, "step_name": "資料輸入層", "created_count": step1.get("raw_meter_created", 0), "message": step1.get("message")},
        {"step_no": 2, "step_name": "資料治理與特徵工程", "created_count": step2.get("created_count", 0), "message": step2.get("message")},
        {"step_no": 9, "step_name": "MES 流程卡輸入", "created_count": run_card_demo.get("detail_count", 0), "message": run_card_demo.get("message")},
        {"step_no": 3, "step_name": "LSTM 產量預測", "created_count": len(predictions), "message": "已執行 AI 產量預測"},
        {"step_no": 4, "step_name": "ARIMA 時間序列預測", "created_count": run_card_features.get("created", 0), "message": "已執行流程卡 ARIMA / LSTM 特徵"},
        {"step_no": 5, "step_name": "Prediction Fusion", "created_count": step2.get("created_count", 0), "message": "已將資料工程特徵與預測結果供 DQN State 使用"},
        {"step_no": 6, "step_name": "DQN State", "created_count": len(states), "message": "已建立 DQN State"},
        {"step_no": 7, "step_name": "DQN Q-Network", "created_count": dqn.get("created_count", dqn.get("created", 0)), "message": "已呼叫 DQN policy 產生 Q value / Action"},
        {"step_no": 8, "step_name": "Action 決策", "created_count": dqn.get("created_count", dqn.get("created", 0)), "message": dqn.get("message", "已產生 DQN Action")},
        {"step_no": 9, "step_name": "MES 執行層", "created_count": _count("aips_run_card_detail"), "message": "以製令流程卡 / 即時事件展示 MES 執行層"},
        {"step_no": 10, "step_name": "Reward 回饋", "created_count": len(rewards), "message": "已計算 Reward 並回饋 Step1/2"},
        {"step_no": 11, "step_name": "ERP 回傳", "created_count": erp_callback.get("processed_count", 0), "message": erp_callback.get("message")},
        {"step_no": 12, "step_name": "回饋循環", "created_count": feedback.get("created_count", 0), "message": "Step10 Reward → Step1 → Step2 → Step3~10 循環已建立"},
    ]

    return {
        "success": True,
        "message": "AIPS 1-10 全流程已執行完成，且已建立 Step10 回饋 Step1/2 的資料工程循環。",
        "stages": stages,
        "run_card_demo": run_card_demo,
        "current_run": current_run,
        "source_summary": source_summary(),
        "downstream_summary": downstream_summary(),
        "feedback_summary": feedback_summary(),
        "erp_callback": erp_callback,
    }
