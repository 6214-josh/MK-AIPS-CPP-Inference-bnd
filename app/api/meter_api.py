from fastapi import APIRouter
from psycopg2.extras import Json
from app.core.database import fetch_all, execute_returning_id
from app.core.schema_guard import ensure_extra_schema
from app.schemas.meter import MeterRawCreate
from app.services.feature_engineering_service import calculate_meter_features
from app.services.electric_meter_service import (
    get_electric_monitor_data,
    seed_all_cnc_meter_data,
    _seed_meter_raw,
    get_alert_settings,
    get_cnc_links,
    ensure_full_meter_demo_data,
)

router = APIRouter()

@router.post("/raw")
def insert_meter_raw(data: MeterRawCreate):
    ensure_extra_schema()
    payload = data.model_dump(mode="json")
    meter_id = execute_returning_id(
        """
        INSERT INTO cnc_meter_raw_data (
            meter_id, cnc_machine_id, device_ip, mqtt_topic, collect_time,
            voltage_r, voltage_s, voltage_t, current_r, current_s, current_t,
            power_kw, power_kwh, power_factor, frequency_hz, demand_kw,
            thd_voltage, thd_current, phase_imbalance_rate, raw_payload
        )
        VALUES (
            %s, %s, %s, %s, COALESCE(%s, NOW()),
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        RETURNING meter_data_id
        """,
        (
            data.meter_id, data.cnc_machine_id, data.device_ip, data.mqtt_topic, data.collect_time,
            data.voltage_r, data.voltage_s, data.voltage_t, data.current_r, data.current_s, data.current_t,
            data.power_kw, data.power_kwh, data.power_factor, data.frequency_hz, data.demand_kw,
            data.thd_voltage, data.thd_current, data.phase_imbalance_rate, Json(payload),
        ),
        "meter_data_id",
    )
    calculate_meter_features(data.cnc_machine_id)
    return {"meter_data_id": meter_id}

@router.post("/features/calculate/{cnc_machine_id}")
def calculate_feature(cnc_machine_id: str):
    ensure_extra_schema()
    return calculate_meter_features(cnc_machine_id)

@router.get("/raw/latest")
def latest_raw(limit: int = 100):
    ensure_extra_schema()
    ensure_full_meter_demo_data()
    return fetch_all("SELECT * FROM cnc_meter_raw_data ORDER BY meter_data_id DESC LIMIT %s", (limit,))

@router.get("/features/latest")
def latest_features(limit: int = 100):
    ensure_extra_schema()
    ensure_full_meter_demo_data()
    return fetch_all("SELECT * FROM cnc_meter_feature ORDER BY feature_id DESC LIMIT %s", (limit,))

# FIX23：FFA 智慧電表介面移植 API
@router.get("/electric/monitor")
def electric_monitor(cnc_machine_id: str = "ALL"):
    return get_electric_monitor_data(cnc_machine_id)

@router.post("/electric/demo/{cnc_machine_id}")
def electric_demo(cnc_machine_id: str):
    meter_data_id = _seed_meter_raw(cnc_machine_id)
    return {"success": True, "meter_data_id": meter_data_id, "cnc_machine_id": cnc_machine_id}

@router.post("/electric/demo-all")
def electric_demo_all():
    return seed_all_cnc_meter_data()

@router.get("/electric/alert-settings")
def electric_alert_settings():
    return get_alert_settings()

@router.get("/electric/cnc-links")
def electric_cnc_links():
    return get_cnc_links()
