from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"


def _file_info(filename: str) -> Dict[str, Any]:
    path = MODEL_DIR / filename

    if not path.exists():
        return {
            "filename": filename,
            "exists": False,
            "path": str(path),
            "size_bytes": 0,
        }

    return {
        "filename": filename,
        "exists": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
    }


def get_production_deployment_concerns() -> Dict[str, Any]:
    """
    將 Demo 前說明用的 concern 固化到專案 API。
    """
    return {
        "title": "AI 模型正式導入產線前 Concern",
        "safe_demo_statement": (
            "目前 Demo 已完成模型檔案保存、產量預測、DQN 排程建議與 Reward 回饋。"
            "正式導入前會先採 AI 建議、人工確認，再逐步提高自動化程度。"
        ),
        "risks_if_skip": [
            {
                "step": "資料品質未檢核",
                "risk": "錯誤 CNC 電表、ERP 製令、WMS 庫存會讓 AI 把錯資料當真。",
                "impact": "可能造成錯誤排程、缺料排程、機台空轉或交期延誤。",
            },
            {
                "step": "特徵工程不足",
                "risk": "未建立 OEE、THD、稼動率、缺料、交期壓力、工序前後關係等特徵。",
                "impact": "DQN Action 會像規則判斷，難以說服委員與現場人員。",
            },
            {
                "step": "未調參",
                "risk": "learning_rate、hidden_size、batch_size、sequence_length 不合理。",
                "impact": "預測結果不穩，同類製令可能產生差異很大的建議。",
            },
            {
                "step": "未剪枝",
                "risk": "模型參數較多，邊緣主機推論成本較高。",
                "impact": "推論速度與記憶體消耗可能不利於正式產線部署。",
            },
            {
                "step": "未量化",
                "risk": "float32 模型體積較大、推論速度較慢。",
                "impact": "在工控機或低階主機上較吃資源。",
            },
            {
                "step": "未 ONNX / TensorRT 部署",
                "risk": "仍依賴 Python / PyTorch runtime。",
                "impact": "正式部署環境較重，GPU 推論效能不是最佳。",
            },
        ],
        "recommended_order": [
            "資料品質檢查",
            "特徵工程",
            "超參數調整",
            "模型剪枝",
            "量化",
            "ONNX 匯出",
            "ONNX Runtime 驗證",
            "TensorRT engine 部署",
        ],
    }


def get_optimization_workflow() -> Dict[str, Any]:
    return {
        "title": "模型剪枝、量化、ONNX、TensorRT 流程",
        "model_files": [
            _file_info("lstm_quantity_forecast.pt"),
            _file_info("dqn_scheduler_policy.pt"),
            _file_info("dqn_scheduler_policy_pruned.pt"),
            _file_info("lstm_quantity_forecast_pruned.pt"),
            _file_info("dqn_scheduler_policy_int8.pt"),
            _file_info("dqn_scheduler_policy.onnx"),
            _file_info("lstm_quantity_forecast.onnx"),
            _file_info("dqn_scheduler_policy.engine"),
        ],
        "steps": [
            {
                "name": "剪枝 Pruning",
                "command": "python tools\\model_optimization\\prune_models.py",
                "output": [
                    "models/dqn_scheduler_policy_pruned.pt",
                    "models/lstm_quantity_forecast_pruned.pt",
                    "models/model_pruning_report.json",
                ],
            },
            {
                "name": "量化 + ONNX 匯出",
                "command": "python tools\\model_optimization\\export_quant_onnx.py",
                "output": [
                    "models/dqn_scheduler_policy_int8.pt",
                    "models/dqn_scheduler_policy.onnx",
                    "models/lstm_quantity_forecast.onnx",
                    "models/model_export_report.json",
                ],
            },
            {
                "name": "ONNX Runtime 驗證",
                "command": "python tools\\model_optimization\\test_onnx_runtime.py",
                "output": [
                    "確認 DQN / LSTM ONNX 可以正常推論",
                ],
            },
            {
                "name": "TensorRT",
                "command": "trtexec --onnx=models\\dqn_scheduler_policy.onnx --saveEngine=models\\dqn_scheduler_policy.engine --fp16",
                "output": [
                    "models/dqn_scheduler_policy.engine",
                ],
                "note": "TensorRT 建議在正式部署 GPU / CUDA / TensorRT 版本確定後再產生 engine。",
            },
        ],
    }
