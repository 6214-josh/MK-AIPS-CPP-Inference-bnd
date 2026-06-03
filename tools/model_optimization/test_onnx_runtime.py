from pathlib import Path
import numpy as np
import onnxruntime as ort

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"

DQN_ONNX = MODEL_DIR / "dqn_scheduler_policy.onnx"
LSTM_ONNX = MODEL_DIR / "lstm_quantity_forecast.onnx"


def test_dqn():
    session = ort.InferenceSession(
        str(DQN_ONNX),
        providers=["CPUExecutionProvider"],
    )
    x = np.random.rand(1, 12).astype(np.float32)
    y = session.run(None, {"state": x})
    print("DQN ONNX output:", y)


def test_lstm():
    session = ort.InferenceSession(
        str(LSTM_ONNX),
        providers=["CPUExecutionProvider"],
    )
    x = np.random.rand(1, 6, 8).astype(np.float32)
    y = session.run(None, {"sequence_features": x})
    print("LSTM ONNX output:", y)


if __name__ == "__main__":
    test_dqn()
    test_lstm()
