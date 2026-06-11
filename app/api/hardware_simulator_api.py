from fastapi import APIRouter
from app.core.database import fetch_all, execute_returning_id, execute
from app.core.schema_guard import ensure_extra_schema
from app.services.feature_engineering_service import calculate_meter_features
from app.services.electric_meter_service import ensure_14_cnc_meter_seed

router = APIRouter()

CNC_CODES = [f"CNC-{i:02d}" for i in range(1, 15)]

def _safe(fn):
    try:
        ensure_extra_schema()
        return fn()
    except Exception as exc:
        return {
            "success": False,
            "message": "硬體模擬器 API 發生錯誤，請看 error 欄位",
            "error": str(exc),
        }

@router.get("/overview")
def overview():
    return {
        "modules": [
            {"code": "A", "name": "WiFi PDA / Android 手持端", "description": "掃描員工識別證 / NFC、工單 / 製令 QR Code、CNC 機台 QR Code。"},
            {"code": "B", "name": "NFC 卡 / QR Code 標籤", "description": "綁定員工、物流車、料件、工單、機台等現場標籤。"},
            {"code": "C", "name": "CNC 機台 + 智慧電表", "description": "模擬電流、電壓、功率、THD、機台運轉 / 待機 / 停機，透過 Modbus / Ethernet 回傳。"},
            {"code": "D", "name": "線邊庫 / 人工推車物流", "description": "模擬入庫、領料、補料、退料與人工業務搬運。"}
        ],
        "flow": [
            "PDA 透過 WiFi / HTTPS 送出掃描事件",
            "NFC / QR Code 形成員工、物料、工單、機台事件",
            "CNC 智慧電表透過 Modbus / Ethernet 回傳電力資料",
            "線邊庫物流事件回寫 WMS / AIPS",
            "事件進入 FastAPI 後端並寫入 PostgreSQL",
            "AI Service 轉成 State / Action / Reward"
        ]
    }

@router.post("/init")
def init_schema():
    ensure_extra_schema()
    return {"success": True, "message": "AIPS Demo 資料表與預設資料已初始化"}

@router.get("/pda/devices")
def pda_devices():
    ensure_extra_schema()
    return fetch_all("SELECT * FROM aips_sim_pda_device ORDER BY pda_id DESC LIMIT 100")

@router.post("/pda/scan-demo")
def pda_scan_demo(cnc_machine_id: str = "CNC-01"):
    def action():
        target = cnc_machine_id if cnc_machine_id != "ALL" else "CNC-01"
        scan_event_id = execute_returning_id(
            """
            INSERT INTO aips_scan_event (
                scan_time, scan_type, scan_code, operator_id,
                work_order_no, material_no, cnc_machine_id,
                event_status, event_message
            )
            VALUES (
                NOW(), 'PDA_QRCODE', %s, 'operator01',
                %s, 'MAT-AL-6061', %s,
                'SUCCESS', 'PDA 掃描工單 / 料件 / CNC QR Code 成功'
            )
            RETURNING scan_event_id
            """,
            (f"QR-WO-{target}", f"WO-{target}-PDA", target),
            "scan_event_id",
        )
        execute(
            """
            INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
            VALUES ('PDA', 'SCAN_EVENT', 'INFO', 'AIPS/PDA/SCAN', jsonb_build_object('scan_type','PDA_QRCODE','cnc_machine_id',%s), 'PROCESSED')
            """,
            (target,),
        )
        execute("UPDATE aips_sim_pda_device SET last_scan_time = NOW() WHERE device_code = 'PDA-001'")
        return {"success": True, "scan_event_id": scan_event_id, "cnc_machine_id": target, "message": f"PDA 掃描事件已寫入 {target}"}
    return _safe(action)

@router.get("/tags")
def tags():
    ensure_extra_schema()
    return fetch_all("SELECT * FROM aips_sim_nfc_qrcode_tag ORDER BY tag_id DESC LIMIT 100")

