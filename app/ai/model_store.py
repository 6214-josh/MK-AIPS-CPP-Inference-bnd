from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"

LSTM_MODEL_PATH = MODEL_DIR / "lstm_quantity_forecast.pt"
DQN_MODEL_PATH = MODEL_DIR / "dqn_scheduler_policy.pt"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

if nn is not None:
    class QuantityLstmModel(nn.Module):
        def __init__(self, input_size: int = 8, hidden_size: int = 32, output_size: int = 3):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                batch_first=True,
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Linear(32, output_size),
            )

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])

    class DqnPolicyModel(nn.Module):
        def __init__(self, state_size: int = 12, action_size: int = 5):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_size, 64),
                nn.ReLU(),
                nn.Linear(64, 64),
                nn.ReLU(),
                nn.Linear(64, action_size),
            )

        def forward(self, x):
            return self.net(x)
else:
    QuantityLstmModel = None
    DqnPolicyModel = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_model_dir() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR


def _read_metadata() -> Dict[str, Any]:
    ensure_model_dir()
    if not METADATA_PATH.exists():
        return {}

    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_model_dir()
    METADATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def _file_info(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "size_bytes": 0,
            "updated_at": None,
        }

    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def get_model_status() -> Dict[str, Any]:
    metadata = _read_metadata()

    return {
        "model_dir": str(ensure_model_dir()),
        "torch_available": torch is not None,
        "cuda_available": bool(torch.cuda.is_available()) if torch is not None else False,
        "cuda_device": (
            torch.cuda.get_device_name(0)
            if torch is not None and torch.cuda.is_available()
            else None
        ),
        "lstm_quantity_forecast": {
            **_file_info(LSTM_MODEL_PATH),
            "description": "LSTM 產量預測模型檔",
        },
        "dqn_scheduler_policy": {
            **_file_info(DQN_MODEL_PATH),
            "description": "DQN 排程 Action Policy 模型檔",
        },
        "metadata": {
            **_file_info(METADATA_PATH),
            "content": metadata,
        },
    }


def train_and_save_demo_models() -> Dict[str, Any]:
    """
    Demo 訓練並保存模型檔。
    正式版可改成讀取 PostgreSQL 歷史資料長時間訓練。
    """
    if torch is None or nn is None:
        raise RuntimeError("PyTorch 尚未安裝，請先安裝 torch。")

    ensure_model_dir()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    lstm = QuantityLstmModel().to(device)
    dqn = DqnPolicyModel().to(device)

    lstm_optimizer = torch.optim.Adam(lstm.parameters(), lr=0.001)
    dqn_optimizer = torch.optim.Adam(dqn.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()

    for _ in range(12):
        x = torch.rand(16, 6, 8, device=device)
        y = torch.rand(16, 3, device=device) * torch.tensor(
            [120.0, 116.0, 6.0],
            device=device,
        )

        pred = lstm(x)
        loss = loss_fn(pred, y)

        lstm_optimizer.zero_grad()
        loss.backward()
        lstm_optimizer.step()

    for _ in range(12):
        state = torch.rand(32, 12, device=device)
        target_q = torch.rand(32, 5, device=device) * 100

        q_values = dqn(state)
        loss = loss_fn(q_values, target_q)

        dqn_optimizer.zero_grad()
        loss.backward()
        dqn_optimizer.step()

    torch.save(
        {
            "model_type": "QuantityLstmModel",
            "input_size": 8,
            "hidden_size": 32,
            "output_size": 3,
            "state_dict": lstm.state_dict(),
            "saved_at": _now(),
            "device": str(device),
            "outputs": [
                "predicted_output_qty",
                "predicted_good_qty",
                "predicted_ng_qty",
            ],
        },
        LSTM_MODEL_PATH,
    )

    torch.save(
        {
            "model_type": "DqnPolicyModel",
            "state_size": 12,
            "action_size": 5,
            "state_dict": dqn.state_dict(),
            "saved_at": _now(),
            "device": str(device),
            "actions": [
                "PROCESS_NOW",
                "WAIT_PREVIOUS_STEP",
                "REQUEST_MATERIAL",
                "PAUSE_OR_MAINTAIN",
                "CHANGE_CNC",
            ],
        },
        DQN_MODEL_PATH,
    )

    _write_metadata(
        {
            "saved_at": _now(),
            "mode": "DEMO_PERSISTED_MODELS",
            "description": "Demo 版已將 LSTM / DQN 以 PyTorch .pt 檔落地保存。",
            "model_dir": str(MODEL_DIR),
            "torch_version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device": (
                torch.cuda.get_device_name(0)
                if torch.cuda.is_available()
                else None
            ),
            "files": {
                "lstm_quantity_forecast": str(LSTM_MODEL_PATH),
                "dqn_scheduler_policy": str(DQN_MODEL_PATH),
                "metadata": str(METADATA_PATH),
            },
        }
    )

    return get_model_status()
