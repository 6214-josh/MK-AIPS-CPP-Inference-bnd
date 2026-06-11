from datetime import datetime, timedelta
from psycopg2.extras import Json
from app.core.database import fetch_all, fetch_one, execute, execute_returning_id
from app.core.schema_guard import ensure_extra_schema
from app.services.feature_engineering_service import calculate_meter_features

CARBON_FACTOR = 0.494
CNC_CODES = [f"CNC-{i:02d}" for i in range(1, 15)]

def _num(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except Exception:
        return default

def _status(power_kw, thd_current):
    power_kw = _num(power_kw)
    thd_current = _num(thd_current)
    if thd_current >= 15 or power_kw >= 12:
        return "ABNORMAL"
    if power_kw >= 3:
        return "RUNNING"
    if power_kw >= 0.5:
        return "IDLE"
    return "STOPPED"

def _demo_meter_profile(cnc_machine_id: str):
    idx = int(str(cnc_machine_id).split('-')[-1]) if '-' in str(cnc_machine_id) else 1
    # CNC-03 保留為異常示範，其餘 14 台為 RUNNING / IDLE 合理狀態。
    if cnc_machine_id == "CNC-03":
        return dict(ip="192.168.1.202", power=12.5, demand=13.2, kwh=1200.8, pf=0.84, thd=18.0, current=25.5, uunbl=2.8, lunbl=12.6)
    power = round(2.4 + (idx % 6) * 1.15, 2)
    demand = round(power + 0.5, 2)
    thd = round(5.8 + (idx % 5) * 0.55, 2)
    current = round(7.5 + power * 1.7, 2)
    return dict(
        ip=f"192.168.1.{199 + idx}",
        power=power,
        demand=demand,
        kwh=880.0 + idx * 36.5,
        pf=round(0.88 + (idx % 4) * 0.02, 3),
        thd=thd,
        current=current,
        uunbl=round(0.9 + (idx % 4) * 0.28, 2),
        lunbl=round(2.4 + (idx % 5) * 0.65, 2),
    )


def ensure_14_cnc_meter_seed():
    ensure_extra_schema()
    for idx, cnc in enumerate(CNC_CODES, start=1):
        data = _demo_meter_profile(cnc)
        execute(
            """
            INSERT INTO aips_sim_cnc_smart_meter (
                cnc_machine_id, meter_id, device_ip, protocol_type, modbus_unit_id,
                mqtt_topic, voltage_v, current_a, power_kw, demand_kw, thd_current,
                machine_status, online_flag, last_collect_time
            )
            VALUES (%s,%s,%s,'MODBUS_TCP',%s,%s,220,%s,%s,%s,%s,%s,TRUE,NOW())
            ON CONFLICT DO NOTHING
            """,
            (
                cnc, f"METER-{cnc}", data["ip"], 10 + idx, f"AIPS/{cnc}/METER",
                data["current"], data["power"], data["demand"], data["thd"],
                _status(data["power"], data["thd"]),
            ),
        )
        execute(
            """
            INSERT INTO aips_electric_cnc_link (
                cnc_machine_id, meter_id, device_ip, protocol_type,
                modbus_unit_id, connected_flag, last_collect_time
            )
            VALUES (%s,%s,%s,'MODBUS_TCP',%s,TRUE,NOW())
            ON CONFLICT DO NOTHING
            """,
            (cnc, f"METER-{cnc}", data["ip"], idx),
        )
        execute(
            """
            UPDATE aips_sim_cnc_smart_meter
            SET meter_id=%s, device_ip=%s, protocol_type='MODBUS_TCP', modbus_unit_id=%s,
                mqtt_topic=%s, current_a=%s, power_kw=%s, demand_kw=%s,
                thd_current=%s, machine_status=%s, online_flag=TRUE, last_collect_time=NOW()
            WHERE cnc_machine_id=%s
            """,
            (
                f"METER-{cnc}", data["ip"], 10 + idx, f"AIPS/{cnc}/METER",
                data["current"], data["power"], data["demand"], data["thd"],
                _status(data["power"], data["thd"]), cnc,
            ),
        )
        execute(
            """
            UPDATE aips_electric_cnc_link
            SET meter_id=%s, device_ip=%s, protocol_type='MODBUS_TCP', modbus_unit_id=%s,
                connected_flag=TRUE, last_collect_time=NOW()
            WHERE cnc_machine_id=%s
            """,
            (f"METER-{cnc}", data["ip"], idx, cnc),
        )


def _seed_meter_raw(cnc_machine_id: str):
    ensure_14_cnc_meter_seed()
    if cnc_machine_id not in CNC_CODES:
        cnc_machine_id = "CNC-01"
    data = _demo_meter_profile(cnc_machine_id)
    payload = {
        "source": "FFA_ELECTRIC_MONITOR_MIGRATION",
        "cncMachineId": cnc_machine_id,
        "meterId": f"METER-{cnc_machine_id}",
        "kWh": data["kwh"],
        "P": data["power"] * 1000,
        "PF": data["pf"],
        "THD": data["thd"],
    }
    meter_data_id = execute_returning_id("""
        INSERT INTO cnc_meter_raw_data (
            meter_id, cnc_machine_id, device_ip, mqtt_topic, collect_time,
            voltage_r, voltage_s, voltage_t, current_r, current_s, current_t,
            power_kw, power_kwh, power_factor, frequency_hz, demand_kw,
            thd_voltage, thd_current, phase_imbalance_rate, raw_payload
        )
        VALUES (
            %s, %s, %s, %s, NOW(),
            220, 221, 219, %s, %s, %s,
            %s, %s, %s, 60, %s,
            2.1, %s, %s, %s
        )
        RETURNING meter_data_id
    """, (
        f"METER-{cnc_machine_id}", cnc_machine_id, data["ip"], f"AIPS/{cnc_machine_id}/METER",
        data["current"], data["current"] + 0.3, data["current"] - 0.2,
        data["power"], data["kwh"], data["pf"], data["demand"],
        data["thd"], data["uunbl"], Json(payload)
    ), "meter_data_id")

    execute("""
        UPDATE aips_sim_cnc_smart_meter
        SET power_kw=%s, demand_kw=%s, thd_current=%s, machine_status=%s, last_collect_time=NOW(), online_flag=TRUE
        WHERE cnc_machine_id=%s
    """, (data["power"], data["demand"], data["thd"], _status(data["power"], data["thd"]), cnc_machine_id))

    execute("""
        UPDATE aips_electric_cnc_link
        SET last_collect_time=NOW(), connected_flag=TRUE
        WHERE cnc_machine_id=%s
    """, (cnc_machine_id,))

    calculate_meter_features(cnc_machine_id)
    return meter_data_id

def seed_all_cnc_meter_data():
    ensure_14_cnc_meter_seed()
    ids = []
    for cnc in CNC_CODES:
        ids.append(_seed_meter_raw(cnc))
    return {"success": True, "meter_data_ids": ids, "cnc_count": len(CNC_CODES), "message": "已模擬 14 台 CNC 智慧電表資料"}

def ensure_full_meter_demo_data():
    ensure_14_cnc_meter_seed()
    raw_count = fetch_one("SELECT COUNT(DISTINCT cnc_machine_id) AS cnt FROM cnc_meter_raw_data WHERE cnc_machine_id IS NOT NULL")
    feature_count = fetch_one("SELECT COUNT(DISTINCT cnc_machine_id) AS cnt FROM cnc_meter_feature WHERE cnc_machine_id IS NOT NULL")
    if int((raw_count or {}).get("cnt") or 0) < len(CNC_CODES) or int((feature_count or {}).get("cnt") or 0) < len(CNC_CODES):
        seed_all_cnc_meter_data()

def get_alert_settings():
    ensure_extra_schema()
    return fetch_all("""
        SELECT alert_type AS "alertType", alert_desc AS "alertDesc",
               thrd_value AS "thrdValue", thrd_value2 AS "thrdValue2"
        FROM aips_electric_alert_setting
        WHERE enabled_flag = TRUE
        ORDER BY alert_type
    """)

def get_cnc_links():
    ensure_14_cnc_meter_seed()
    return fetch_all("""
        SELECT
            l.*,
            s.machine_status,
            s.power_kw,
            s.demand_kw,
            s.thd_current,
            f.estimated_machine_status,
            f.machine_abnormal_power_flag
        FROM aips_electric_cnc_link l
        LEFT JOIN aips_sim_cnc_smart_meter s ON s.cnc_machine_id = l.cnc_machine_id
        LEFT JOIN LATERAL (
            SELECT *
            FROM cnc_meter_feature f
            WHERE f.cnc_machine_id = l.cnc_machine_id
            ORDER BY f.feature_id DESC
            LIMIT 1
        ) f ON TRUE
        ORDER BY l.cnc_machine_id
    """)

def get_electric_monitor_data(cnc_machine_id: str | None = None):
    ensure_full_meter_demo_data()

    params = ()
    where = ""
    if cnc_machine_id and cnc_machine_id != "ALL":
        where = "WHERE cnc_machine_id = %s"
        params = (cnc_machine_id,)

    latest = fetch_one(f"""
        SELECT *
        FROM cnc_meter_raw_data
        {where}
        ORDER BY collect_time DESC, meter_data_id DESC
        LIMIT 1
    """, params)

    if not latest:
        return {
            "currentData": None,
            "monthlyDataList": [],
            "dailyDataList": [],
            "hourlyDataList": [],
            "cncLinks": get_cnc_links(),
            "alertSettings": get_alert_settings(),
        }

    monthly_ae = _num(latest.get("power_kwh"))
    power_kw = _num(latest.get("power_kw"))
    demand_kw = _num(latest.get("demand_kw"))
    pf = _num(latest.get("power_factor"))
    thd = _num(latest.get("thd_current"))
    phase = _num(latest.get("phase_imbalance_rate"))
    carbon = round(monthly_ae * CARBON_FACTOR, 1)

    now = datetime.now()
    monthly_rows = []
    for i in range(5, -1, -1):
        dt = now - timedelta(days=30 * i)
        factor = 0.75 + (6 - i) * 0.06
        ae = round(monthly_ae * factor, 1)
        max_pdm = round(max(demand_kw * factor, 1), 1)
        monthly_rows.append({
            "monthString": f"{dt.year}-{str(dt.month).zfill(2)}",
            "maxCe": round(ae * CARBON_FACTOR, 1),
            "maxPdm": max_pdm,
            "maxAe": ae,
        })

    raws = fetch_all(f"""
        SELECT *
        FROM cnc_meter_raw_data
        {where}
        ORDER BY collect_time DESC, meter_data_id DESC
        LIMIT 24
    """, params)

    daily_rows = []
    hourly_rows = []
    for idx, row in enumerate(reversed(raws)):
        t = row.get("collect_time") or now
        label = t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[11:16]
        ae = round(_num(row.get("power_kw")) * 0.25, 2)
        daily_rows.append({"timeString": label, "ae": ae, "createTime": str(t)})
        hourly_rows.append({"timeString": label, "hourlyAE": ae, "createTime": str(t)})

    current = {
        "meterDataId": latest.get("meter_data_id"),
        "cncMachineId": latest.get("cnc_machine_id"),
        "meterId": latest.get("meter_id"),
        "deviceIp": latest.get("device_ip"),
        "p": round(power_kw, 3),
        "pdm": round(demand_kw, 3),
        "pf": round(pf, 3),
        "thdCurrent": round(thd, 3),
        "uunbl": round(phase, 3),
        "lunbl": round(min(thd, 15), 3),
        "loadFactor": round(min((power_kw / 15.0) * 100, 100), 2),
        "monthlyAe": round(monthly_ae, 1),
        "lastYearMonthlyAe": round(monthly_ae * 0.92, 1),
        "carbonEmission": carbon,
        "lastYearCarbonEmission": round(carbon * 0.92, 1),
        "machineStatus": _status(power_kw, thd),
        "collectTime": str(latest.get("collect_time")),
    }

    execute("""
        INSERT INTO aips_electric_dashboard_snapshot (
            cnc_machine_id, meter_id, monthly_ae, last_year_monthly_ae,
            carbon_emission, last_year_carbon_emission,
            max_demand_kw, max_power_kw, avg_power_factor, uunbl, lunbl, load_factor
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        current["cncMachineId"], current["meterId"], current["monthlyAe"], current["lastYearMonthlyAe"],
        current["carbonEmission"], current["lastYearCarbonEmission"],
        current["pdm"], current["p"], current["pf"], current["uunbl"], current["lunbl"], current["loadFactor"]
    ))

    return {
        "currentData": current,
        "monthlyDataList": monthly_rows,
        "dailyDataList": daily_rows,
        "hourlyDataList": hourly_rows,
        "cncLinks": get_cnc_links(),
        "alertSettings": get_alert_settings(),
    }
