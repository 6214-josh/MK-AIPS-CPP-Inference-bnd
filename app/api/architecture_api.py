from fastapi import APIRouter, HTTPException
from app.core.database import fetch_all, execute_returning_id, execute
from app.core.schema_guard import ensure_extra_schema
from fastapi.responses import FileResponse
from pathlib import Path
from app.services.report_export_service import generate_report

router = APIRouter()

def _safe_list(sql: str):
    ensure_extra_schema()
    return fetch_all(sql)

def _safe_insert(sql: str, id_column: str):
    ensure_extra_schema()
    return execute_returning_id(sql, (), id_column)


def _report_media_type(fmt: str):
    fmt = (fmt or "").lower()
    if fmt in ("excel", "xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fmt == "pdf":
        return "application/pdf"
    if fmt in ("html", "bi"):
        return "text/html"
    if fmt == "csv":
        return "text/csv"
    return "application/octet-stream"

@router.get("/overview")
def overview():
    return {
        "groups": [
            {"group": "使用端 / 操作介面", "items": ["Web 管理後台", "PDA 手持端", "看板 / 報表", "NFC / QR Code / 工單掃描"]},
            {"group": "現場資料來源", "items": ["掃描事件", "CNC 機台狀態", "智慧電表數據", "MQTT / Modbus 資料"]},
            {"group": "API 與業務服務", "items": ["登入 / 權限管理", "工單 / 製令管理", "線邊庫 / 搬運任務", "排程建議查詢", "REST API"]},
            {"group": "即時通訊與事件處理", "items": ["MQTT Broker", "WebSocket 即時推播", "事件接收 / 轉發", "Gateway 資料接入"]},
            {"group": "資料儲存", "items": ["PostgreSQL 主資料 / 交易資料", "Timeseries / 歷史紀錄", "Redis 快取", "MinIO 檔案 / 圖片"]},
            {"group": "AI / DQN 決策服務", "items": ["資料處理", "State / Action / Reward", "排程建議", "建議結果輸出", "人工覆核"]},
            {"group": "對外整合與輸出", "items": ["MES / ERP / WMS", "Email / LINE / Teams", "Excel / PDF / BI", "OEE / 碳排 / 異常資訊"]},
        ]
    }

@router.get("/ui/users")
def users():
    return _safe_list("SELECT user_id, username, display_name, role_name, enabled_flag, created_at FROM aips_user_account ORDER BY user_id DESC LIMIT 100")

@router.get("/ui/pda-tasks")
def pda_tasks():
    return _safe_list("SELECT * FROM aips_pda_scan_task ORDER BY task_id DESC LIMIT 100")

@router.post("/ui/pda-tasks/demo")
def create_pda_task_demo():
    task_id = _safe_insert(
        """
        INSERT INTO aips_pda_scan_task (task_type, work_order_no, material_no, source_location, target_location, task_status, assigned_user)
        VALUES ('QRCODE_SCAN', 'WO-DEMO', 'MAT-DEMO', '倉庫-DEMO', 'LS-CNC-01', 'OPEN', 'operator01')
        RETURNING task_id
        """,
        "task_id",
    )
    return {"success": True, "task_id": task_id}

@router.get("/dashboard/widgets")
def widgets():
    return _safe_list("SELECT * FROM aips_dashboard_widget ORDER BY widget_id DESC LIMIT 100")

@router.get("/scan/events")
def scan_events():
    return _safe_list("SELECT * FROM aips_scan_event ORDER BY scan_event_id DESC LIMIT 100")

@router.post("/scan/events/demo")
def create_scan_event_demo():
    scan_event_id = _safe_insert(
        """
        INSERT INTO aips_scan_event (scan_type, scan_code, operator_id, work_order_no, material_no, cnc_machine_id, event_status, event_message)
        VALUES ('NFC', 'NFC-DEMO-' || EXTRACT(EPOCH FROM NOW())::bigint, 'operator01', 'WO-DEMO', 'MAT-DEMO', 'CNC-01', 'SUCCESS', 'Demo 掃描事件已建立')
        RETURNING scan_event_id
        """,
        "scan_event_id",
    )
    return {"success": True, "scan_event_id": scan_event_id}

@router.get("/gateway/devices")
def gateway_devices():
    return _safe_list("SELECT * FROM aips_gateway_device ORDER BY device_id DESC LIMIT 100")

@router.get("/events/realtime")
def realtime_events():
    return _safe_list("SELECT * FROM aips_realtime_event_log ORDER BY event_id DESC LIMIT 100")

@router.post("/events/realtime/demo")
def create_realtime_event_demo():
    event_id = _safe_insert(
        """
        INSERT INTO aips_realtime_event_log (event_source, event_type, event_level, topic, payload_json, process_status)
        VALUES ('MQTT', 'DEMO_EVENT', 'INFO', 'AIPS/DEMO/EVENT', jsonb_build_object('demo', true, 'created_at', NOW()), 'RECEIVED')
        RETURNING event_id
        """,
        "event_id",
    )
    return {"success": True, "event_id": event_id, "latest": realtime_events()}

@router.get("/events/websocket-push")
def websocket_push():
    return _safe_list("SELECT * FROM aips_websocket_push_log ORDER BY push_id DESC LIMIT 100")

@router.post("/events/websocket-push/demo")
def create_websocket_push_demo():
    push_id = _safe_insert(
        """
        INSERT INTO aips_websocket_push_log (channel_name, target_user, message_title, message_body, push_status)
        VALUES ('AIPS_DASHBOARD', 'admin', '即時推播測試', '這是一筆 WebSocket 即時推播 Demo。', 'PUSHED')
        RETURNING push_id
        """,
        "push_id",
    )
    return {"success": True, "push_id": push_id, "latest": websocket_push()}

@router.get("/storage/files")
def files():
    return _safe_list("SELECT * FROM aips_file_object_log ORDER BY file_id DESC LIMIT 100")

@router.get("/notifications")
def notifications():
    return _safe_list("SELECT * FROM aips_notification_log ORDER BY notification_id DESC LIMIT 100")

@router.post("/notifications/demo")
def create_notification_demo():
    notification_id = _safe_insert(
        """
        INSERT INTO aips_notification_log (channel_type, receiver, subject, message_body, send_status, related_work_order_no)
        VALUES ('LINE', 'line-group-aips', 'Demo 通知', '這是一筆 LINE / Email / Teams 通知 Demo。', 'SENT', 'WO-DEMO')
        RETURNING notification_id
        """,
        "notification_id",
    )
    return {"success": True, "notification_id": notification_id, "latest": notifications()}


def _delete_report_file_if_exists(file_path):
    if not file_path:
        return False
    try:
        p = Path(str(file_path))
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        return False
    return False

@router.get("/reports")
def reports():
    return _safe_list("SELECT * FROM aips_report_job ORDER BY report_job_id DESC LIMIT 100")

@router.post("/reports/demo")
def create_report_demo():
    result = generate_report("excel")
    return {
        "success": True,
        "report_job_id": result["report_job_id"],
        "download_url": f"/api/architecture/reports/download/{result['report_job_id']}",
        "latest": reports()
    }



@router.post("/reports/export/{format_name}")
def export_report(format_name: str):
    try:
        result = generate_report(format_name)
        return {
            "success": True,
            "report_job_id": result["report_job_id"],
            "filename": result["filename"],
            "download_url": f"/api/architecture/reports/download/{result['report_job_id']}",
            "latest": reports()
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))




