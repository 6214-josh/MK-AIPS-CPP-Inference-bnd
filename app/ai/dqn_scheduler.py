import random
import numpy as np

ACTIONS = [
    "KEEP_CURRENT_SCHEDULE",
    "REQUEST_REPLENISHMENT",
    "INCREASE_ORDER_PRIORITY",
    "REQUEST_MAINTENANCE_CHECK",
    "QUALITY_HOLD",
    "CHANGE_CNC_MACHINE",
]

ACTION_NAMES = {
    "KEEP_CURRENT_SCHEDULE": "維持目前排程",
    "REQUEST_REPLENISHMENT": "提前補料",
    "INCREASE_ORDER_PRIORITY": "提高製令優先順序",
    "REQUEST_MAINTENANCE_CHECK": "建議機台檢查",
    "QUALITY_HOLD": "品質風險暫停確認",
    "CHANGE_CNC_MACHINE": "更換 CNC 機台",
}

class DqnScheduler:
    """
    真 PyTorch DQN 架構：
    - 使用 torch.nn 建立 Q-Network。
    - Demo 階段用啟發式 reward 產生離線樣本訓練 Q 值。
    - 回傳 Q value 最大的 Action。
    """
    def __init__(self, epochs=160, lr=0.01):
        self.epochs = epochs
        self.lr = lr
        self.last_mode = "UNKNOWN"

    def _state_vector(self, f):
        return np.array([
            float(f.get("delay_risk_score") or 0),
            float(f.get("shortage_risk_score") or 0),
            float(f.get("quality_risk_score") or 0),
            float(f.get("power_risk_score") or 0),
            float(f.get("lstm_predicted_minutes") or 0) / 120.0,
            float(f.get("arima_predicted_minutes") or 0) / 120.0,
        ], dtype=np.float32)

    def _heuristic_target_q(self, state):
        delay, shortage, quality, power, lstm_norm, arima_norm = state
        q = np.zeros(len(ACTIONS), dtype=np.float32)
        q[ACTIONS.index("KEEP_CURRENT_SCHEDULE")] = 0.2 + (1 - max(delay, shortage, quality, power))
        q[ACTIONS.index("REQUEST_REPLENISHMENT")] = shortage * 1.5 + delay * 0.2
        q[ACTIONS.index("INCREASE_ORDER_PRIORITY")] = delay * 1.4 + lstm_norm * 0.4
        q[ACTIONS.index("REQUEST_MAINTENANCE_CHECK")] = power * 1.4
        q[ACTIONS.index("QUALITY_HOLD")] = quality * 1.5
        q[ACTIONS.index("CHANGE_CNC_MACHINE")] = max(delay, power) * 1.1
        return q

    def choose_action(self, features):
        if not features:
            self.last_mode = "NO_FEATURE"
            return []

        try:
            import torch
            import torch.nn as nn
        except Exception:
            self.last_mode = "FALLBACK_NO_TORCH"
            return [self._fallback_action(f) for f in features]

        x_np = np.array([self._state_vector(f) for f in features], dtype=np.float32)
        y_np = np.array([self._heuristic_target_q(s) for s in x_np], dtype=np.float32)

        torch.manual_seed(42)
        x = torch.tensor(x_np, dtype=torch.float32)
        y = torch.tensor(y_np, dtype=torch.float32)

        class QNetwork(nn.Module):
            def __init__(self, input_size, action_size):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(input_size, 32),
                    nn.ReLU(),
                    nn.Linear(32, 32),
                    nn.ReLU(),
                    nn.Linear(32, action_size),
                )

            def forward(self, x):
                return self.net(x)

        model = QNetwork(x.shape[1], len(ACTIONS))
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        model.train()
        for _ in range(self.epochs):
            pred_q = model(x)
            loss = loss_fn(pred_q, y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            q_values = model(x).numpy()

        self.last_mode = "PYTORCH_DQN_Q_NETWORK"
        results = []
        for f, q in zip(features, q_values):
            idx = int(np.argmax(q))
            action_type = ACTIONS[idx]
            results.append(self._build_result(f, action_type, q))
        return results

    def _fallback_action(self, f):
        delay = float(f.get("delay_risk_score") or 0)
        shortage = float(f.get("shortage_risk_score") or 0)
        quality = float(f.get("quality_risk_score") or 0)
        power = float(f.get("power_risk_score") or 0)
        if shortage >= 0.7:
            action_type = "REQUEST_REPLENISHMENT"
        elif delay >= 0.7:
            action_type = "INCREASE_ORDER_PRIORITY"
        elif power >= 0.7:
            action_type = "REQUEST_MAINTENANCE_CHECK"
        elif quality >= 0.6:
            action_type = "QUALITY_HOLD"
        else:
            action_type = "KEEP_CURRENT_SCHEDULE"
        q = np.zeros(len(ACTIONS), dtype=np.float32)
        q[ACTIONS.index(action_type)] = max(delay, shortage, quality, power, 0.5)
        return self._build_result(f, action_type, q)

    def _build_result(self, f, action_type, q):
        reasons = {
            "KEEP_CURRENT_SCHEDULE": "DQN Q-Network 判斷目前風險可接受。",
            "REQUEST_REPLENISHMENT": "DQN Q-Network 判斷缺料風險最高，建議提前補料。",
            "INCREASE_ORDER_PRIORITY": "DQN Q-Network 判斷延遲風險較高，建議提高優先級。",
            "REQUEST_MAINTENANCE_CHECK": "DQN Q-Network 判斷電力 / THD 風險較高，建議機台檢查。",
            "QUALITY_HOLD": "DQN Q-Network 判斷品質風險較高，建議暫停確認。",
            "CHANGE_CNC_MACHINE": "DQN Q-Network 判斷換機台可能降低延遲或電力風險。",
        }
        confidence = float(np.max(q))
        return {
            "feature": f,
            "action_type": action_type,
            "action_name": ACTION_NAMES[action_type],
            "reason": reasons[action_type],
            "q_values": {a: round(float(v), 4) for a, v in zip(ACTIONS, q)},
            "confidence": round(confidence, 4),
        }