@router.post("/tags/scan-demo")
def tag_scan_demo(cnc_machine_id: str = "CNC-01"):
    def action():
        target = cnc_machine_id if cnc_machine_id != "ALL" else "CNC-01"
        scan_event_id = execute_returning_id(
            """
            INSERT INTO aips_scan_event (
                scan_time, scan_type, scan_code, operator_id,
                work_order_no, material_no, cnc_machine_id,
                event_status, event_message
            )
            VALUES (
                NOW(), 'NFC', %s, 'operator01',
                %s, 'MAT-AL-6061', %s,
                'SUCCESS', 'NFC / QR 標籤掃描成功，已識別料件與工單'
            )
            RETURNING scan_event_id
            """,
            (f"NFC-MAT-{target}", f"WO-{target}-NFC", target),
            "scan_event_id",
        )
        execute("UPDATE aips_sim_nfc_qrcode_tag SET last_scan_time = NOW() WHERE tag_code = 'NFC-MAT-AL-6061'")
        execute(
            """
            INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
            VALUES ('NFC', 'TAG_SCAN', 'INFO', 'AIPS/TAG/NFC', jsonb_build_object('tag_code','NFC-MAT-AL-6061','cnc_machine_id',%s), 'PROCESSED')
            """,
            (target,),
        )
        return {"success": True, "scan_event_id": scan_event_id, "cnc_machine_id": target, "message": f"NFC / QR Code 標籤掃描事件已寫入 {target}"}
    return _safe(action)

@router.get("/cnc/meters")
def cnc_meters():
    ensure_14_cnc_meter_seed()
    return fetch_all("SELECT * FROM aips_sim_cnc_smart_meter ORDER BY cnc_machine_id LIMIT 100")

@router.post("/cnc/meter-demo/{cnc_machine_id}")
def cnc_meter_demo(cnc_machine_id: str):
    def action():
        meters = fetch_all(
            "SELECT * FROM aips_sim_cnc_smart_meter WHERE cnc_machine_id = %s ORDER BY sim_meter_id DESC LIMIT 1",
            (cnc_machine_id,),
        )
        if not meters:
            return {"success": False, "message": f"查無模擬智慧電表：{cnc_machine_id}"}

        meter = meters[0]
        meter_data_id = execute_returning_id(
            """
            INSERT INTO cnc_meter_raw_data (
                meter_id, cnc_machine_id, device_ip, mqtt_topic, collect_time,
                voltage_r, voltage_s, voltage_t,
                current_r, current_s, current_t,
                power_kw, power_kwh, power_factor, frequency_hz,
                demand_kw, thd_voltage, thd_current, phase_imbalance_rate,
                raw_payload
            )
            VALUES (
                %s, %s, %s, %s, NOW(),
                %s, %s, %s,
                %s, %s, %s,
                %s, 1000 + EXTRACT(EPOCH FROM NOW()) / 3600, 0.92, 60,
                %s, 2.5, %s, 1.2,
                jsonb_build_object('source','hardware_simulator','protocol',%s)
            )
            RETURNING meter_data_id
            """,
            (
                meter["meter_id"], meter["cnc_machine_id"], meter["device_ip"], meter["mqtt_topic"],
                meter["voltage_v"], meter["voltage_v"], meter["voltage_v"],
                meter["current_a"], meter["current_a"], meter["current_a"],
                meter["power_kw"], meter["demand_kw"], meter["thd_current"], meter["protocol_type"],
            ),
            "meter_data_id",
        )
        execute(
            """
            INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
            VALUES ('MODBUS', 'CNC_METER_DATA', 'INFO', %s, jsonb_build_object('cnc_machine_id', %s, 'power_kw', %s, 'thd_current', %s), 'PROCESSED')
            """,
            (meter["mqtt_topic"], meter["cnc_machine_id"], meter["power_kw"], meter["thd_current"]),
        )
        feature = calculate_meter_features(cnc_machine_id)
        return {"success": True, "meter_data_id": meter_data_id, "feature": feature, "message": "CNC 智慧電表模擬資料已寫入，並計算 Feature"}
    return _safe(action)