def _export_report_file_response(format_name: str):
    try:
        result = generate_report(format_name)
        file_path = Path(result["file"])
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type=_report_media_type(str(file_path.suffix).replace(".", "").lower()),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/reports/export-file/{format_name}")
def export_report_file_get(format_name: str):
    """
    FIX27：給瀏覽器直接網址下載用。
    使用 GET 可避免前端 blob / popup / CORS 行為造成按鈕看起來沒反應。
    """
    return _export_report_file_response(format_name)

@router.post("/reports/export-file/{format_name}")
def export_report_file_post(format_name: str):
    """
    保留 POST 相容舊前端。
    """
    return _export_report_file_response(format_name)



@router.get("/reports/download/{report_job_id}")
def download_report(report_job_id: int):
    ensure_extra_schema()
    rows = fetch_all(
        "SELECT * FROM aips_report_job WHERE report_job_id = %s LIMIT 1",
        (report_job_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="查無報表")

    row = rows[0]
    path = row.get("file_path")
    fmt = str(row.get("file_format") or "excel").lower()

    # FIX25：
    # 舊資料庫裡可能有 /reports/demo_oee.xlsx 或 /reports/oee_daily.xlsx，
    # 這些只是早期 demo path，實體檔案不存在。
    # 下載時若檔案不存在，直接依照格式重新產生一份真實報表並下載。
    file_path = Path(path) if path else None
    if (not file_path) or (not file_path.exists()):
        try:
            if fmt in ("excel", "xlsx"):
                new_result = generate_report("excel")
            elif fmt == "pdf":
                new_result = generate_report("pdf")
            elif fmt in ("html", "bi"):
                new_result = generate_report("html")
            elif fmt == "csv":
                new_result = generate_report("csv")
            else:
                new_result = generate_report("excel")
            file_path = Path(new_result["file"])
            fmt = str(file_path.suffix).replace(".", "").lower()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"報表檔案不存在，且重新產生失敗：{exc}")

    media_type = "application/octet-stream"
    if fmt in ("excel", "xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "pdf":
        media_type = "application/pdf"
    elif fmt in ("html", "bi"):
        media_type = "text/html"
    elif fmt == "csv":
        media_type = "text/csv"

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )


