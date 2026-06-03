from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"
TOOLS_DIR = BASE_DIR / "tools" / "model_optimization"

COMMAND_TIMEOUT_SECONDS = 300


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


def _read_json_file(filename: str) -> Dict[str, Any]:
    path = MODEL_DIR / filename
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"read_error": str(exc), "path": str(path)}


def _run_command(args: List[str], timeout: int = COMMAND_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Run model optimization command from backend root.
    Windows 也可用，回傳 stdout / stderr 給前端 Demo 顯示。
    """
    started = time.time()

    try:
        completed = subprocess.run(
            args,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )

        return {
            "success": completed.returncode == 0,
            "returncode": completed.returncode,
            "command": " ".join(args),
            "cwd": str(BASE_DIR),
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "returncode": -1,
            "command": " ".join(args),
            "cwd": str(BASE_DIR),
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"Command timeout after {timeout} seconds.",
        }
    except Exception as exc:
        return {
            "success": False,
            "returncode": -1,
            "command": " ".join(args),
            "cwd": str(BASE_DIR),
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout": "",
            "stderr": str(exc),
        }


def get_aips_integrated_flow() -> Dict[str, Any]:
    """
    圖二：LSTM + ARIMA + DQN 整合運算邏輯。
    將圖片流程轉成專案內可展示資料。
    """
    return {
        "title": "AIPS 智慧排程系統：LSTM + ARIMA + DQN 整合運算邏輯",
        "summary": (
            "ERP 製令、CNC 設備、智慧電表、WMS 線邊庫、AOI 品質、人員作業資料先進資料治理與特徵工程，"
            "再由 LSTM 預測未來產量與品質、ARIMA 預測時間序列趨勢，兩者融合後形成 DQN State，"
            "最後由 DQN Q-Network 選擇最佳排程 Action，MES 執行後再由 Reward 回饋持續優化策略。"
        ),
        "stages": [
            {
                "no": 1,
                "name": "資料輸入層",
                "description": "彙整 ERP 製令、CNC 設備、智慧電表、WMS 線邊庫、AOI 品質、人員作業資料。",
                "inputs": ["ERP 製令", "CNC 主軸負載 / OEE / 加工時間", "智慧電表 kWh / THD", "WMS 即時庫存 / 缺料風險", "AOI 良品數 / 不良數", "NFC / QR Code / PDA 掃描"],
                "outputs": ["raw_operational_data"],
            },
            {
                "no": 2,
                "name": "資料治理與特徵工程",
                "description": "清洗異常值、整理時間序列、產生 AI 特徵向量。",
                "inputs": ["raw_operational_data"],
                "outputs": ["remaining_qty", "estimated_hours", "utilization", "OEE", "shortage_risk", "quality_risk", "energy_kwh", "priority_level"],
            },
            {
                "no": 3,
                "name": "LSTM 產量預測模型",
                "description": "使用多個時間點序列特徵，預測未來產量、良品量、不良量、良率、產能利用率與信心分數。",
                "inputs": ["time_series_features"],
                "outputs": ["predicted_output_qty", "predicted_good_qty", "predicted_ng_qty", "predicted_yield_rate", "capacity_utilization_rate", "confidence_score"],
            },
            {
                "no": 4,
                "name": "ARIMA 時間序列預測",
                "description": "針對加工時間、產量趨勢、能耗趨勢、設備狀態趨勢進行線性時間序列預測。",
                "inputs": ["history_output", "history_processing_time", "history_energy"],
                "outputs": ["trend_forecast", "processing_time_trend", "energy_trend"],
            },
            {
                "no": 5,
                "name": "預測結果融合 Prediction Fusion",
                "description": "將 LSTM 結果與 ARIMA 趨勢融合，形成更穩定的 DQN State。",
                "inputs": ["LSTM predictions", "ARIMA trends"],
                "outputs": ["DQN state features"],
            },
            {
                "no": 6,
                "name": "DQN State 狀態向量",
                "description": "形成 12 維 state vector，供 Q-Network 判斷最佳 Action。",
                "inputs": ["remaining_qty", "due_pressure", "previous_step_ready", "current_oee", "utilization", "energy_kwh", "shortage_risk", "quality_risk", "predicted_processing_time", "predicted_output_qty", "predicted_yield_rate", "priority_level"],
                "outputs": ["state_size = 12"],
            },
            {
                "no": 7,
                "name": "DQN Q-Network",
                "description": "Dense(12→64) + ReLU + Dense(64→64) + ReLU + Output(64→5)，輸出 5 個 Action 的 Q value。",
                "inputs": ["state vector"],
                "outputs": ["Q(PROCESS_NOW)", "Q(WAIT_PREVIOUS_STEP)", "Q(REQUEST_MATERIAL)", "Q(PAUSE_OR_MAINTAIN)", "Q(CHANGE_CNC)"],
            },
            {
                "no": 8,
                "name": "Action 決策",
                "description": "選擇 Q value 最高的 Action 作為排程建議。",
                "inputs": ["Q values"],
                "outputs": ["PROCESS_NOW", "WAIT_PREVIOUS_STEP", "REQUEST_MATERIAL", "PAUSE_OR_MAINTAIN", "CHANGE_CNC"],
            },
            {
                "no": 9,
                "name": "執行層 MES",
                "description": "DQN 決策交由 MES 派工，現場執行 CNC 加工並產生實際結果。",
                "inputs": ["selected action"],
                "outputs": ["actual_oee", "delivery_result", "quality_result", "energy_result"],
            },
            {
                "no": 10,
                "name": "Reward 計算與回饋",
                "description": "Reward = OEE_score + Delivery_score + Shortage_score + Quality_score + Energy_score，回饋 DQN 持續學習。",
                "inputs": ["actual_oee", "delay_hours", "shortage", "yield_rate", "energy_efficiency"],
                "outputs": ["total_reward_score", "updated_policy"],
            },
        ],
        "optimization_note": (
            "此流程先確保模型可落地、可剪枝、可量化、可 ONNX、可 TensorRT；正式產線再逐步補資料品質檢核、"
            "特徵穩定性、回測與人工確認機制。"
        ),
    }


def get_production_deployment_concerns() -> Dict[str, Any]:
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
        "integrated_flow": get_aips_integrated_flow(),
        "model_files": [
            _file_info("lstm_quantity_forecast.pt"),
            _file_info("dqn_scheduler_policy.pt"),
            _file_info("dqn_scheduler_policy_pruned.pt"),
            _file_info("lstm_quantity_forecast_pruned.pt"),
            _file_info("dqn_scheduler_policy_int8.pt"),
            _file_info("dqn_scheduler_policy.onnx"),
            _file_info("lstm_quantity_forecast.onnx"),
            _file_info("dqn_scheduler_policy_pruned.onnx"),
            _file_info("lstm_quantity_forecast_pruned.onnx"),
            _file_info("dqn_scheduler_policy.png"),
            _file_info("lstm_quantity_forecast.png"),
            _file_info("dqn_scheduler_policy_pruned.png"),
            _file_info("lstm_quantity_forecast_pruned.png"),
            _file_info("dqn_scheduler_policy.engine"),
        ],
        "reports": {
            "pruning": _read_json_file("model_pruning_report.json"),
            "export": _read_json_file("model_export_report.json"),
            "onnx_png": _read_json_file("onnx_png_report.json"),
            "tensorrt": _read_json_file("tensorrt_report.json"),
        },
        "steps": [
            {
                "key": "prune",
                "name": "剪枝 Pruning",
                "command": "python tools\\model_optimization\\prune_models.py",
                "output": [
                    "models/dqn_scheduler_policy_pruned.pt",
                    "models/lstm_quantity_forecast_pruned.pt",
                    "models/model_pruning_report.json",
                ],
                "note": "產生剪枝後 .pt，並輸出 sparsity 報告。",
            },
            {
                "key": "export",
                "name": "量化 + ONNX 匯出",
                "command": "python tools\\model_optimization\\export_quant_onnx.py",
                "output": [
                    "models/dqn_scheduler_policy_int8.pt",
                    "models/dqn_scheduler_policy.onnx",
                    "models/lstm_quantity_forecast.onnx",
                    "models/model_export_report.json",
                ],
                "note": "DQN dynamic int8 量化，並匯出 ONNX。",
            },
            {
                "key": "onnx_png",
                "name": "ONNX PNG 結構圖",
                "command": "python tools\\model_optimization\\export_onnx_png.py",
                "output": [
                    "models/dqn_scheduler_policy.png",
                    "models/dqn_scheduler_policy_pruned.png",
                    "models/lstm_quantity_forecast.png",
                    "models/lstm_quantity_forecast_pruned.png",
                    "models/onnx_png_report.json",
                ],
                "note": "需要 pydot + graphviz；若只要互動觀看可用 netron。",
            },
            {
                "key": "test",
                "name": "ONNX Runtime 驗證",
                "command": "python tools\\model_optimization\\test_onnx_runtime.py",
                "output": [
                    "確認 DQN / LSTM ONNX 可以正常推論",
                ],
                "note": "確認 ONNX 不只是檔案存在，而是真的能推論。",
            },
            {
                "key": "tensorrt",
                "name": "TensorRT",
                "command": "trtexec --onnx=models\\dqn_scheduler_policy.onnx --saveEngine=models\\dqn_scheduler_policy.engine",
                "output": [
                    "models/dqn_scheduler_policy.engine",
                    "models/tensorrt_report.json",
                ],
                "note": "--fp16 已移除；因使用者環境測試 --fp16 失敗，目前先使用 FP32 engine。",
            },
        ],
        "netron": {
            "install": "python -m pip install netron",
            "open_dqn": "netron models\\dqn_scheduler_policy.onnx",
            "open_lstm": "netron models\\lstm_quantity_forecast.onnx",
            "note": "Netron 適合互動看 ONNX；PNG 適合放簡報或專案頁面。",
        },
    }


def run_pruning() -> Dict[str, Any]:
    return _run_command([sys.executable, str(TOOLS_DIR / "prune_models.py")])


def run_export_quant_onnx() -> Dict[str, Any]:
    return _run_command([sys.executable, str(TOOLS_DIR / "export_quant_onnx.py")])


def run_onnx_runtime_test() -> Dict[str, Any]:
    return _run_command([sys.executable, str(TOOLS_DIR / "test_onnx_runtime.py")])


def run_onnx_png_export() -> Dict[str, Any]:
    return _run_command([sys.executable, str(TOOLS_DIR / "export_onnx_png.py")])


def run_tensorrt() -> Dict[str, Any]:
    # FIX54：依使用者測試結果，移除 --fp16。
    command = [
        "trtexec",
        "--onnx=models\\dqn_scheduler_policy.onnx",
        "--saveEngine=models\\dqn_scheduler_policy.engine",
    ]
    result = _run_command(command, timeout=600)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "command": " ".join(command),
        "success": result.get("success"),
        "returncode": result.get("returncode"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "engine": _file_info("dqn_scheduler_policy.engine"),
        "stdout_tail": result.get("stdout", "")[-5000:],
        "stderr_tail": result.get("stderr", "")[-5000:],
    }
    (MODEL_DIR / "tensorrt_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def run_optimization_step(step: str) -> Dict[str, Any]:
    mapping = {
        "prune": run_pruning,
        "export": run_export_quant_onnx,
        "onnx_png": run_onnx_png_export,
        "test": run_onnx_runtime_test,
        "tensorrt": run_tensorrt,
    }

    if step not in mapping:
        return {
            "success": False,
            "returncode": -1,
            "command": step,
            "stderr": f"Unsupported optimization step: {step}",
        }

    return mapping[step]()


def get_model_file_response(filename: str) -> Path:
    allowed = {
        "dqn_scheduler_policy.png",
        "lstm_quantity_forecast.png",
        "dqn_scheduler_policy_pruned.png",
        "lstm_quantity_forecast_pruned.png",
    }

    if filename not in allowed:
        raise FileNotFoundError("Unsupported file.")

    path = MODEL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(str(path))

    return path
