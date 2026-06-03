@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd /d %~dp0
nvcc -ptx dqn_policy_kernel.cu -o dqn_policy_kernel.ptx
if errorlevel 1 pause && exit /b 1
nvcc cuda_dqn_inference_service.cpp -o cuda_dqn_inference_service.exe -Xcompiler /utf-8 -I"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\include" -L"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\lib\x64" -lcuda -lws2_32
if errorlevel 1 pause && exit /b 1
echo Build OK: cuda_dqn_inference_service.exe
pause