@router.delete("/reports/{report_job_id}")
def delete_report(report_job_id: int):
    ensure_extra_schema()
    rows = fetch_all(
        "SELECT * FROM aips_report_job WHERE report_job_id = %s LIMIT 1",
        (report_job_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="查無報表")

    removed_file = _delete_report_file_if_exists(rows[0].get("file_path"))
    execute("DELETE FROM aips_report_job WHERE report_job_id = %s", (report_job_id,))
    return {
        "success": True,
        "report_job_id": report_job_id,
        "removed_file": removed_file,
        "latest": reports()
    }

@router.delete("/reports")
def delete_all_reports():
    ensure_extra_schema()
    rows = fetch_all("SELECT * FROM aips_report_job")
    removed_count = 0
    for row in rows:
        if _delete_report_file_if_exists(row.get("file_path")):
            removed_count += 1
    execute("DELETE FROM aips_report_job")
    return {
        "success": True,
        "deleted_records": len(rows),
        "removed_files": removed_count,
        "latest": reports()
    }

@router.post("/reports/cleanup-demo")
def cleanup_demo_reports():
    ensure_extra_schema()
    rows = fetch_all("""
        SELECT *
        FROM aips_report_job
        WHERE file_path IS NULL
           OR file_path LIKE '/reports/%'
           OR file_path LIKE 'reports/%'
    """)
    removed_count = 0
    for row in rows:
        if _delete_report_file_if_exists(row.get("file_path")):
            removed_count += 1
    execute("""
        DELETE FROM aips_report_job
        WHERE file_path IS NULL
           OR file_path LIKE '/reports/%'
           OR file_path LIKE 'reports/%'
    """)
    return {
        "success": True,
        "deleted_demo_records": len(rows),
        "removed_files": removed_count,
        "latest": reports()
    }


@router.get("/integrations")
def integrations():
    return _safe_list("SELECT * FROM aips_external_integration_log ORDER BY integration_id DESC LIMIT 100")

@router.post("/integrations/demo")
def create_integration_demo():
    integration_id = _safe_insert(
        """
        INSERT INTO aips_external_integration_log (target_system, direction, api_name, request_json, response_json, status, message)
        VALUES ('ERP', 'OUT', 'demoSync', '{"demo":true}'::jsonb, '{"result":"OK"}'::jsonb, 'SUCCESS', 'Demo 對外整合紀錄已建立')
        RETURNING integration_id
        """,
        "integration_id",
    )
    return {"success": True, "integration_id": integration_id, "latest": integrations()}

@router.get("/business-services")
def business_services():
    return _safe_list("SELECT * FROM aips_business_service_log ORDER BY service_log_id DESC LIMIT 100")

@router.post("/business-services/demo")
def create_business_service_demo():
    service_log_id = _safe_insert(
        """
        INSERT INTO aips_business_service_log (service_name, operation_name, operator_id, request_json, result_status, result_message)
        VALUES ('ScheduleService', 'querySuggestion', 'planner01', '{"demo":true}'::jsonb, 'SUCCESS', 'Demo 業務服務呼叫完成')
        RETURNING service_log_id
        """,
        "service_log_id",
    )
    return {"success": True, "service_log_id": service_log_id, "latest": business_services()}
