@echo off
cd /d "%~dp0"
if not exist "cuda_dqn_inference_service.exe" (
    echo cuda_dqn_inference_service.exe not found. Please run build_cuda_dqn_service.bat first.
    pause
    exit /b 1
)
cuda_dqn_inference_service.exe
