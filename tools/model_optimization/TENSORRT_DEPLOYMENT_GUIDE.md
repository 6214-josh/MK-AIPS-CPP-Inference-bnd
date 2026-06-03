# TensorRT 部署起步

建議流程：

```text
.pt
→ pruning
→ dynamic int8 quantization
→ ONNX export
→ ONNX Runtime 驗證
→ TensorRT engine
```

## Windows / Linux 轉 TensorRT engine

先確認已安裝 NVIDIA Driver / CUDA / TensorRT，並且 `trtexec` 可執行。

```bash
trtexec --onnx=models/dqn_scheduler_policy.onnx --saveEngine=models/dqn_scheduler_policy.engine --fp16
```

## 注意

TensorRT engine 通常與下列環境綁定：

```text
GPU 型號
NVIDIA Driver
CUDA
TensorRT 版本
```

所以 Demo 階段建議先產生 ONNX 並用 ONNX Runtime 驗證。正式部署機器確定後，再產生 TensorRT engine。
