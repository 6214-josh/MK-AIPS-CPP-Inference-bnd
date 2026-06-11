from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import fetch_all, fetch_one, execute_returning_id, execute
from app.core.schema_guard import ensure_extra_schema
from app.services.run_card_ai_service import generate_run_card_ai_features, generate_dqn_suggestion

router = APIRouter()

class RunCardHeaderCreate(BaseModel):
    run_card_no: str = "MK20240069"
    production_batch_no: str = "MK20260111003"
    work_order_no: str = "WO-RUNCARD-DEMO"
    sales_order_no: Optional[str] = "SO-DEMO"
    customer_name: Optional[str] = "UMC"
    product_no: Optional[str] = "MK030001"
    material_no: Optional[str] = "3D10-260318-11"
    piece_id: Optional[str] = "A123-456-789"
    serial_no: Optional[str] = "20260401 ZH-260318"
    process_name: Optional[str] = "CNC 加工"
    process_level: Optional[str] = "低階"
    unit: Optional[str] = "mm"
    size_length: Optional[float] = 130
    size_width: Optional[float] = 130
    planned_qty: Optional[float] = 100
    due_hours: Optional[float] = 24
    priority_level: Optional[int] = 8

class RunCardDetailCreate(BaseModel):
    run_card_id: int
    sequence_no: int
    station_name: str
    station_sub_name: Optional[str] = None
    process_type: Optional[str] = None
    cnc_machine_id: Optional[str] = None
    planned_qty: Optional[float] = 100
    completed_qty: Optional[float] = 0
    good_qty: Optional[float] = 0
    ng_qty: Optional[float] = 0
    control_spec_text: Optional[str] = None
    measurement_spec_text: Optional[str] = None
    standard_cycle_time_sec: Optional[float] = None
    actual_processing_minutes: Optional[float] = None
    delay_minutes: Optional[float] = 0
    shortage_flag: Optional[bool] = False
    shortage_qty: Optional[float] = 0
    avg_power_kw: Optional[float] = None
    avg_thd_current: Optional[float] = None
    quality_risk_score: Optional[float] = 0.1
    detail_status: Optional[str] = "PENDING"

@router.get("/headers")
def headers():
    ensure_extra_schema()
    return fetch_all("""
        SELECT *
        FROM aips_run_card_header
        ORDER BY run_card_id DESC
        LIMIT 1000
    """)

@router.get("/headers/{run_card_id}")
def header(run_card_id: int):
    ensure_extra_schema()
    row = fetch_one("SELECT * FROM aips_run_card_header WHERE run_card_id = %s", (run_card_id,))
    details = fetch_all("""
        SELECT *
        FROM aips_run_card_detail
        WHERE run_card_id = %s
        ORDER BY sequence_no, run_card_detail_id
    """, (run_card_id,))
    return {"header": row, "details": details}

@router.post("/headers")
def create_header(data: RunCardHeaderCreate):
    ensure_extra_schema()
    run_card_id = execute_returning_id("""
        INSERT INTO aips_run_card_header (
            run_card_no, production_batch_no, work_order_no, sales_order_no, customer_name,
            product_no, material_no, piece_id, serial_no, process_name, process_level, unit,
            size_length, size_width, planned_qty, remaining_qty, due_date, priority_level,
            run_card_status, source_system, created_by
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW() + (%s || ' hours')::interval, %s,
            'OPEN', 'AIPS_DEMO', 'admin'
        )
        RETURNING run_card_id
    """, (
        data.run_card_no, data.production_batch_no, data.work_order_no, data.sales_order_no, data.customer_name,
        data.product_no, data.material_no, data.piece_id, data.serial_no, data.process_name, data.process_level, data.unit,
        data.size_length, data.size_width, data.planned_qty, data.planned_qty, data.due_hours, data.priority_level,
    ), "run_card_id")
    return {"success": True, "run_card_id": run_card_id}

@router.post("/details")
def create_detail(data: RunCardDetailCreate):
    ensure_extra_schema()
    detail_id = execute_returning_id("""
        INSERT INTO aips_run_card_detail (
            run_card_id, sequence_no, station_name, station_sub_name, process_type,
            cnc_machine_id, planned_qty, completed_qty, good_qty, ng_qty,
            control_spec_text, measurement_spec_text, standard_cycle_time_sec,
            actual_processing_minutes, delay_minutes, shortage_flag, shortage_qty,
            avg_power_kw, avg_thd_current, quality_risk_score, detail_status
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        RETURNING run_card_detail_id
    """, (
        data.run_card_id, data.sequence_no, data.station_name, data.station_sub_name, data.process_type,
        data.cnc_machine_id, data.planned_qty, data.completed_qty, data.good_qty, data.ng_qty,
        data.control_spec_text, data.measurement_spec_text, data.standard_cycle_time_sec,
        data.actual_processing_minutes, data.delay_minutes, data.shortage_flag, data.shortage_qty,
        data.avg_power_kw, data.avg_thd_current, data.quality_risk_score, data.detail_status,
    ), "run_card_detail_id")
    return {"success": True, "run_card_detail_id": detail_id}



