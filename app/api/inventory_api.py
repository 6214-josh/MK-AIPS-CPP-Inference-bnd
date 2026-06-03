from fastapi import APIRouter
from app.core.database import fetch_all, execute_returning_id
from app.schemas.inventory import InventorySnapshotCreate

router = APIRouter()

@router.post("/snapshots")
def create_snapshot(data: InventorySnapshotCreate):
    available_qty = (data.current_qty or 0) - (data.reserved_qty or 0)
    shortage_qty = max((data.safety_stock_qty or 0) - available_qty, 0)
    shortage_flag = shortage_qty > 0
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
            NOW(), %s
        )
        RETURNING snapshot_id
        """,
        (
            data.cnc_machine_id, data.line_side_location_id,
            data.material_no, data.material_name, data.lot_no,
            data.current_qty, data.reserved_qty, available_qty, data.safety_stock_qty,
            shortage_flag, shortage_qty, shortage_flag,
            data.source_system,
        ),
        "snapshot_id",
    )
    return {"snapshot_id": snapshot_id, "shortage_flag": shortage_flag, "shortage_qty": shortage_qty}

@router.get("/snapshots/latest")
def latest(limit: int = 100):
    return fetch_all("SELECT * FROM line_side_inventory_snapshot ORDER BY snapshot_id DESC LIMIT %s", (limit,))
