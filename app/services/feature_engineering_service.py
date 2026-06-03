from app.core.database import fetch_all, execute_returning_id, execute

def calculate_meter_features(cnc_machine_id: str):
    rows = fetch_all(
        """
        SELECT *
        FROM cnc_meter_raw_data
        WHERE cnc_machine_id = %s
        ORDER BY collect_time DESC
        LIMIT 30
        """,
        (cnc_machine_id,),
    )
    if not rows:
        return None

    powers = [float(r["power_kw"] or 0) for r in rows]
    currents = [((float(r["current_r"] or 0) + float(r["current_s"] or 0) + float(r["current_t"] or 0)) / 3) for r in rows]
    thds = [float(r["thd_current"] or 0) for r in rows]
    demands = [float(r["demand_kw"] or 0) for r in rows]
    kwhs = [float(r["power_kwh"] or 0) for r in rows]

    avg_power = sum(powers) / len(powers)
    max_power = max(powers)
    min_power = min(powers)
    avg_current = sum(currents) / len(currents)
    thd_avg = sum(thds) / len(thds)
    demand_avg = sum(demands) / len(demands)
    energy_1hr = max(kwhs) - min(kwhs) if len(kwhs) >= 2 else 0

    machine_running_flag = avg_power >= 3
    machine_idle_flag = 0.5 <= avg_power < 3
    abnormal_power_flag = thd_avg >= 15 or max_power >= 12

    if abnormal_power_flag:
        status = "ABNORMAL"
    elif machine_running_flag:
        status = "RUNNING"
    elif machine_idle_flag:
        status = "IDLE"
    else:
        status = "STOPPED"

    feature_id = execute_returning_id(
        """
        INSERT INTO cnc_meter_feature (
            cnc_machine_id, feature_time,
            avg_power_kw_1min, avg_power_kw_5min, avg_power_kw_15min,
            max_power_kw, min_power_kw, power_variation_rate,
            avg_current_a, current_variation_rate, energy_kwh_1hr,
            demand_kw_15min, thd_current_avg,
            machine_running_flag, machine_idle_flag, machine_abnormal_power_flag,
            estimated_machine_status
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING feature_id
        """,
        (
            cnc_machine_id,
            avg_power, avg_power, avg_power,
            max_power, min_power, max_power - min_power,
            avg_current, max(currents) - min(currents),
            energy_1hr, demand_avg, thd_avg,
            machine_running_flag, machine_idle_flag, abnormal_power_flag,
            status,
        ),
        "feature_id",
    )

    execute(
        """
        INSERT INTO cnc_machine_status_snapshot (
            cnc_machine_id, snapshot_time, machine_status,
            running_minutes_today, idle_minutes_today, down_minutes_today, setup_minutes_today,
            avg_power_kw, current_load_level, estimated_finish_time,
            abnormal_flag, abnormal_reason
        )
        VALUES (%s, NOW(), %s, 300, 40, 10, 20, %s, %s, NOW() + INTERVAL '4 hours', %s, %s)
        """,
        (
            cnc_machine_id,
            status,
            avg_power,
            min(avg_power / 10.0, 1.0),
            abnormal_power_flag,
            "THD 或功率異常" if abnormal_power_flag else "",
        ),
    )

    return {"feature_id": feature_id, "cnc_machine_id": cnc_machine_id, "estimated_machine_status": status}
