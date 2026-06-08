from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.schema_guard import ensure_extra_schema

from app.api import auth_api
from app.api import hardware_simulator_api
from app.api import dashboard_api
from app.api import meter_api
from app.api import work_order_api
from app.api import inventory_api
from app.api import state_api
from app.api import dqn_api
from app.api import dqn_explain_api
from app.api import prediction_api
from app.api import reward_api
from app.api import architecture_api
from app.api import run_card_api
from app.api import model_api
from app.api import model_optimization_api
from app.api import data_engineering_api
from app.api import erp_simulator_api
from app.api import shortage_priority_dqn_api
from app.api import cnc_daily_schedule_api

app = FastAPI(title="AIPS / MK-AIPS AI Scheduling API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    ensure_extra_schema()

app.include_router(auth_api.router, prefix="/api/auth", tags=["auth"])
app.include_router(hardware_simulator_api.router, prefix="/api/hardware-simulator", tags=["hardware-simulator"])
app.include_router(dashboard_api.router, prefix="/api", tags=["dashboard"])
app.include_router(meter_api.router, prefix="/api/meter", tags=["meter"])
app.include_router(work_order_api.router, prefix="/api/work-orders", tags=["work-orders"])
app.include_router(inventory_api.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(state_api.router, prefix="/api/aips/states", tags=["aips-state"])
app.include_router(dqn_api.router, prefix="/api/aips/dqn", tags=["dqn"])
app.include_router(dqn_explain_api.router, prefix="/api/aips/dqn-explain", tags=["dqn-explain"])
app.include_router(prediction_api.router, prefix="/api/aips/predictions", tags=["prediction"])
app.include_router(reward_api.router, prefix="/api/aips/rewards", tags=["reward"])
app.include_router(architecture_api.router, prefix="/api/architecture", tags=["architecture"])

app.include_router(run_card_api.router, prefix="/api/run-cards", tags=["run-cards"])

app.include_router(model_api.router, prefix="/api/aips/models", tags=["aips-models"])

app.include_router(model_optimization_api.router, prefix="/api/aips/model-optimization", tags=["aips-model-optimization"])
app.include_router(data_engineering_api.router, prefix="/api/aips/data-engineering", tags=["aips-data-engineering"])
app.include_router(erp_simulator_api.router, prefix="/api/erp-simulator", tags=["erp-simulator"])

app.include_router(shortage_priority_dqn_api.router, prefix="/api/aips/shortage-priority-dqn", tags=["shortage-priority-dqn"])
app.include_router(cnc_daily_schedule_api.router, prefix="/api/aips/cnc-daily-schedule", tags=["cnc-daily-schedule"])
