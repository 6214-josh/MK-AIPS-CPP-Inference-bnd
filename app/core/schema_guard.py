from app.core.database import execute, fetch_all

def _run(sql: str):
    execute(sql)

def _add_columns(table_name: str, columns: list[tuple[str, str]]):
    for column_name, column_type in columns:
        execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")

def ensure_extra_schema():
    # 基礎核心表
    _run("""
        CREATE TABLE IF NOT EXISTS cnc_meter_raw_data (
            meter_data_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("cnc_meter_raw_data", [
        ("meter_id", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("device_ip", "VARCHAR(80)"),
        ("mqtt_topic", "VARCHAR(200)"),
        ("collect_time", "TIMESTAMP DEFAULT NOW()"),
        ("voltage_r", "NUMERIC(12,4)"),
        ("voltage_s", "NUMERIC(12,4)"),
        ("voltage_t", "NUMERIC(12,4)"),
        ("current_r", "NUMERIC(12,4)"),
        ("current_s", "NUMERIC(12,4)"),
        ("current_t", "NUMERIC(12,4)"),
        ("power_kw", "NUMERIC(12,4)"),
        ("power_kwh", "NUMERIC(14,4)"),
        ("power_factor", "NUMERIC(8,4)"),
        ("frequency_hz", "NUMERIC(8,4)"),
        ("demand_kw", "NUMERIC(12,4)"),
        ("thd_voltage", "NUMERIC(8,4)"),
        ("thd_current", "NUMERIC(8,4)"),
        ("phase_imbalance_rate", "NUMERIC(8,4)"),
        ("raw_payload", "JSONB"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS cnc_meter_feature (
            feature_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("cnc_meter_feature", [
        ("cnc_machine_id", "VARCHAR(80)"),
        ("feature_time", "TIMESTAMP DEFAULT NOW()"),
        ("avg_power_kw_1min", "NUMERIC(12,4)"),
        ("avg_power_kw_5min", "NUMERIC(12,4)"),
        ("avg_power_kw_15min", "NUMERIC(12,4)"),
        ("max_power_kw", "NUMERIC(12,4)"),
        ("min_power_kw", "NUMERIC(12,4)"),
        ("power_variation_rate", "NUMERIC(12,4)"),
        ("avg_current_a", "NUMERIC(12,4)"),
        ("current_variation_rate", "NUMERIC(12,4)"),
        ("energy_kwh_1hr", "NUMERIC(14,4)"),
        ("demand_kw_15min", "NUMERIC(12,4)"),
        ("thd_current_avg", "NUMERIC(8,4)"),
        ("machine_running_flag", "BOOLEAN DEFAULT FALSE"),
        ("machine_idle_flag", "BOOLEAN DEFAULT FALSE"),
        ("machine_abnormal_power_flag", "BOOLEAN DEFAULT FALSE"),
        ("estimated_machine_status", "VARCHAR(40)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS cnc_machine_status_snapshot (
            snapshot_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("cnc_machine_status_snapshot", [
        ("cnc_machine_id", "VARCHAR(80)"),
        ("snapshot_time", "TIMESTAMP DEFAULT NOW()"),
        ("machine_status", "VARCHAR(40)"),
        ("current_work_order_no", "VARCHAR(80)"),
        ("current_product_no", "VARCHAR(80)"),
        ("current_process_code", "VARCHAR(80)"),
        ("operator_id", "VARCHAR(80)"),
        ("running_minutes_today", "NUMERIC(12,4)"),
        ("idle_minutes_today", "NUMERIC(12,4)"),
        ("down_minutes_today", "NUMERIC(12,4)"),
        ("setup_minutes_today", "NUMERIC(12,4)"),
        ("avg_power_kw", "NUMERIC(12,4)"),
        ("current_load_level", "NUMERIC(8,4)"),
        ("estimated_finish_time", "TIMESTAMP"),
        ("abnormal_flag", "BOOLEAN DEFAULT FALSE"),
        ("abnormal_reason", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS work_order_progress_snapshot (
            snapshot_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("work_order_progress_snapshot", [
        ("snapshot_time", "TIMESTAMP DEFAULT NOW()"),
        ("work_order_no", "VARCHAR(80)"),
        ("sales_order_no", "VARCHAR(80)"),
        ("customer_id", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("product_name", "VARCHAR(200)"),
        ("process_code", "VARCHAR(80)"),
        ("planned_qty", "NUMERIC(14,4)"),
        ("completed_qty", "NUMERIC(14,4)"),
        ("good_qty", "NUMERIC(14,4)"),
        ("ng_qty", "NUMERIC(14,4)"),
        ("remaining_qty", "NUMERIC(14,4)"),
        ("due_date", "TIMESTAMP"),
        ("priority_level", "INTEGER"),
        ("current_process_status", "VARCHAR(40)"),
        ("assigned_cnc_machine_id", "VARCHAR(80)"),
        ("estimated_remaining_hours", "NUMERIC(12,4)"),
        ("delay_risk_flag", "BOOLEAN DEFAULT FALSE"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS line_side_inventory_snapshot (
            snapshot_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("line_side_inventory_snapshot", [
        ("snapshot_time", "TIMESTAMP DEFAULT NOW()"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("line_side_location_id", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("material_name", "VARCHAR(200)"),
        ("lot_no", "VARCHAR(80)"),
        ("current_qty", "NUMERIC(14,4)"),
        ("reserved_qty", "NUMERIC(14,4)"),
        ("available_qty", "NUMERIC(14,4)"),
        ("safety_stock_qty", "NUMERIC(14,4)"),
        ("shortage_flag", "BOOLEAN DEFAULT FALSE"),
        ("shortage_qty", "NUMERIC(14,4)"),
        ("replenishment_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("last_scan_time", "TIMESTAMP"),
        ("source_system", "VARCHAR(40)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_scheduling_state (
            state_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_scheduling_state", [
        ("state_time", "TIMESTAMP DEFAULT NOW()"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("process_code", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("machine_status", "VARCHAR(40)"),
        ("machine_available_flag", "BOOLEAN"),
        ("machine_load_rate", "NUMERIC(8,4)"),
        ("estimated_processing_time", "NUMERIC(12,4)"),
        ("estimated_finish_time", "TIMESTAMP"),
        ("line_side_material_available_flag", "BOOLEAN"),
        ("line_side_shortage_qty", "NUMERIC(14,4)"),
        ("remaining_order_qty", "NUMERIC(14,4)"),
        ("due_date", "TIMESTAMP"),
        ("remaining_days_to_due", "NUMERIC(12,4)"),
        ("order_priority_score", "NUMERIC(8,4)"),
        ("delay_risk_score", "NUMERIC(8,4)"),
        ("shortage_risk_score", "NUMERIC(8,4)"),
        ("power_consumption_level", "NUMERIC(12,4)"),
        ("abnormal_power_flag", "BOOLEAN"),
        ("quality_risk_score", "NUMERIC(8,4)"),
        ("current_oee", "NUMERIC(8,4)"),
        ("current_availability_rate", "NUMERIC(8,4)"),
        ("current_performance_rate", "NUMERIC(8,4)"),
        ("current_yield_rate", "NUMERIC(8,4)"),
        ("state_vector_json", "JSONB"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_dqn_action_log (
            action_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_dqn_action_log", [
        ("state_id", "BIGINT"),
        ("action_time", "TIMESTAMP DEFAULT NOW()"),
        ("action_type", "VARCHAR(80)"),
        ("action_name", "VARCHAR(120)"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("original_cnc_machine_id", "VARCHAR(80)"),
        ("suggested_cnc_machine_id", "VARCHAR(80)"),
        ("original_start_time", "TIMESTAMP"),
        ("suggested_start_time", "TIMESTAMP"),
        ("original_finish_time", "TIMESTAMP"),
        ("suggested_finish_time", "TIMESTAMP"),
        ("replenishment_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("maintenance_check_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("expected_delay_reduction_hours", "NUMERIC(12,4)"),
        ("expected_oee_improvement_rate", "NUMERIC(8,4)"),
        ("expected_shortage_risk_reduction", "NUMERIC(8,4)"),
        ("action_confidence_score", "NUMERIC(8,4)"),
        ("action_status", "VARCHAR(40) DEFAULT 'PENDING'"),
        ("action_reason", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_exception_event", "event_id", [
        ("event_time", "TIMESTAMP DEFAULT NOW()"),
        ("event_type", "VARCHAR(80)"),
        ("event_level", "VARCHAR(40)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("event_description", "TEXT"),
        ("detected_by", "VARCHAR(80)"),
        ("shortage_qty", "NUMERIC(14,4)"),
        ("impact_on_schedule_flag", "BOOLEAN DEFAULT FALSE"),
        ("impact_hours", "NUMERIC(12,4)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_data_sync_log", "sync_id", [
        ("sync_time", "TIMESTAMP DEFAULT NOW()"),
        ("source_system", "VARCHAR(80)"),
        ("target_table", "VARCHAR(120)"),
        ("sync_type", "VARCHAR(80)"),
        ("sync_status", "VARCHAR(40)"),
        ("record_count", "INTEGER DEFAULT 0"),
        ("message", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_production_prediction (
            prediction_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_production_prediction", [
        ("prediction_time", "TIMESTAMP DEFAULT NOW()"),
        ("model_name", "VARCHAR(120)"),
        ("model_version", "VARCHAR(40)"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("process_code", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("predicted_processing_time", "NUMERIC(12,4)"),
        ("predicted_finish_time", "TIMESTAMP"),
        ("predicted_delay_hours", "NUMERIC(12,4)"),
        ("predicted_machine_down_risk", "NUMERIC(8,4)"),
        ("predicted_quality_risk", "NUMERIC(8,4)"),
        ("predicted_material_shortage_risk", "NUMERIC(8,4)"),
        ("predicted_energy_consumption_kwh", "NUMERIC(14,4)"),
        ("prediction_confidence_score", "NUMERIC(8,4)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_reward_result (
            reward_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_reward_result", [
        ("action_id", "BIGINT"),
        ("state_id", "BIGINT"),
        ("evaluate_time", "TIMESTAMP DEFAULT NOW()"),
        ("work_order_no", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("actual_start_time", "TIMESTAMP"),
        ("actual_finish_time", "TIMESTAMP"),
        ("actual_processing_time", "NUMERIC(12,4)"),
        ("planned_processing_time", "NUMERIC(12,4)"),
        ("delay_hours", "NUMERIC(12,4)"),
        ("shortage_occurred_flag", "BOOLEAN"),
        ("machine_down_occurred_flag", "BOOLEAN"),
        ("ng_qty", "NUMERIC(14,4)"),
        ("good_qty", "NUMERIC(14,4)"),
        ("actual_yield_rate", "NUMERIC(8,4)"),
        ("actual_oee", "NUMERIC(8,4)"),
        ("energy_kwh", "NUMERIC(14,4)"),
        ("reward_oee_score", "NUMERIC(12,4)"),
        ("reward_delivery_score", "NUMERIC(12,4)"),
        ("reward_shortage_score", "NUMERIC(12,4)"),
        ("reward_quality_score", "NUMERIC(12,4)"),
        ("reward_energy_score", "NUMERIC(12,4)"),
        ("total_reward_score", "NUMERIC(12,4)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    # 系統 / 模擬器 / 架構功能表
    _run("""
        CREATE TABLE IF NOT EXISTS aips_user_account (
            user_id BIGSERIAL PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE
        )
    """)
    _add_columns("aips_user_account", [
        ("display_name", "VARCHAR(120)"),
        ("role_name", "VARCHAR(80)"),
        ("permission_json", "JSONB"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("password_text", "VARCHAR(120) DEFAULT '123456'"),
        ("last_login_time", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_login_log", "login_id", [
        ("login_time", "TIMESTAMP DEFAULT NOW()"),
        ("username", "VARCHAR(80)"),
        ("login_status", "VARCHAR(40)"),
        ("client_ip", "VARCHAR(80)"),
        ("user_agent", "TEXT"),
        ("message", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_pda_scan_task", "task_id", [
        ("task_type", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("source_location", "VARCHAR(80)"),
        ("target_location", "VARCHAR(80)"),
        ("task_status", "VARCHAR(40) DEFAULT 'OPEN'"),
        ("assigned_user", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_dashboard_widget", "widget_id", [
        ("widget_code", "VARCHAR(80)"),
        ("widget_name", "VARCHAR(120)"),
        ("widget_type", "VARCHAR(80)"),
        ("data_source", "VARCHAR(120)"),
        ("refresh_seconds", "INTEGER DEFAULT 30"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_scan_event", "scan_event_id", [
        ("scan_time", "TIMESTAMP DEFAULT NOW()"),
        ("scan_type", "VARCHAR(80)"),
        ("scan_code", "VARCHAR(200)"),
        ("operator_id", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("event_status", "VARCHAR(40)"),
        ("event_message", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_gateway_device", "device_id", [
        ("device_code", "VARCHAR(80)"),
        ("device_name", "VARCHAR(120)"),
        ("device_type", "VARCHAR(80)"),
        ("device_ip", "VARCHAR(80)"),
        ("protocol_type", "VARCHAR(80)"),
        ("mqtt_topic", "VARCHAR(200)"),
        ("modbus_unit_id", "INTEGER"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("last_seen_time", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_realtime_event_log", "event_id", [
        ("event_time", "TIMESTAMP DEFAULT NOW()"),
        ("event_source", "VARCHAR(80)"),
        ("event_type", "VARCHAR(80)"),
        ("event_level", "VARCHAR(40)"),
        ("topic", "VARCHAR(200)"),
        ("payload_json", "JSONB"),
        ("process_status", "VARCHAR(40) DEFAULT 'RECEIVED'"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_websocket_push_log", "push_id", [
        ("push_time", "TIMESTAMP DEFAULT NOW()"),
        ("channel_name", "VARCHAR(120)"),
        ("target_user", "VARCHAR(80)"),
        ("message_title", "VARCHAR(200)"),
        ("message_body", "TEXT"),
        ("push_status", "VARCHAR(40)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_notification_log", "notification_id", [
        ("notification_time", "TIMESTAMP DEFAULT NOW()"),
        ("channel_type", "VARCHAR(40)"),
        ("receiver", "VARCHAR(200)"),
        ("subject", "VARCHAR(200)"),
        ("message_body", "TEXT"),
        ("send_status", "VARCHAR(40)"),
        ("related_work_order_no", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_report_job", "report_job_id", [
        ("report_time", "TIMESTAMP DEFAULT NOW()"),
        ("report_type", "VARCHAR(80)"),
        ("report_name", "VARCHAR(200)"),
        ("file_format", "VARCHAR(40)"),
        ("file_path", "TEXT"),
        ("job_status", "VARCHAR(40)"),
        ("created_by", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_external_integration_log", "integration_id", [
        ("integration_time", "TIMESTAMP DEFAULT NOW()"),
        ("target_system", "VARCHAR(80)"),
        ("direction", "VARCHAR(40)"),
        ("api_name", "VARCHAR(120)"),
        ("request_json", "JSONB"),
        ("response_json", "JSONB"),
        ("status", "VARCHAR(40)"),
        ("message", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_file_object_log", "file_id", [
        ("upload_time", "TIMESTAMP DEFAULT NOW()"),
        ("storage_type", "VARCHAR(40)"),
        ("bucket_name", "VARCHAR(120)"),
        ("object_key", "TEXT"),
        ("file_name", "VARCHAR(200)"),
        ("file_type", "VARCHAR(80)"),
        ("related_module", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_business_service_log", "service_log_id", [
        ("service_time", "TIMESTAMP DEFAULT NOW()"),
        ("service_name", "VARCHAR(120)"),
        ("operation_name", "VARCHAR(120)"),
        ("operator_id", "VARCHAR(80)"),
        ("request_json", "JSONB"),
        ("result_status", "VARCHAR(40)"),
        ("result_message", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_sim_pda_device", "pda_id", [
        ("device_code", "VARCHAR(80)"),
        ("device_name", "VARCHAR(120)"),
        ("device_type", "VARCHAR(80)"),
        ("wifi_ssid", "VARCHAR(120)"),
        ("ip_address", "VARCHAR(80)"),
        ("operator_id", "VARCHAR(80)"),
        ("online_flag", "BOOLEAN DEFAULT TRUE"),
        ("last_scan_time", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_sim_nfc_qrcode_tag", "tag_id", [
        ("tag_code", "VARCHAR(200)"),
        ("tag_type", "VARCHAR(80)"),
        ("bind_target_type", "VARCHAR(80)"),
        ("bind_target_code", "VARCHAR(120)"),
        ("bind_target_name", "VARCHAR(200)"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("last_scan_time", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_sim_cnc_smart_meter", "sim_meter_id", [
        ("cnc_machine_id", "VARCHAR(80)"),
        ("meter_id", "VARCHAR(80)"),
        ("device_ip", "VARCHAR(80)"),
        ("protocol_type", "VARCHAR(80)"),
        ("modbus_unit_id", "INTEGER"),
        ("mqtt_topic", "VARCHAR(200)"),
        ("voltage_v", "NUMERIC(12,4)"),
        ("current_a", "NUMERIC(12,4)"),
        ("power_kw", "NUMERIC(12,4)"),
        ("demand_kw", "NUMERIC(12,4)"),
        ("thd_current", "NUMERIC(8,4)"),
        ("machine_status", "VARCHAR(40)"),
        ("online_flag", "BOOLEAN DEFAULT TRUE"),
        ("last_collect_time", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_sim_line_side_logistics", "logistics_id", [
        ("event_time", "TIMESTAMP DEFAULT NOW()"),
        ("cart_code", "VARCHAR(80)"),
        ("operator_id", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("from_location", "VARCHAR(80)"),
        ("to_location", "VARCHAR(80)"),
        ("logistics_action", "VARCHAR(80)"),
        ("qty", "NUMERIC(14,4)"),
        ("event_status", "VARCHAR(40)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])


    # FIX23：移植 FFA 智慧電表畫面所需資料結構，並與 CNC / AIPS 特徵串聯
    _run("""
        CREATE TABLE IF NOT EXISTS aips_electric_alert_setting (
            alert_setting_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_electric_alert_setting", [
        ("device_type", "VARCHAR(40) DEFAULT '2'"),
        ("alert_type", "VARCHAR(40)"),
        ("alert_desc", "VARCHAR(200)"),
        ("thrd_value", "NUMERIC(12,4)"),
        ("thrd_value2", "NUMERIC(12,4)"),
        ("enabled_flag", "BOOLEAN DEFAULT TRUE"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_electric_cnc_link (
            link_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_electric_cnc_link", [
        ("cnc_machine_id", "VARCHAR(80)"),
        ("meter_id", "VARCHAR(80)"),
        ("device_ip", "VARCHAR(80)"),
        ("protocol_type", "VARCHAR(80) DEFAULT 'MODBUS_TCP'"),
        ("modbus_unit_id", "INTEGER"),
        ("source_spec", "VARCHAR(80) DEFAULT 'FFA_ELECTRIC_MONITOR'"),
        ("connected_flag", "BOOLEAN DEFAULT TRUE"),
        ("last_collect_time", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _run("""
        CREATE TABLE IF NOT EXISTS aips_electric_dashboard_snapshot (
            snapshot_id BIGSERIAL PRIMARY KEY
        )
    """)
    _add_columns("aips_electric_dashboard_snapshot", [
        ("snapshot_time", "TIMESTAMP DEFAULT NOW()"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("meter_id", "VARCHAR(80)"),
        ("monthly_ae", "NUMERIC(14,4)"),
        ("last_year_monthly_ae", "NUMERIC(14,4)"),
        ("carbon_emission", "NUMERIC(14,4)"),
        ("last_year_carbon_emission", "NUMERIC(14,4)"),
        ("max_demand_kw", "NUMERIC(12,4)"),
        ("max_power_kw", "NUMERIC(12,4)"),
        ("avg_power_factor", "NUMERIC(8,4)"),
        ("uunbl", "NUMERIC(8,4)"),
        ("lunbl", "NUMERIC(8,4)"),
        ("load_factor", "NUMERIC(8,4)"),
        ("source_system", "VARCHAR(80) DEFAULT 'AIPS'"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])


    _simple_table("aips_data_engineering_feature", "data_feature_id", [
        ("feature_time", "TIMESTAMP DEFAULT NOW()"),
        ("feature_category", "VARCHAR(80)"),
        ("source_table", "VARCHAR(120)"),
        ("source_pk", "VARCHAR(120)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("feature_name", "VARCHAR(120)"),
        ("raw_value", "TEXT"),
        ("cleaned_value", "TEXT"),
        ("normalized_value", "NUMERIC(12,6)"),
        ("time_bucket", "VARCHAR(80)"),
        ("feature_vector_json", "JSONB"),
        ("engineering_step", "VARCHAR(80) DEFAULT 'FEATURE_ENGINEERING'"),
        ("downstream_stage", "VARCHAR(120)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])
    
    execute("CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_category ON aips_data_engineering_feature(feature_category)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_downstream ON aips_data_engineering_feature(downstream_stage)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_cnc ON aips_data_engineering_feature(cnc_machine_id)")

    _seed_if_empty()

def _simple_table(table_name: str, pk_name: str, columns: list[tuple[str, str]]):
    execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({pk_name} BIGSERIAL PRIMARY KEY)")
    _add_columns(table_name, columns)

def _table_empty(table_name: str) -> bool:
    row = fetch_all(f"SELECT COUNT(*) AS cnt FROM {table_name}")
    return int(row[0]["cnt"]) == 0

def _seed_if_empty():
    if _table_empty("aips_user_account"):
        execute("""
            INSERT INTO aips_user_account (username, display_name, role_name, permission_json, enabled_flag, password_text)
            VALUES
            ('admin', '系統管理員', 'ADMIN', '{"login":true,"permission":true}'::jsonb, TRUE, '123456'),
            ('operator01', '現場操作員', 'OPERATOR', '{"scan":true,"pda":true}'::jsonb, TRUE, '123456'),
            ('planner01', '生管排程人員', 'PLANNER', '{"schedule":true,"approve":true}'::jsonb, TRUE, '123456')
            ON CONFLICT (username) DO NOTHING
        """)


    if _table_empty("aips_electric_alert_setting"):
        execute("""
            INSERT INTO aips_electric_alert_setting (device_type, alert_type, alert_desc, thrd_value, thrd_value2)
            VALUES
            ('2','M1','電壓不平衡注意',2,5),
            ('2','M2','電壓不平衡異常',5,8),
            ('2','M3','電壓不平衡危險',8,10),
            ('2','M4','電流不平衡異常',8,12),
            ('2','M5','電流不平衡危險',12,15)
        """)

    if _table_empty("aips_electric_cnc_link"):
        execute("""
            INSERT INTO aips_electric_cnc_link (
                cnc_machine_id, meter_id, device_ip, protocol_type, modbus_unit_id, connected_flag, last_collect_time
            )
            VALUES
            ('CNC-01','METER-CNC-01','192.168.1.200','MODBUS_TCP',1,TRUE,NOW()),
            ('CNC-02','METER-CNC-02','192.168.1.201','MODBUS_TCP',2,TRUE,NOW()),
            ('CNC-03','METER-CNC-03','192.168.1.202','MODBUS_TCP',3,TRUE,NOW())
        """)


    if _table_empty("cnc_meter_raw_data"):
        execute("""
            INSERT INTO cnc_meter_raw_data (
                meter_id, cnc_machine_id, device_ip, mqtt_topic,
                voltage_r, voltage_s, voltage_t,
                current_r, current_s, current_t,
                power_kw, power_kwh, power_factor, frequency_hz,
                demand_kw, thd_voltage, thd_current,
                phase_imbalance_rate, raw_payload
            )
            VALUES
            ('METER-CNC-01','CNC-01','192.168.1.200','AIPS/CNC-01/METER',220,221,219,12,13,12,5.8,1001,0.92,60,6.2,2.1,7.2,1.2,'{}'),
            ('METER-CNC-02','CNC-02','192.168.1.201','AIPS/CNC-02/METER',220,220,219,9,9,10,3.2,900,0.90,60,3.6,2.3,8.0,1.5,'{}'),
            ('METER-CNC-03','CNC-03','192.168.1.202','AIPS/CNC-03/METER',220,220,221,25,26,25,12.5,1200,0.84,60,13.2,3.8,18.0,2.8,'{}')
        """)

    if _table_empty("work_order_progress_snapshot"):
        execute("""
            INSERT INTO work_order_progress_snapshot (
                work_order_no, product_no, product_name, process_code,
                planned_qty, completed_qty, good_qty, ng_qty,
                remaining_qty, due_date, priority_level,
                current_process_status, assigned_cnc_machine_id,
                estimated_remaining_hours, delay_risk_flag
            )
            VALUES
            ('WO-202606-001','P-AXLE-001','軸心零件','CNC-MILLING',100,20,20,0,80,NOW() + INTERVAL '20 hours',8,'PROCESSING','CNC-01',8,false),
            ('WO-202606-002','P-GEAR-002','齒輪零件','CNC-MILLING',120,30,29,1,90,NOW() + INTERVAL '8 hours',9,'PROCESSING','CNC-02',12,true),
            ('WO-202606-003','P-BRKT-003','支架零件','CNC-MILLING',80,10,10,0,70,NOW() + INTERVAL '36 hours',5,'PROCESSING','CNC-03',10,false)
        """)

    if _table_empty("line_side_inventory_snapshot"):
        execute("""
            INSERT INTO line_side_inventory_snapshot (
                cnc_machine_id, line_side_location_id,
                material_no, material_name, lot_no,
                current_qty, reserved_qty, available_qty,
                safety_stock_qty, shortage_flag, shortage_qty,
                replenishment_required_flag, last_scan_time, source_system
            )
            VALUES
            ('CNC-01','LS-CNC-01','MAT-AL-6061','鋁棒 6061','LOT-A1',80,10,70,30,false,0,false,NOW(),'WMS'),
            ('CNC-02','LS-CNC-02','MAT-S45C','S45C 圓棒','LOT-B1',20,5,15,30,true,15,true,NOW(),'WMS'),
            ('CNC-03','LS-CNC-03','MAT-SUS304','SUS304 板材','LOT-C1',55,10,45,30,false,0,false,NOW(),'WMS')
        """)

    if _table_empty("aips_sim_pda_device"):
        execute("""
            INSERT INTO aips_sim_pda_device (device_code, device_name, device_type, wifi_ssid, ip_address, operator_id, online_flag, last_scan_time)
            VALUES
            ('PDA-001', 'Android 手持端 1', 'ANDROID_PDA', 'Factory-WiFi', '192.168.1.51', 'operator01', TRUE, NOW()),
            ('PDA-002', 'Android 手持端 2', 'ANDROID_PDA', 'Factory-WiFi', '192.168.1.52', 'operator02', TRUE, NOW())
        """)

    if _table_empty("aips_sim_nfc_qrcode_tag"):
        execute("""
            INSERT INTO aips_sim_nfc_qrcode_tag (tag_code, tag_type, bind_target_type, bind_target_code, bind_target_name, enabled_flag, last_scan_time)
            VALUES
            ('NFC-EMP-operator01', 'NFC', 'EMPLOYEE', 'operator01', '現場操作員 01', TRUE, NOW()),
            ('QR-WO-202606-001', 'QRCODE', 'WORK_ORDER', 'WO-202606-001', '製令單 WO-202606-001', TRUE, NOW()),
            ('QR-CNC-01', 'QRCODE', 'CNC_MACHINE', 'CNC-01', 'CNC 機台 01', TRUE, NOW()),
            ('NFC-MAT-AL-6061', 'NFC', 'MATERIAL', 'MAT-AL-6061', '鋁棒 6061', TRUE, NOW()),
            ('QR-CART-001', 'QRCODE', 'LOGISTICS_CART', 'CART-001', '人工物流車 001', TRUE, NOW())
        """)

    if _table_empty("aips_sim_cnc_smart_meter"):
        execute("""
            INSERT INTO aips_sim_cnc_smart_meter (
                cnc_machine_id, meter_id, device_ip, protocol_type, modbus_unit_id, mqtt_topic,
                voltage_v, current_a, power_kw, demand_kw, thd_current, machine_status, online_flag, last_collect_time
            )
            VALUES
            ('CNC-01', 'METER-CNC-01', '192.168.1.200', 'MODBUS_TCP', 11, 'AIPS/CNC-01/METER', 220, 12, 6.2, 6.8, 7.5, 'RUNNING', TRUE, NOW()),
            ('CNC-02', 'METER-CNC-02', '192.168.1.201', 'MODBUS_TCP', 12, 'AIPS/CNC-02/METER', 220, 8, 3.1, 3.6, 8.1, 'IDLE', TRUE, NOW()),
            ('CNC-03', 'METER-CNC-03', '192.168.1.202', 'MODBUS_TCP', 13, 'AIPS/CNC-03/METER', 220, 25, 12.8, 13.3, 18.5, 'ABNORMAL', TRUE, NOW())
        """)

    if _table_empty("aips_sim_line_side_logistics"):
        execute("""
            INSERT INTO aips_sim_line_side_logistics (
                cart_code, operator_id, work_order_no, material_no, from_location, to_location, logistics_action, qty, event_status
            )
            VALUES
            ('CART-001', 'operator01', 'WO-202606-001', 'MAT-AL-6061', '倉庫-A', 'LS-CNC-01', 'REPLENISH', 30, 'DONE'),
            ('CART-002', 'operator02', 'WO-202606-002', 'MAT-S45C', '倉庫-B', 'LS-CNC-02', 'PICKING', 20, 'DONE')
        """)

    if _table_empty("aips_websocket_push_log"):
        execute("""
            INSERT INTO aips_websocket_push_log (channel_name, target_user, message_title, message_body, push_status)
            VALUES ('AIPS_DASHBOARD', 'admin', '缺料風險即時推播', 'CNC-02 線邊庫低於安全庫存。', 'PUSHED')
        """)

    if _table_empty("aips_notification_log"):
        execute("""
            INSERT INTO aips_notification_log (channel_type, receiver, subject, message_body, send_status, related_work_order_no)
            VALUES ('EMAIL', 'manager@example.com', 'AIPS 缺料風險通知', 'CNC-02 線邊庫低於安全庫存，建議提前補料。', 'SENT', 'WO-202606-002')
        """)

    if _table_empty("aips_report_job"):
        execute("""
            INSERT INTO aips_report_job (report_type, report_name, file_format, file_path, job_status, created_by)
            VALUES ('OEE', '每日 OEE 報表', 'Excel', '/reports/oee_daily.xlsx', 'DONE', 'admin')
        """)

    if _table_empty("aips_external_integration_log"):
        execute("""
            INSERT INTO aips_external_integration_log (target_system, direction, api_name, request_json, response_json, status, message)
            VALUES ('WMS', 'OUT', 'requestMaterialReplenishment', '{"material_no":"MAT-S45C"}'::jsonb, '{"result":"OK"}'::jsonb, 'SUCCESS', '補料請求已送出')
        """)


    # 25432 新 DB 是空庫時，流程卡頁面的 /run-cards/demo、/headers、
    # /features/generate、/dqn/suggest 也需要自動建立流程卡相關資料表。
    ensure_run_card_schema()

def ensure_run_card_schema():
    _simple_table("aips_run_card_header", "run_card_id", [
        ("run_card_no", "VARCHAR(80)"),
        ("production_batch_no", "VARCHAR(80)"),
        ("work_order_no", "VARCHAR(80)"),
        ("sales_order_no", "VARCHAR(80)"),
        ("customer_name", "VARCHAR(120)"),
        ("product_no", "VARCHAR(80)"),
        ("material_no", "VARCHAR(80)"),
        ("piece_id", "VARCHAR(120)"),
        ("serial_no", "VARCHAR(120)"),
        ("process_name", "VARCHAR(120)"),
        ("process_level", "VARCHAR(40)"),
        ("unit", "VARCHAR(40)"),
        ("size_length", "NUMERIC(14,4)"),
        ("size_width", "NUMERIC(14,4)"),
        ("planned_qty", "NUMERIC(14,4)"),
        ("completed_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("good_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("ng_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("remaining_qty", "NUMERIC(14,4)"),
        ("planned_start_time", "TIMESTAMP"),
        ("planned_finish_time", "TIMESTAMP"),
        ("actual_start_time", "TIMESTAMP"),
        ("actual_finish_time", "TIMESTAMP"),
        ("due_date", "TIMESTAMP"),
        ("priority_level", "INTEGER DEFAULT 5"),
        ("run_card_status", "VARCHAR(40) DEFAULT 'OPEN'"),
        ("source_system", "VARCHAR(40) DEFAULT 'AIPS'"),
        ("source_file_name", "VARCHAR(255)"),
        ("import_batch_no", "VARCHAR(80)"),
        ("remark", "TEXT"),
        ("created_by", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
        ("updated_by", "VARCHAR(80)"),
        ("updated_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_run_card_detail", "run_card_detail_id", [
        ("run_card_id", "BIGINT"),
        ("sequence_no", "INTEGER"),
        ("station_code", "VARCHAR(80)"),
        ("station_name", "VARCHAR(120)"),
        ("station_sub_name", "VARCHAR(120)"),
        ("process_type", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("machine_group", "VARCHAR(80)"),
        ("line_side_location_id", "VARCHAR(80)"),
        ("planned_qty", "NUMERIC(14,4)"),
        ("completed_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("good_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("ng_qty", "NUMERIC(14,4) DEFAULT 0"),
        ("control_spec_text", "TEXT"),
        ("measurement_spec_text", "TEXT"),
        ("standard_cycle_time_sec", "NUMERIC(14,4)"),
        ("standard_setup_time_min", "NUMERIC(14,4)"),
        ("input_time", "TIMESTAMP"),
        ("output_time", "TIMESTAMP"),
        ("actual_processing_minutes", "NUMERIC(14,4)"),
        ("wait_minutes_before_start", "NUMERIC(14,4)"),
        ("delay_minutes", "NUMERIC(14,4)"),
        ("responsible_user_id", "VARCHAR(80)"),
        ("responsible_user_name", "VARCHAR(120)"),
        ("sign_status", "VARCHAR(40)"),
        ("confirm_flag", "BOOLEAN DEFAULT FALSE"),
        ("qc_result", "VARCHAR(40)"),
        ("material_available_flag", "BOOLEAN"),
        ("shortage_flag", "BOOLEAN DEFAULT FALSE"),
        ("shortage_qty", "NUMERIC(14,4)"),
        ("replenishment_required_flag", "BOOLEAN DEFAULT FALSE"),
        ("machine_status_when_start", "VARCHAR(40)"),
        ("avg_power_kw", "NUMERIC(14,4)"),
        ("max_power_kw", "NUMERIC(14,4)"),
        ("avg_thd_current", "NUMERIC(14,4)"),
        ("energy_kwh", "NUMERIC(14,4)"),
        ("quality_risk_score", "NUMERIC(8,4)"),
        ("abnormal_flag", "BOOLEAN DEFAULT FALSE"),
        ("abnormal_reason", "TEXT"),
        ("detail_status", "VARCHAR(40) DEFAULT 'PENDING'"),
        ("ai_feature_ready_flag", "BOOLEAN DEFAULT FALSE"),
        ("remark", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
        ("updated_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_run_card_detail_item", "run_card_item_id", [
        ("run_card_detail_id", "BIGINT"),
        ("item_sequence_no", "INTEGER"),
        ("item_type", "VARCHAR(80)"),
        ("item_code", "VARCHAR(80)"),
        ("item_name", "VARCHAR(200)"),
        ("tool_no", "VARCHAR(80)"),
        ("tool_name", "VARCHAR(120)"),
        ("pressure_name", "VARCHAR(80)"),
        ("pressure_spec", "VARCHAR(120)"),
        ("speed_spec", "VARCHAR(120)"),
        ("planned_qty", "NUMERIC(14,4)"),
        ("control_spec_text", "TEXT"),
        ("spec_upper_limit", "NUMERIC(14,4)"),
        ("spec_lower_limit", "NUMERIC(14,4)"),
        ("target_value", "NUMERIC(14,4)"),
        ("confirm_flag", "BOOLEAN DEFAULT FALSE"),
        ("item_result", "VARCHAR(40)"),
        ("input_time", "TIMESTAMP"),
        ("output_time", "TIMESTAMP"),
        ("responsible_user_id", "VARCHAR(80)"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
        ("updated_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_run_card_measurement", "measurement_id", [
        ("run_card_detail_id", "BIGINT"),
        ("run_card_item_id", "BIGINT"),
        ("measure_time", "TIMESTAMP DEFAULT NOW()"),
        ("measure_source", "VARCHAR(40)"),
        ("measure_device_id", "VARCHAR(80)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("measure_name", "VARCHAR(120)"),
        ("measure_value", "NUMERIC(18,6)"),
        ("measure_unit", "VARCHAR(40)"),
        ("target_value", "NUMERIC(18,6)"),
        ("upper_limit", "NUMERIC(18,6)"),
        ("lower_limit", "NUMERIC(18,6)"),
        ("deviation_value", "NUMERIC(18,6)"),
        ("pass_flag", "BOOLEAN"),
        ("quality_risk_score", "NUMERIC(8,4)"),
        ("raw_measure_text", "TEXT"),
        ("raw_payload", "JSONB"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    _simple_table("aips_run_card_ai_feature", "feature_id", [
        ("feature_time", "TIMESTAMP DEFAULT NOW()"),
        ("run_card_id", "BIGINT"),
        ("run_card_detail_id", "BIGINT"),
        ("work_order_no", "VARCHAR(80)"),
        ("product_no", "VARCHAR(80)"),
        ("station_name", "VARCHAR(120)"),
        ("cnc_machine_id", "VARCHAR(80)"),
        ("sequence_no", "INTEGER"),
        ("actual_processing_minutes", "NUMERIC(14,4)"),
        ("moving_avg_processing_minutes", "NUMERIC(14,4)"),
        ("arima_predicted_minutes", "NUMERIC(14,4)"),
        ("lstm_predicted_minutes", "NUMERIC(14,4)"),
        ("predicted_finish_time", "TIMESTAMP"),
        ("delay_risk_score", "NUMERIC(8,4)"),
        ("shortage_risk_score", "NUMERIC(8,4)"),
        ("quality_risk_score", "NUMERIC(8,4)"),
        ("power_risk_score", "NUMERIC(8,4)"),
        ("dqn_state_json", "JSONB"),
        ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ])

    execute("CREATE INDEX IF NOT EXISTS ix_aips_run_card_header_card_no ON aips_run_card_header(run_card_no)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_run_card_header_work_order ON aips_run_card_header(work_order_no)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_run_card_detail_card ON aips_run_card_detail(run_card_id)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_run_card_detail_machine ON aips_run_card_detail(cnc_machine_id)")
    execute("CREATE INDEX IF NOT EXISTS ix_aips_run_card_ai_feature_work_order ON aips_run_card_ai_feature(work_order_no)")