@router.get("/logistics")
def logistics():
    ensure_extra_schema()
    return fetch_all("SELECT * FROM aips_sim_line_side_logistics ORDER BY logistics_id DESC LIMIT 100")

@router.post("/logistics/cart-demo")
def logistics_cart_demo(cnc_machine_id: str = "CNC-02"):
    def action():
        targets = CNC_CODES if cnc_machine_id == "ALL" else [cnc_machine_id]
        created = []
        for index, target in enumerate(targets, start=1):
            material_no = f"MAT-CNC-{target[-2:]}"
            line_side = f"LS-{target}"
            current_qty = 45 + index * 3
            reserved_qty = 5
            safety_qty = 30
            available_qty = current_qty - reserved_qty
            shortage_qty = max(safety_qty - available_qty, 0)
            shortage_flag = shortage_qty > 0
            logistics_id = execute_returning_id(
                """
                INSERT INTO aips_sim_line_side_logistics (
                    event_time, cart_code, operator_id, work_order_no, material_no,
                    from_location, to_location, logistics_action, qty, event_status
                )
                VALUES (
                    NOW(), %s, 'operator01', %s, %s,
                    '倉庫-B', %s, 'REPLENISH', %s, 'DONE'
                )
                RETURNING logistics_id
                """,
                (f"CART-{target}", f"WO-{target}-LOG", material_no, line_side, 20 + index),
                "logistics_id",
            )
            snapshot_id = execute_returning_id(
                """
                INSERT INTO line_side_inventory_snapshot (
                    snapshot_time, cnc_machine_id, line_side_location_id,
                    material_no, material_name, lot_no,
                    current_qty, reserved_qty, available_qty, safety_stock_qty,
                    shortage_flag, shortage_qty, replenishment_required_flag,
                    last_scan_time, source_system
                )
                VALUES (
                    NOW(), %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    NOW(), 'HARDWARE_SIMULATOR'
                )
                RETURNING snapshot_id
                """,
                (
                    target, line_side, material_no, f"{target} 線邊庫料件", f"LOT-{target[-2:]}",
                    current_qty, reserved_qty, available_qty, safety_qty,
                    shortage_flag, shortage_qty, shortage_flag,
                ),
                "snapshot_id",
            )
            execute(
                """
                INSERT INTO aips_scan_event (
                    scan_time, scan_type, scan_code, operator_id,
                    work_order_no, material_no, cnc_machine_id,
                    event_status, event_message
                )
                VALUES (
                    NOW(), 'LOGISTICS_CART', %s, 'operator01',
                    %s, %s, %s,
                    'SUCCESS', '人工推車完成線邊庫補料'
                )
                """,
                (f"QR-CART-{target}", f"WO-{target}-LOG", material_no, target),
            )
            created.append({"cnc_machine_id": target, "logistics_id": logistics_id, "inventory_snapshot_id": snapshot_id})
        execute(
            """
            INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
            VALUES ('LOGISTICS', 'LINE_SIDE_REPLENISH', 'INFO', 'AIPS/LOGISTICS/CART', jsonb_build_object('cnc_machine_id',%s,'count',%s), 'PROCESSED')
            """,
            (cnc_machine_id, len(created)),
        )
        return {"success": True, "created_count": len(created), "created": created, "message": f"線邊庫 / 人工物流事件已寫入 {len(created)} 筆"}
    return _safe(action)


@router.post("/logistics/demo")
def logistics_demo_alias(cnc_machine_id: str = "CNC-02"):
    """
    FIX34：React 前端舊呼叫 /logistics/demo，實際後端原本只有 /logistics/cart-demo。
    保留 alias 避免 404。
    """
    return logistics_cart_demo(cnc_machine_id=cnc_machine_id)
