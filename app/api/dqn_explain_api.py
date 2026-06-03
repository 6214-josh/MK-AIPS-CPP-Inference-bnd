from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class DqnInput(BaseModel):
    cnc_id: str
    current_step: str
    next_step: Optional[str] = None
    step_ready: bool = True
    step_dependency_done: bool = True

    due_remaining_hours: float = 8.0
    estimated_process_hours: float = 4.0
    cnc_oee: float = 0.82
    shortage_risk: float = 0.10
    power_thd_risk: float = 0.12
    quality_risk: float = 0.10
    setup_change_minutes: float = 20.0

class DqnExplainRequest(BaseModel):
    items: List[DqnInput]

ACTIONS = [
    {
        "action_code": "PROCESS_NOW",
        "action_name": "立即加工",
        "trigger": "步驟前置完成、交期壓力高、機台效率佳、風險低",
        "event": "派工到 CNC，產生加工指令"
    },
    {
        "action_code": "WAIT_PREVIOUS_STEP",
        "action_name": "等待前工序",
        "trigger": "目前步驟尚未滿足前置關係，例如步驟 2 必須等步驟 1 完成",
        "event": "暫不派工，維持 WIP 等待"
    },
    {
        "action_code": "REQUEST_MATERIAL",
        "action_name": "觸發補料",
        "trigger": "線邊庫缺料風險高",
        "event": "通知 WMS / 人工物流補料"
    },
    {
        "action_code": "PAUSE_OR_MAINTAIN",
        "action_name": "停機 / 維護檢查",
        "trigger": "智慧電表 THD / 功率異常或品質風險高",
        "event": "暫停加工並發出機台檢查事件"
    },
    {
        "action_code": "CHANGE_CNC",
        "action_name": "換 CNC 機台",
        "trigger": "目前 CNC 效率低、換線成本可接受、其他 CNC 更適合",
        "event": "改派到其他 CNC，更新排程建議"
    },
    {
        "action_code": "INCREASE_PRIORITY",
        "action_name": "提高製令優先權",
        "trigger": "預估加工時間大於剩餘交期，延遲風險高",
        "event": "提升工單 priority，插入較前排程"
    },
]

VARIABLES = [
    {
        "name": "due_remaining_hours",
        "label": "交期剩餘小時",
        "meaning": "越少代表越急，DQN 會提高立即加工或提高優先權的 Q 值。",
        "source": "ERP 製令單交期 + 目前時間"
    },
    {
        "name": "estimated_process_hours",
        "label": "預估加工小時",
        "meaning": "由 LSTM / ARIMA 預測此站加工時間，若大於交期剩餘時間，延遲懲罰會提高。",
        "source": "流程卡單身、歷史加工時間、CNC 狀態"
    },
    {
        "name": "cnc_oee",
        "label": "CNC OEE / 可用效率",
        "meaning": "越高代表越適合加工；太低時 DQN 會考慮換機台或維護。",
        "source": "CNC 智慧電表、稼動率、停機紀錄"
    },
    {
        "name": "shortage_risk",
        "label": "缺料風險",
        "meaning": "越高代表線邊庫不足，DQN 會傾向補料而非立即加工。",
        "source": "WMS 線邊庫存、BOM 用量、補料 ETA"
    },
    {
        "name": "power_thd_risk",
        "label": "電力 / THD 風險",
        "meaning": "越高代表加工可能不穩或機台異常，DQN 會傾向停機檢查。",
        "source": "CNC 智慧電表 kW、電流、THD"
    },
    {
        "name": "quality_risk",
        "label": "品質風險",
        "meaning": "越高代表可能加工不良，DQN 會傾向暫停或 QC 覆核。",
        "source": "流程卡量測值、歷史不良率、加工參數"
    },
    {
        "name": "step_dependency_done",
        "label": "工序前置完成",
        "meaning": "步驟 2 必須等步驟 1；若前置未完成，立即加工 reward 會大幅扣分。",
        "source": "生產流程卡單身 sequence_no / 工序關係"
    },
]

def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))