def _create_demo_details_for_header(run_card_id: int):
    demo_details = [
        (1, 'CNC工序01' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-01', 'CNC', 'CNC-01', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 36, 0, False, 0, 4.25, 5.28, 0.07, 'PENDING'),
        (2, 'CNC工序02' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-02', 'CNC', 'CNC-02', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 37, 0, False, 0, 4.5, 5.56, 0.08, 'PENDING'),
        (3, 'CNC工序03' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-03', 'CNC', 'CNC-03', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 38, 0, False, 0, 4.75, 5.84, 0.09, 'PENDING'),
        (4, 'CNC工序04' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-04', 'CNC', 'CNC-04', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 39, 10, False, 0, 5.0, 6.12, 0.1, 'PENDING'),
        (5, 'CNC工序05' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-05', 'CNC', 'CNC-05', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 40, 0, True, 5, 5.25, 6.4, 0.11, 'PENDING'),
        (6, 'CNC工序06' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-06', 'CNC', 'CNC-06', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 41, 0, False, 0, 5.5, 6.68, 0.12, 'PENDING'),
        (7, 'CNC工序07' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-07', 'CNC', 'CNC-07', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 42, 0, False, 0, 5.75, 6.96, 0.13, 'PENDING'),
        (8, 'CNC工序08' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-08', 'CNC', 'CNC-08', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 43, 10, False, 0, 6.0, 7.24, 0.14, 'PENDING'),
        (9, 'CNC工序09' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-09', 'CNC', 'CNC-09', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 44, 0, False, 0, 6.25, 7.52, 0.15, 'PENDING'),
        (10, 'CNC工序10' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-10', 'CNC', 'CNC-10', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 45, 0, True, 5, 6.5, 7.8, 0.16, 'PENDING'),
        (11, 'CNC工序11' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-11', 'CNC', 'CNC-11', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 46, 0, False, 0, 6.75, 8.08, 0.17, 'PENDING'),
        (12, 'CNC工序12' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-12', 'CNC', 'CNC-12', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 47, 10, False, 0, 7.0, 8.36, 0.18, 'PENDING'),
        (13, 'CNC工序13' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-13', 'CNC', 'CNC-13', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 48, 0, False, 0, 7.25, 8.64, 0.19, 'PENDING'),
        (14, 'CNC工序14' if 'CNC工序'.endswith('工序') else 'CNC工序', 'CNC-STEP-14', 'CNC', 'CNC-14', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 49, 0, False, 0, 7.5, 8.92, 0.2, 'PENDING'),
    ]

    for d in demo_details:
        existed = fetch_one("""
            SELECT run_card_detail_id
            FROM aips_run_card_detail
            WHERE run_card_id = %s AND sequence_no = %s
            LIMIT 1
        """, (run_card_id, d[0]))
        if existed:
            continue
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
        created += 1
    return created

@router.post("/details/auto-create")
def auto_create_details():
    """
    FIX34：補齊 React 前端「補齊單身」按鈕呼叫的 API。
    針對所有沒有單身的流程卡單頭，自動建立 8 筆標準流程卡單身。
    """
    ensure_extra_schema()
    headers = fetch_all("""
        SELECT h.run_card_id
        FROM aips_run_card_header h
        LEFT JOIN aips_run_card_detail d ON d.run_card_id = h.run_card_id
        GROUP BY h.run_card_id
        HAVING COUNT(d.run_card_detail_id) = 0
        ORDER BY h.run_card_id DESC
    """)
    total = 0
    for row in headers:
        total += _create_demo_details_for_header(row["run_card_id"])
    return {"success": True, "created": total, "headers": len(headers)}

@router.post("/demo")
def create_demo_run_card():
    ensure_extra_schema()
    run_card_id = execute_returning_id("""
        INSERT INTO aips_run_card_header (
            run_card_no, production_batch_no, work_order_no, sales_order_no, customer_name,
            product_no, material_no, piece_id, serial_no, process_name, process_level, unit,
            size_length, size_width, planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
            due_date, priority_level, run_card_status, source_system, source_file_name, created_by
        )
        VALUES (
            'MK20240069-' || EXTRACT(EPOCH FROM NOW())::bigint,
            'MK20260111003',
            'WO-RUNCARD-' || EXTRACT(EPOCH FROM NOW())::bigint,
            'SO-DEMO-001',
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
            'EXCEL_SAMPLE',
            '銘金(生產流程卡)模板樣本_2026-0601.xlsx',
            'admin'
        )
        RETURNING run_card_id
    """, (), "run_card_id")

    demo_details = [
        (1, 'CNC加工01' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-01', 'CNC', 'CNC-01', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 36, 0, False, 0, 4.25, 5.28, 0.07, 'PENDING'),
        (2, 'CNC加工02' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-02', 'CNC', 'CNC-02', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 37, 0, False, 0, 4.5, 5.56, 0.08, 'PENDING'),
        (3, 'CNC加工03' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-03', 'CNC', 'CNC-03', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 38, 0, False, 0, 4.75, 5.84, 0.09, 'PENDING'),
        (4, 'CNC加工04' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-04', 'CNC', 'CNC-04', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 39, 10, False, 0, 5.0, 6.12, 0.1, 'PENDING'),
        (5, 'CNC加工05' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-05', 'CNC', 'CNC-05', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 40, 0, True, 5, 5.25, 6.4, 0.11, 'PENDING'),
        (6, 'CNC加工06' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-06', 'CNC', 'CNC-06', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 41, 0, False, 0, 5.5, 6.68, 0.12, 'PENDING'),
        (7, 'CNC加工07' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-07', 'CNC', 'CNC-07', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 42, 0, False, 0, 5.75, 6.96, 0.13, 'PENDING'),
        (8, 'CNC加工08' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-08', 'CNC', 'CNC-08', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 43, 10, False, 0, 6.0, 7.24, 0.14, 'PENDING'),
        (9, 'CNC加工09' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-09', 'CNC', 'CNC-09', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 44, 0, False, 0, 6.25, 7.52, 0.15, 'PENDING'),
        (10, 'CNC加工10' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-10', 'CNC', 'CNC-10', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 45, 0, True, 5, 6.5, 7.8, 0.16, 'PENDING'),
        (11, 'CNC加工11' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-11', 'CNC', 'CNC-11', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 46, 0, False, 0, 6.75, 8.08, 0.17, 'PENDING'),
        (12, 'CNC加工12' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-12', 'CNC', 'CNC-12', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 47, 10, False, 0, 7.0, 8.36, 0.18, 'PENDING'),
        (13, 'CNC加工13' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-13', 'CNC', 'CNC-13', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 48, 0, False, 0, 7.25, 8.64, 0.19, 'PENDING'),
        (14, 'CNC加工14' if 'CNC加工'.endswith('工序') else 'CNC加工', 'CNC-STEP-14', 'CNC', 'CNC-14', 100, 0, 'CNC 製程參數 / 工序關係檢查', 'CNC 自動量測回傳', 49, 0, False, 0, 7.5, 8.92, 0.2, 'PENDING'),
    ]

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

    return {"success": True, "run_card_id": run_card_id, "message": "已建立生產流程卡 Demo"}

@router.get("/features")
def features():
    ensure_extra_schema()
    return fetch_all("""
        SELECT *
        FROM aips_run_card_ai_feature
        ORDER BY feature_id DESC
        LIMIT 1000
    """)

@router.post("/features/generate")
def generate_features():
    ensure_extra_schema()
    result = generate_run_card_ai_features()
    return result

@router.post("/dqn/suggest")
def dqn_suggest():
    ensure_extra_schema()
    result = generate_dqn_suggestion()
    return result


@router.get("/dqn/actions")
def dqn_actions():
    ensure_extra_schema()
    return fetch_all("""
        SELECT
            action_id,
            action_time,
            work_order_no,
            product_no,
            COALESCE(suggested_cnc_machine_id, original_cnc_machine_id) AS cnc_machine_id,
            action_type,
            action_name,
            action_reason AS reason,
            expected_delay_reduction_hours,
            expected_oee_improvement_rate,
            expected_shortage_risk_reduction,
            action_confidence_score,
            action_status
        FROM aips_dqn_action_log
        ORDER BY action_id DESC
        LIMIT 1000
    """)



@router.get("/dqn/actions/summary")
def dqn_actions_summary():
    ensure_extra_schema()
    total = fetch_one("SELECT COUNT(*) AS total_count FROM aips_dqn_action_log")
    latest = fetch_one("""
        SELECT action_id, action_time, work_order_no, action_name, action_status
        FROM aips_dqn_action_log
        ORDER BY action_id DESC
        LIMIT 1
    """)
    return {
        "total_count": int(total["total_count"]) if total else 0,
        "latest": latest,
        "note": "total_count 是資料庫全部 DQN 建議筆數；/dqn/actions 表格最多回傳最近 1000 筆。"
    }


@router.get("/ai/status")
def ai_status():
    ensure_extra_schema()
    status = {
        "pytorch": False,
        "torch_version": None,
        "statsmodels": False,
        "statsmodels_version": None,
        "sklearn": False,
        "sklearn_version": None,
        "note": "pytorch=True 且 statsmodels=True 時，系統會使用真 PyTorch LSTM / DQN 與 statsmodels ARIMA；資料不足時會降級。"
    }
    try:
        import torch
        status["pytorch"] = True
        status["torch_version"] = torch.__version__
    except Exception as exc:
        status["pytorch_error"] = str(exc)

    try:
        import statsmodels
        status["statsmodels"] = True
        status["statsmodels_version"] = statsmodels.__version__
    except Exception as exc:
        status["statsmodels_error"] = str(exc)

    try:
        import sklearn
        status["sklearn"] = True
        status["sklearn_version"] = sklearn.__version__
    except Exception as exc:
        status["sklearn_error"] = str(exc)

    return status
