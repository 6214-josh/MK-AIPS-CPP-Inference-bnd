from pathlib import Path
import json
import torch
import torch.nn as nn
import torch.ao.quantization as quantization

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"

DQN_PT = MODEL_DIR / "dqn_scheduler_policy.pt"
DQN_INT8_PT = MODEL_DIR / "dqn_scheduler_policy_int8.pt"
DQN_ONNX = MODEL_DIR / "dqn_scheduler_policy.onnx"

LSTM_PT = MODEL_DIR / "lstm_quantity_forecast.pt"
LSTM_ONNX = MODEL_DIR / "lstm_quantity_forecast.onnx"

REPORT = MODEL_DIR / "model_export_report.json"


class DqnPolicyModel(nn.Module):
    def __init__(self, state_size=12, action_size=5):
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


class QuantityLstmModel(nn.Module):
    def __init__(self, input_size=8, hidden_size=32, output_size=3):
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


def file_info(path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def load_dqn():
    checkpoint = torch.load(DQN_PT, map_location="cpu")
    model = DqnPolicyModel(
        state_size=int(checkpoint.get("state_size", 12)),
        action_size=int(checkpoint.get("action_size", 5)),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


def load_lstm():
    checkpoint = torch.load(LSTM_PT, map_location="cpu")
    model = QuantityLstmModel(
        input_size=int(checkpoint.get("input_size", 8)),
        hidden_size=int(checkpoint.get("hidden_size", 32)),
        output_size=int(checkpoint.get("output_size", 3)),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


def quantize_dqn_dynamic():
    model, checkpoint = load_dqn()

    q_model = quantization.quantize_dynamic(
        model,
        {nn.Linear},
        dtype=torch.qint8,
    )

    torch.save(
        {
            **checkpoint,
            "state_dict": q_model.state_dict(),
            "quantized": True,
            "quantization_method": "dynamic_int8",
        },
        DQN_INT8_PT,
    )

    return {
        "source": file_info(DQN_PT),
        "output": file_info(DQN_INT8_PT),
    }


def export_dqn_onnx():
    model, _ = load_dqn()
    dummy_input = torch.randn(1, 12)

    torch.onnx.export(
        model,
        dummy_input,
        DQN_ONNX,
        input_names=["state"],
        output_names=["q_values"],
        dynamic_axes={
            "state": {0: "batch_size"},
            "q_values": {0: "batch_size"},
        },
        opset_version=17,
        dynamo=False,
    )

    return file_info(DQN_ONNX)


def export_lstm_onnx():
    model, _ = load_lstm()
    dummy_input = torch.randn(1, 6, 8)

    torch.onnx.export(
        model,
        dummy_input,
        LSTM_ONNX,
        input_names=["sequence_features"],
        output_names=["quantity_prediction"],
        dynamic_axes={
            "sequence_features": {0: "batch_size"},
            "quantity_prediction": {0: "batch_size"},
        },
        opset_version=17,
        dynamo=False,
    )

    return file_info(LSTM_ONNX)


def main():
    if not DQN_PT.exists() or not LSTM_PT.exists():
        raise FileNotFoundError("請先產生 .pt 模型檔，再執行量化與 ONNX 匯出。")

    report = {
        "dqn_dynamic_int8": quantize_dqn_dynamic(),
        "dqn_onnx": export_dqn_onnx(),
        "lstm_onnx": export_lstm_onnx(),
        "next_step": "Use ONNX Runtime to test .onnx, then convert ONNX to TensorRT engine.",
    }

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
