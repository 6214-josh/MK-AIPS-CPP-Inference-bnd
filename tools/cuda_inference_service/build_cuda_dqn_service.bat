@echo off
setlocal EnableExtensions

REM FIX78：避免 Windows 批次檔出現 The input line is too long.
REM 原因通常是 vcvars64.bat 讓 PATH/INCLUDE/LIB 太長，或 nvcc/link 指令過長。
REM 本版先縮短 PATH，再用分段方式編譯 PTX、OBJ、EXE。

cd /d "%~dp0"

set "CUDA_ROOT=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9"
set "VS_VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

REM 先縮短 PATH，避免 vcvars64.bat 因為使用者環境變數太長而失敗。
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;%CUDA_ROOT%\bin"

if exist "%VS_VCVARS%" (
    call "%VS_VCVARS%"
) else (
    echo Cannot find VS Build Tools vcvars64.bat
    echo Please install Build Tools for Visual Studio 2022.
    pause
    exit /b 1
)

echo [1/3] Build PTX
nvcc -ptx "dqn_policy_kernel.cu" -o "dqn_policy_kernel.ptx"
if errorlevel 1 pause && exit /b 1

echo [2/3] Compile OBJ
nvcc -c "cuda_dqn_inference_service.cpp" -o "cuda_dqn_inference_service.obj" -Xcompiler "/utf-8" -I"%CUDA_ROOT%\include"
if errorlevel 1 pause && exit /b 1

echo [3/3] Link EXE
nvcc "cuda_dqn_inference_service.obj" -o "cuda_dqn_inference_service.exe" -L"%CUDA_ROOT%\lib\x64" -lcuda -lws2_32
if errorlevel 1 pause && exit /b 1

echo Build OK: cuda_dqn_inference_service.exe
pause