def score_actions(item: DqnInput):
    due_pressure = clamp((item.estimated_process_hours - item.due_remaining_hours) / max(item.estimated_process_hours, 1.0) + 0.5)
    oee_good = clamp(item.cnc_oee)
    shortage = clamp(item.shortage_risk)
    power = clamp(item.power_thd_risk)
    quality = clamp(item.quality_risk)
    dependency_penalty = 0.0 if item.step_dependency_done and item.step_ready else 1.0
    setup_penalty = clamp(item.setup_change_minutes / 120.0)

    rewards = {
        "PROCESS_NOW": (
            35 * oee_good
            + 25 * due_pressure
            + 20 * (1 - shortage)
            + 10 * (1 - power)
            + 10 * (1 - quality)
            - 80 * dependency_penalty
        ),
        "WAIT_PREVIOUS_STEP": (
            80 * dependency_penalty
            + 10 * (1 - due_pressure)
            - 10 * shortage
        ),
        "REQUEST_MATERIAL": (
            75 * shortage
            + 10 * due_pressure
            - 5 * dependency_penalty
        ),
        "PAUSE_OR_MAINTAIN": (
            45 * power
            + 35 * quality
            + 10 * (1 - oee_good)
            - 10 * due_pressure
        ),
        "CHANGE_CNC": (
            35 * (1 - oee_good)
            + 25 * due_pressure
            + 20 * power
            - 20 * setup_penalty
            - 20 * dependency_penalty
        ),
        "INCREASE_PRIORITY": (
            70 * due_pressure
            + 10 * (1 - shortage)
            - 15 * dependency_penalty
        ),
    }

    normalized = {k: round(clamp(v / 100.0) * 100, 2) for k, v in rewards.items()}
    best_action = max(normalized.items(), key=lambda kv: kv[1])[0]

    explain = {
        "due_pressure": round(due_pressure, 4),
        "oee_good": round(oee_good, 4),
        "shortage_risk": round(shortage, 4),
        "power_thd_risk": round(power, 4),
        "quality_risk": round(quality, 4),
        "dependency_penalty": round(dependency_penalty, 4),
        "setup_penalty": round(setup_penalty, 4),
    }

    return {
        "cnc_id": item.cnc_id,
        "current_step": item.current_step,
        "next_step": item.next_step,
        "input_state": item.model_dump(),
        "state_vector": [
            round(item.due_remaining_hours, 4),
            round(item.estimated_process_hours, 4),
            round(item.cnc_oee, 4),
            round(item.shortage_risk, 4),
            round(item.power_thd_risk, 4),
            round(item.quality_risk, 4),
            1 if item.step_dependency_done else 0,
        ],
        "reward_scores": normalized,
        "best_action": best_action,
        "best_action_name": next(a["action_name"] for a in ACTIONS if a["action_code"] == best_action),
        "explain": explain,
    }

def demo_items():
    return [
        DqnInput(
            cnc_id="CNC-01",
            current_step="步驟1：粗加工",
            next_step="步驟2：精加工",
            step_ready=True,
            step_dependency_done=True,
            due_remaining_hours=5,
            estimated_process_hours=4,
            cnc_oee=0.88,
            shortage_risk=0.08,
            power_thd_risk=0.10,
            quality_risk=0.12,
            setup_change_minutes=15,
        ),
        DqnInput(
            cnc_id="CNC-02",
            current_step="步驟2：精加工",
            next_step="步驟3：檢驗",
            step_ready=False,
            step_dependency_done=False,
            due_remaining_hours=8,
            estimated_process_hours=3,
            cnc_oee=0.80,
            shortage_risk=0.15,
            power_thd_risk=0.12,
            quality_risk=0.10,
            setup_change_minutes=20,
        ),
        DqnInput(
            cnc_id="CNC-03",
            current_step="步驟3：二次加工",
            next_step="步驟4：入庫",
            step_ready=True,
            step_dependency_done=True,
            due_remaining_hours=2,
            estimated_process_hours=4,
            cnc_oee=0.58,
            shortage_risk=0.70,
            power_thd_risk=0.62,
            quality_risk=0.35,
            setup_change_minutes=45,
        ),
    ]

@router.get("/overview")
def overview():
    items = demo_items()
    results = [score_actions(item) for item in items]
    return {
        "title": "DQN CNC 排程決策說明",
        "purpose": "說明 DQN 如何接收 CNC / ERP / WMS / 流程卡變數，計算 Reward，並決定加工、補料、停機、換機台或提高優先權。",
        "variables": VARIABLES,
        "actions": ACTIONS,
        "reward_formula": {
            "PROCESS_NOW": "35*OEE + 25*交期壓力 + 20*(1-缺料) + 10*(1-電力風險) + 10*(1-品質風險) - 80*前置未完成",
            "WAIT_PREVIOUS_STEP": "80*前置未完成 + 10*(1-交期壓力) - 10*缺料",
            "REQUEST_MATERIAL": "75*缺料風險 + 10*交期壓力 - 5*前置未完成",
            "PAUSE_OR_MAINTAIN": "45*電力風險 + 35*品質風險 + 10*(1-OEE) - 10*交期壓力",
            "CHANGE_CNC": "35*(1-OEE) + 25*交期壓力 + 20*電力風險 - 20*換線成本 - 20*前置未完成",
            "INCREASE_PRIORITY": "70*交期壓力 + 10*(1-缺料) - 15*前置未完成",
        },
        "step_rule": "若流程卡步驟是 1→2→3，後一步必須等前一步完成；若三台 CNC 可平行加工，DQN 會比較每台 CNC 的 reward / Q value，再選分數最高 action。",
        "demo_results": results,
    }

@router.post("/simulate")
def simulate(req: DqnExplainRequest):
    return {
        "results": [score_actions(item) for item in req.items]
    }
