from pathlib import Path
import json
import torch
import torch.nn as nn
import torch.nn.utils.prune as prune

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"

DQN_MODEL_PATH = MODEL_DIR / "dqn_scheduler_policy.pt"
LSTM_MODEL_PATH = MODEL_DIR / "lstm_quantity_forecast.pt"

DQN_PRUNED_PATH = MODEL_DIR / "dqn_scheduler_policy_pruned.pt"
LSTM_PRUNED_PATH = MODEL_DIR / "lstm_quantity_forecast_pruned.pt"
REPORT_PATH = MODEL_DIR / "model_pruning_report.json"


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


def count_sparsity(model):
    total = 0
    zero = 0

    for _, param in model.named_parameters():
        data = param.detach()
        total += data.numel()
        zero += torch.sum(data == 0).item()

    return {
        "total_params": int(total),
        "zero_params": int(zero),
        "sparsity_rate": round(zero / total, 4) if total else 0,
    }


def prune_linear_layers(model, amount=0.30):
    for module in model.modules():
        if isinstance(module, nn.Linear):
            prune.l1_unstructured(module, name="weight", amount=amount)
            prune.remove(module, "weight")


def prune_lstm_weights(model, amount=0.15):
    for module in model.modules():
        if isinstance(module, nn.LSTM):
            for param_name, _ in list(module.named_parameters()):
                if "weight" in param_name:
                    prune.l1_unstructured(module, name=param_name, amount=amount)
                    prune.remove(module, param_name)


def prune_dqn():
    checkpoint = torch.load(DQN_MODEL_PATH, map_location="cpu")

    model = DqnPolicyModel(
        state_size=int(checkpoint.get("state_size", 12)),
        action_size=int(checkpoint.get("action_size", 5)),
    )
    model.load_state_dict(checkpoint["state_dict"])

    before = count_sparsity(model)
    prune_linear_layers(model, amount=0.30)
    after = count_sparsity(model)

    torch.save(
        {
            **checkpoint,
            "state_dict": model.state_dict(),
            "pruned": True,
            "prune_method": "l1_unstructured",
            "prune_amount": 0.30,
        },
        DQN_PRUNED_PATH,
    )

    return {
        "model": "DQN",
        "source": str(DQN_MODEL_PATH),
        "output": str(DQN_PRUNED_PATH),
        "before": before,
        "after": after,
        "source_size_bytes": DQN_MODEL_PATH.stat().st_size,
        "output_size_bytes": DQN_PRUNED_PATH.stat().st_size,
    }


def prune_lstm():
    checkpoint = torch.load(LSTM_MODEL_PATH, map_location="cpu")

    model = QuantityLstmModel(
        input_size=int(checkpoint.get("input_size", 8)),
        hidden_size=int(checkpoint.get("hidden_size", 32)),
        output_size=int(checkpoint.get("output_size", 3)),
    )
    model.load_state_dict(checkpoint["state_dict"])

    before = count_sparsity(model)
    prune_lstm_weights(model, amount=0.15)
    prune_linear_layers(model, amount=0.20)
    after = count_sparsity(model)

    torch.save(
        {
            **checkpoint,
            "state_dict": model.state_dict(),
            "pruned": True,
            "prune_method": "l1_unstructured",
            "lstm_prune_amount": 0.15,
            "fc_prune_amount": 0.20,
        },
        LSTM_PRUNED_PATH,
    )

    return {
        "model": "LSTM",
        "source": str(LSTM_MODEL_PATH),
        "output": str(LSTM_PRUNED_PATH),
        "before": before,
        "after": after,
        "source_size_bytes": LSTM_MODEL_PATH.stat().st_size,
        "output_size_bytes": LSTM_PRUNED_PATH.stat().st_size,
    }


def main():
    if not DQN_MODEL_PATH.exists() or not LSTM_MODEL_PATH.exists():
        raise FileNotFoundError("請先產生 models/lstm_quantity_forecast.pt 與 models/dqn_scheduler_policy.pt")

    report = {
        "dqn": prune_dqn(),
        "lstm": prune_lstm(),
        "important_note": (
            "PyTorch pruning 會把權重變成 0，但 .pt 檔案大小不一定明顯變小。"
            "真正加速通常還要搭配 sparse inference、quantization、ONNX 或 TensorRT。"
        ),
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
