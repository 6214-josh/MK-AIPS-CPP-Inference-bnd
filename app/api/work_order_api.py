from fastapi import APIRouter
from app.core.database import fetch_all, execute_returning_id
from app.schemas.work_order import WorkOrderSnapshotCreate

router = APIRouter()

@router.post("/snapshots")
def create_snapshot(data: WorkOrderSnapshotCreate):
    snapshot_id = execute_returning_id(
        """
        INSERT INTO work_order_progress_snapshot (
            snapshot_time, work_order_no, sales_order_no, customer_id,
            product_no, product_name, process_code,
            planned_qty, completed_qty, good_qty, ng_qty, remaining_qty,
            due_date, priority_level, current_process_status,
            assigned_cnc_machine_id, estimated_remaining_hours, delay_risk_flag
        )
        VALUES (
            NOW(), %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        RETURNING snapshot_id
        """,
        (
            data.work_order_no, data.sales_order_no, data.customer_id,
            data.product_no, data.product_name, data.process_code,
            data.planned_qty, data.completed_qty, data.good_qty, data.ng_qty, data.remaining_qty,
            data.due_date, data.priority_level, data.current_process_status,
            data.assigned_cnc_machine_id, data.estimated_remaining_hours, data.delay_risk_flag,
        ),
        "snapshot_id",
    )
    return {"snapshot_id": snapshot_id}

@router.get("/snapshots/latest")
def latest(limit: int = 100):
    return fetch_all("SELECT * FROM work_order_progress_snapshot ORDER BY snapshot_id DESC LIMIT %s", (limit,))
