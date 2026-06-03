import json
from datetime import datetime
from app.core.database import fetch_all, execute_returning_id, execute

def build_states():
    work_orders = fetch_all(
        """
        SELECT *
        FROM work_order_progress_snapshot w
        WHERE COALESCE(w.current_process_status, '') <> 'COMPLETED'
          AND w.snapshot_id IN (
              SELECT MAX(snapshot_id)
              FROM work_order_progress_snapshot
              GROUP BY work_order_no
          )
        ORDER BY priority_level DESC, due_date ASC NULLS LAST
        """
    )

    created = []
    for wo in work_orders:
        cnc = wo["assigned_cnc_machine_id"]
        if not cnc:
            continue

        features = fetch_all("SELECT * FROM cnc_meter_feature WHERE cnc_machine_id = %s ORDER BY feature_time DESC LIMIT 1", (cnc,))
        feature = features[0] if features else {}

        inventories = fetch_all(
            """
            SELECT *
            FROM line_side_inventory_snapshot
            WHERE cnc_machine_id = %s
              AND snapshot_id IN (
                  SELECT MAX(snapshot_id)
                  FROM line_side_inventory_snapshot
                  WHERE cnc_machine_id = %s
                  GROUP BY material_no
              )
            ORDER BY shortage_flag DESC, shortage_qty DESC
            """,
            (cnc, cnc),
        )

        total_shortage_qty = sum(float(i["shortage_qty"] or 0) for i in inventories)
        any_shortage = any(bool(i["shortage_flag"]) for i in inventories)
        material_available = not any_shortage

        remaining_qty = float(wo["remaining_qty"] or 0)
        planned_qty = max(float(wo["planned_qty"] or 1), 1)
        progress_rate = 1 - (remaining_qty / planned_qty)

        priority = int(wo["priority_level"] or 5)
        estimated_hours = float(wo["estimated_remaining_hours"] or 1)
        due_date = wo["due_date"]

        remaining_days = 999.0
        delay_by_due = False
        if due_date:
            remaining_days = (due_date - datetime.now()).total_seconds() / 86400
            delay_by_due = remaining_days < (estimated_hours / 24)

        machine_status = feature.get("estimated_machine_status") or "UNKNOWN"
        avg_power = float(feature.get("avg_power_kw_5min") or 0)
        thd_avg = float(feature.get("thd_current_avg") or 0)
        abnormal_power = bool(feature.get("machine_abnormal_power_flag") or False)

        machine_available = machine_status in ("RUNNING", "IDLE")
        machine_load_rate = min(avg_power / 10.0, 1.0)

        delay_risk = 0.35 if delay_by_due else 0.05
        delay_risk += min(priority / 10.0, 1.0) * 0.25
        delay_risk += 0.25 if estimated_hours > 12 else 0.05
        delay_risk = min(delay_risk, 1.0)

        shortage_risk = 0.9 if any_shortage else 0.1
        quality_risk = min((thd_avg / 30.0) + (0.2 if abnormal_power else 0), 1.0)

        availability = 0.95
        if machine_status == "STOPPED":
            availability -= 0.30
        if any_shortage:
            availability -= 0.20
        if abnormal_power:
            availability -= 0.10
        availability = max(0.1, min(availability, 1.0))

        performance = max(0.5, min(0.98, 0.75 + progress_rate * 0.20 - delay_risk * 0.10))
        yield_rate = max(0.5, min(0.99, 0.97 - quality_risk * 0.20))
        current_oee = availability * performance * yield_rate

        state_vector = {
            "work_order_no": wo["work_order_no"],
            "cnc_machine_id": cnc,
            "machine_status": machine_status,
            "machine_available": machine_available,
            "machine_load_rate": machine_load_rate,
            "estimated_processing_time": estimated_hours,
            "line_side_material_available": material_available,
            "line_side_shortage_qty": total_shortage_qty,
            "remaining_order_qty": remaining_qty,
            "remaining_days_to_due": remaining_days,
            "order_priority_score": priority / 10.0,
            "delay_risk_score": delay_risk,
            "shortage_risk_score": shortage_risk,
            "power_consumption_level": avg_power,
            "abnormal_power_flag": abnormal_power,
            "quality_risk_score": quality_risk,
            "current_oee": current_oee,
        }

        state_id = execute_returning_id(
            """
            INSERT INTO aips_scheduling_state (
                state_time, work_order_no, product_no, process_code, cnc_machine_id,
                machine_status, machine_available_flag, machine_load_rate,
                estimated_processing_time, estimated_finish_time,
                line_side_material_available_flag, line_side_shortage_qty,
                remaining_order_qty, due_date, remaining_days_to_due,
                order_priority_score, delay_risk_score, shortage_risk_score,
                power_consumption_level, abnormal_power_flag, quality_risk_score,
                current_oee, current_availability_rate, current_performance_rate, current_yield_rate,
                state_vector_json
            )
            VALUES (
                NOW(), %s, %s, %s, %s,
                %s, %s, %s,
                %s, NOW() + (%s || ' hours')::interval,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb
            )
            RETURNING state_id
            """,
            (
                wo["work_order_no"], wo["product_no"], wo["process_code"], cnc,
                machine_status, machine_available, machine_load_rate,
                estimated_hours, estimated_hours,
                material_available, total_shortage_qty,
                remaining_qty, due_date, remaining_days,
                priority / 10.0, delay_risk, shortage_risk,
                avg_power, abnormal_power, quality_risk,
                current_oee, availability, performance, yield_rate,
                json.dumps(state_vector, ensure_ascii=False),
            ),
            "state_id",
        )
        created.append({"state_id": state_id, "work_order_no": wo["work_order_no"]})

        if any_shortage:
            execute(
                """
                INSERT INTO aips_exception_event (
                    event_time, event_type, event_level, cnc_machine_id, work_order_no, material_no,
                    event_description, detected_by, shortage_qty, impact_on_schedule_flag, impact_hours
                )
                VALUES (NOW(), 'MATERIAL_SHORTAGE', 'HIGH', %s, %s, %s, %s, 'AIPS_STATE_BUILDER', %s, TRUE, %s)
                """,
                (
                    cnc, wo["work_order_no"],
                    inventories[0]["material_no"] if inventories else "",
                    f"線邊庫缺料，缺料量 {total_shortage_qty}",
                    total_shortage_qty,
                    min(total_shortage_qty / 10, 8),
                ),
            )

    execute(
        """
        INSERT INTO aips_data_sync_log (sync_time, source_system, target_table, sync_type, sync_status, record_count, message)
        VALUES (NOW(), 'AIPS', 'aips_scheduling_state', 'BUILD_STATE', 'SUCCESS', %s, 'DQN State 建立完成')
        """,
        (len(created),),
    )
    return created
