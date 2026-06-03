import os
import numpy as np

class LstmProcessTimePredictor:
    """
    真 PyTorch LSTM：
    - 會以目前 DB 內的製令流程卡工序資料即時訓練一個小型 LSTM。
    - 資料量不足時會降級成加權平均，但只要 torch 可用且資料 >= min_samples 就會跑 torch.nn.LSTM。
    - Demo 階段不依賴外部模型檔，會動態訓練；之後可改為載入 .pt 模型。
    """
    def __init__(self, min_samples=8, epochs=80, lr=0.03):
        self.min_samples = min_samples
        self.epochs = epochs
        self.lr = lr
        self.last_mode = "UNKNOWN"

    def _fallback(self, features):
        if not features:
            self.last_mode = "FALLBACK_NO_DATA"
            return 30.0
        vals = [float(x.get("actual_processing_minutes") or 0) for x in features]
        vals = [v for v in vals if v > 0]
        if not vals:
            self.last_mode = "FALLBACK_NO_VALID_DURATION"
            return 30.0
        self.last_mode = "FALLBACK_WEIGHTED_AVG"
        return round(float(np.mean(vals[-5:])), 2)

    def predict_next_minutes(self, features):
        if len(features) < self.min_samples:
            return self._fallback(features)

        try:
            import torch
            import torch.nn as nn
        except Exception:
            return self._fallback(features)

        rows = []
        y = []
        for item in features:
            actual = float(item.get("actual_processing_minutes") or 0)
            if actual <= 0:
                continue
            rows.append([
                float(item.get("sequence_no") or 0),
                float(item.get("standard_cycle_time_sec") or 0) / 60.0,
                float(item.get("delay_minutes") or 0),
                1.0 if item.get("shortage_flag") else 0.0,
                float(item.get("shortage_qty") or 0),
                float(item.get("avg_power_kw") or 0),
                float(item.get("avg_thd_current") or 0),
                float(item.get("quality_risk_score") or 0),
            ])
            y.append(actual)

        if len(rows) < self.min_samples:
            return self._fallback(features)

        x_np = np.array(rows, dtype=np.float32)
        y_np = np.array(y, dtype=np.float32).reshape(-1, 1)

        x_mean = x_np.mean(axis=0)
        x_std = x_np.std(axis=0) + 1e-6
        y_mean = y_np.mean(axis=0)
        y_std = y_np.std(axis=0) + 1e-6

        x_scaled = (x_np - x_mean) / x_std
        y_scaled = (y_np - y_mean) / y_std

        torch.manual_seed(42)
        x_tensor = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(1)  # batch, seq_len, features
        y_tensor = torch.tensor(y_scaled, dtype=torch.float32)

        class LstmRegressor(nn.Module):
            def __init__(self, input_size):
                super().__init__()
                self.lstm = nn.LSTM(input_size=input_size, hidden_size=16, num_layers=1, batch_first=True)
                self.fc = nn.Sequential(nn.Linear(16, 8), nn.ReLU(), nn.Linear(8, 1))

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])

        model = LstmRegressor(input_size=x_tensor.shape[-1])
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        model.train()
        for _ in range(self.epochs):
            pred = model(x_tensor)
            loss = loss_fn(pred, y_tensor)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        latest = x_scaled[-1:].astype(np.float32)
        latest_tensor = torch.tensor(latest, dtype=torch.float32).unsqueeze(1)
        model.eval()
        with torch.no_grad():
            pred_scaled = model(latest_tensor).numpy()[0][0]

        predicted = float(pred_scaled * y_std[0] + y_mean[0])
        self.last_mode = "PYTORCH_LSTM_DYNAMIC_TRAINING"
        return round(max(predicted, 1.0), 2)
