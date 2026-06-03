from pydantic import BaseModel
from typing import Optional

class InventorySnapshotCreate(BaseModel):
    cnc_machine_id: str
    line_side_location_id: Optional[str] = None
    material_no: str
    material_name: Optional[str] = None
    lot_no: Optional[str] = None
    current_qty: Optional[float] = 0
    reserved_qty: Optional[float] = 0
    safety_stock_qty: Optional[float] = 0
    source_system: Optional[str] = "WMS"
