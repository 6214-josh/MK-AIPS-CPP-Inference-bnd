from pathlib import Path
import json
import sys

import onnx
from onnx.tools.net_drawer import GetOpNodeProducer, GetPydotGraph

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"
REPORT = MODEL_DIR / "onnx_png_report.json"

MODELS = [
    MODEL_DIR / "dqn_scheduler_policy.onnx",
    MODEL_DIR / "lstm_quantity_forecast.onnx",
    MODEL_DIR / "dqn_scheduler_policy_pruned.onnx",
    MODEL_DIR / "lstm_quantity_forecast_pruned.onnx",
]


def file_info(path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def export_png(model_path):
    if not model_path.exists():
        return {
            "model": str(model_path),
            "success": False,
            "reason": "ONNX 檔案不存在，請先執行 export_quant_onnx.py",
        }

    output_png = MODEL_DIR / f"{model_path.stem}.png"

    model = onnx.load(str(model_path))
    graph = GetPydotGraph(
        model.graph,
        name=model_path.stem,
        rankdir="TB",
        node_producer=GetOpNodeProducer("docstring"),
    )
    graph.write_png(str(output_png))

    return {
        "model": file_info(model_path),
        "png": file_info(output_png),
        "success": output_png.exists(),
    }


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for model_path in MODELS:
        try:
            results.append(export_png(model_path))
        except Exception as exc:
            results.append({
                "model": str(model_path),
                "success": False,
                "error": str(exc),
                "hint": "請安裝 Graphviz 程式本體並確認 dot -V 可執行；Python 套件需 pydot graphviz onnx。",
            })

    report = {
        "results": results,
        "netron_note": "若 PNG 產生失敗，可用：python -m pip install netron && netron models\\dqn_scheduler_policy.onnx",
    }

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
