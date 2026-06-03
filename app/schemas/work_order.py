from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class WorkOrderSnapshotCreate(BaseModel):
    work_order_no: str
    sales_order_no: Optional[str] = None
    customer_id: Optional[str] = None
    product_no: Optional[str] = None
    product_name: Optional[str] = None
    process_code: Optional[str] = None
    planned_qty: Optional[float] = 0
    completed_qty: Optional[float] = 0
    good_qty: Optional[float] = 0
    ng_qty: Optional[float] = 0
    remaining_qty: Optional[float] = 0
    due_date: Optional[datetime] = None
    priority_level: Optional[int] = 5
    current_process_status: Optional[str] = "PROCESSING"
    assigned_cnc_machine_id: Optional[str] = None
    estimated_remaining_hours: Optional[float] = 0
    delay_risk_flag: Optional[bool] = False
