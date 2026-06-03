from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MeterRawCreate(BaseModel):
    meter_id: Optional[str] = None
    cnc_machine_id: str
    device_ip: Optional[str] = None
    mqtt_topic: Optional[str] = None
    collect_time: Optional[datetime] = None
    voltage_r: Optional[float] = None
    voltage_s: Optional[float] = None
    voltage_t: Optional[float] = None
    current_r: Optional[float] = None
    current_s: Optional[float] = None
    current_t: Optional[float] = None
    power_kw: Optional[float] = None
    power_kwh: Optional[float] = None
    power_factor: Optional[float] = None
    frequency_hz: Optional[float] = None
    demand_kw: Optional[float] = None
    thd_voltage: Optional[float] = None
    thd_current: Optional[float] = None
    phase_imbalance_rate: Optional[float] = None
