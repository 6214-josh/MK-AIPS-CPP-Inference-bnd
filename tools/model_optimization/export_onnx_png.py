from pathlib import Path
import json
import shutil
import sys

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"
REPORT = MODEL_DIR / "onnx_png_report.json"

MODELS = [
    {
        "onnx": MODEL_DIR / "dqn_scheduler_policy.onnx",
        "png": MODEL_DIR / "dqn_scheduler_policy.png",
        "title": "DQN Q-Network",
        "subtitle": "Before pruning",
        "nodes": ["state\\n(batch x 12)", "Dense / Gemm\\n12 -> 64", "ReLU", "Dense / Gemm\\n64 -> 64", "ReLU", "Dense / Gemm\\n64 -> 5", "q_values\\n(batch x 5)"],
    },
    {
        "onnx": MODEL_DIR / "dqn_scheduler_policy_pruned.onnx",
        "png": MODEL_DIR / "dqn_scheduler_policy_pruned.png",
        "title": "DQN Q-Network",
        "subtitle": "After pruning",
        "nodes": ["state\\n(batch x 12)", "Pruned Dense\\n12 -> 64", "ReLU", "Pruned Dense\\n64 -> 64", "ReLU", "Pruned Dense\\n64 -> 5", "q_values\\n(batch x 5)"],
    },
    {
        "onnx": MODEL_DIR / "lstm_quantity_forecast.onnx",
        "png": MODEL_DIR / "lstm_quantity_forecast.png",
        "title": "LSTM Quantity Forecast",
        "subtitle": "Before pruning",
        "nodes": ["sequence_features\\n(batch x 6 x 8)", "LSTM\\ninput 8 / hidden 32", "Take last step", "Dense\\n32 -> 32", "ReLU", "Dense\\n32 -> 3", "quantity_prediction\\noutput/good/ng"],
    },
    {
        "onnx": MODEL_DIR / "lstm_quantity_forecast_pruned.onnx",
        "png": MODEL_DIR / "lstm_quantity_forecast_pruned.png",
        "title": "LSTM Quantity Forecast",
        "subtitle": "After pruning",
        "nodes": ["sequence_features\\n(batch x 6 x 8)", "Pruned LSTM\\ninput 8 / hidden 32", "Take last step", "Pruned Dense\\n32 -> 32", "ReLU", "Pruned Dense\\n32 -> 3", "quantity_prediction\\noutput/good/ng"],
    },
]


def file_info(path: Path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def try_export_with_graphviz(model_path: Path, output_png: Path):
    try:
        import onnx
        from onnx.tools.net_drawer import GetOpNodeProducer, GetPydotGraph

        if shutil.which("dot") is None:
            return False, "Graphviz dot not found."

        model = onnx.load(str(model_path))
        graph = GetPydotGraph(
            model.graph,
            name=model_path.stem,
            rankdir="TB",
            node_producer=GetOpNodeProducer("docstring"),
        )
        graph.write_png(str(output_png))

        return output_png.exists(), "graphviz"
    except Exception as exc:
        return False, str(exc)


def draw_fallback_png(item):
    """
    Graphviz 沒裝或 dot 不能用時，產生可 Demo 的簡化 PNG。
    這不是 Netron 完整 graph，但可在前端頁面顯示剪枝前/後模型結構。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        return False, f"Pillow not installed: {exc}"

    output_png = item["png"]
    nodes = item["nodes"]

    width = 1180
    node_w = 230
    node_h = 76
    gap = 38
    margin_x = 70
    margin_y = 110
    height = margin_y * 2 + len(nodes) * node_h + (len(nodes) - 1) * gap

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 34)
        subtitle_font = ImageFont.truetype("arial.ttf", 22)
        font = ImageFont.truetype("arial.ttf", 20)
        small_font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((margin_x, 28), item["title"], fill=(15, 23, 42), font=title_font)
    draw.text((margin_x, 68), item["subtitle"], fill=(71, 85, 105), font=subtitle_font)

    x = (width - node_w) // 2
    y = margin_y

    for idx, node in enumerate(nodes):
        fill = (224, 242, 254)
        outline = (37, 99, 235)
        if "Pruned" in node or "After" in item["subtitle"]:
            fill = (220, 252, 231)
            outline = (22, 163, 74)
        if "ReLU" in node:
            fill = (254, 243, 199)
            outline = (217, 119, 6)
        if idx == 0 or idx == len(nodes) - 1:
            fill = (241, 245, 249)
            outline = (71, 85, 105)

        draw.rounded_rectangle(
            [x, y, x + node_w, y + node_h],
            radius=14,
            fill=fill,
            outline=outline,
            width=3,
        )

        lines = node.split("\\n")
        line_y = y + 16
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text((x + (node_w - tw) / 2, line_y), line, fill=(15, 23, 42), font=font)
            line_y += 24

        if idx < len(nodes) - 1:
            ax = width // 2
            y1 = y + node_h
            y2 = y + node_h + gap
            draw.line([ax, y1, ax, y2 - 10], fill=(100, 116, 139), width=3)
            draw.polygon(
                [(ax - 8, y2 - 12), (ax + 8, y2 - 12), (ax, y2)],
                fill=(100, 116, 139),
            )

        y += node_h + gap

    footer = "Generated by export_onnx_png.py fallback renderer. Use Netron for interactive ONNX graph."
    draw.text((margin_x, height - 44), footer, fill=(100, 116, 139), font=small_font)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png)

    return output_png.exists(), "fallback_pillow"


def export_one(item):
    model_path = item["onnx"]
    output_png = item["png"]

    if not model_path.exists():
        return {
            "model": str(model_path),
            "png": str(output_png),
            "success": False,
            "method": None,
            "reason": "ONNX 檔案不存在，請先執行「量化 + ONNX 匯出」。",
        }

    ok, method_or_error = try_export_with_graphviz(model_path, output_png)

    if not ok:
        fallback_ok, fallback_method_or_error = draw_fallback_png(item)
        return {
            "model": file_info(model_path),
            "png": file_info(output_png),
            "success": fallback_ok,
            "method": fallback_method_or_error if fallback_ok else None,
            "graphviz_error": method_or_error,
            "fallback_error": None if fallback_ok else fallback_method_or_error,
        }

    return {
        "model": file_info(model_path),
        "png": file_info(output_png),
        "success": True,
        "method": "graphviz",
    }


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    results = [export_one(item) for item in MODELS]
    success_count = sum(1 for item in results if item.get("success"))

    report = {
        "success_count": success_count,
        "results": results,
        "netron_note": "Netron 只會開啟互動檢視畫面，不會自動在 models 目錄產生 PNG。要讓前端顯示，需要本腳本輸出 PNG 檔。",
        "install_hint": "建議安裝：python -m pip install pillow pydot graphviz onnx netron；Windows 若要完整 graphviz PNG，還要安裝 Graphviz 程式本體並確認 dot -V。",
    }

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
