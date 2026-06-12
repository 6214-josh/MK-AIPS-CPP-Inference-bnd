@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM AIPS 14 CNC 今日資料產生 / 排程 / AI / DQN / Reward Log 一鍵執行
REM 檔名：run_aips_today_14cnc.bat
REM
REM 手動執行：
REM   run_aips_today_14cnc.bat
REM
REM 排程 / 背景執行：
REM   run_aips_today_14cnc.bat /silent
REM ============================================================

REM ====== 請依你的實際專案路徑修改 ======
set "PROJECT_ROOT=C:\Users\solno\OneDrive\桌面\MINKIN\inference-cpp"
set "BND_DIR=%PROJECT_ROOT%\bnd"
set "FND_DIR=%PROJECT_ROOT%\fnd"

set "API_HOST=http://127.0.0.1:8999"
set "API_BASE=%API_HOST%/api"

set "START_FRONTEND=1"
set "FRONT_HOST=0.0.0.0"
set "FRONT_PORT=5074"

set "START_CUDA_SERVICE=1"
set "CUDA_SERVICE_DIR=%BND_DIR%\tools\cuda_inference_service"

set "ERP_ROUNDS=2"
set "ORDER_LIMIT=80"
set "PAUSE_AT_END=1"

if /I "%~1"=="/silent" (
  set "START_FRONTEND=0"
  set "PAUSE_AT_END=0"
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "RUN_DATE=%%I"

echo.
echo ============================================================
echo AIPS 14 CNC 今日運作一鍵執行
echo 日期：%RUN_DATE%
echo API ：%API_BASE%
echo ============================================================
echo.

call :CHECK_CURL
if errorlevel 1 goto :END_FAIL

if "%START_CUDA_SERVICE%"=="1" (
  call :ENSURE_CUDA_SERVICE
)

call :ENSURE_BACKEND
if errorlevel 1 goto :END_FAIL

if "%START_FRONTEND%"=="1" (
  call :START_FRONTEND
)

echo.
echo ============================================================
echo STEP 1. 初始化硬體模擬資料
echo ============================================================
call :POST "%API_BASE%/hardware-simulator/init"

echo.
echo ============================================================
echo STEP 2. 產生 CNC-01 ~ CNC-14 智慧電表資料
echo ============================================================
call :POST "%API_BASE%/meter/electric/demo-all"
call :GET "%API_BASE%/meter/electric/monitor"
call :GET "%API_BASE%/meter/raw/latest?limit=50"
call :GET "%API_BASE%/meter/features/latest?limit=50"

echo.
echo ============================================================
echo STEP 3. 產生線邊庫 / 人工物流資料，CNC-01 ~ CNC-14
echo ============================================================
call :POST "%API_BASE%/hardware-simulator/logistics/cart-demo?cnc_machine_id=ALL"
call :GET "%API_BASE%/inventory/snapshots/latest?limit=100"

echo.
echo ============================================================
echo STEP 4. 建立 ERP 製令資料，CNC-01 ~ CNC-14
echo ============================================================
for /L %%R in (1,1,%ERP_ROUNDS%) do (
  echo.
  echo --- ERP 製令第 %%R 輪 ---
  for /L %%N in (1,1,14) do (
    set "NUM=0%%N"
    set "NUM=!NUM:~-2!"
    set "CNC=CNC-!NUM!"
    call :POST "%API_BASE%/erp-simulator/receive-demo?cnc_machine_id=!CNC!"
  )
)
call :GET "%API_BASE%/erp-simulator/orders/latest?limit=100"

echo.
echo ============================================================
echo STEP 5. 建立產品 CNC 工序假設資料
echo ============================================================
call :POST "%API_BASE%/aips/cnc-daily-schedule/assumptions/seed?reset=true"

echo.
echo ============================================================
echo STEP 6. 產生今日 CNC-01 ~ CNC-14 日排程
echo ============================================================
call :POST "%API_BASE%/aips/cnc-daily-schedule/run?schedule_date=%RUN_DATE%&reset=true&order_limit=%ORDER_LIMIT%"
call :GET "%API_BASE%/aips/cnc-daily-schedule/gantt?schedule_date=%RUN_DATE%"

echo.
echo ============================================================
echo STEP 7. 執行 AIPS 資料工程 / State / DQN / Prediction / Reward
echo ============================================================
call :POST "%API_BASE%/aips/data-engineering/run-full-flow"
call :POST "%API_BASE%/aips/states/build"
call :POST "%API_BASE%/aips/dqn/generate-actions"
call :POST "%API_BASE%/aips/predictions/run"
call :POST "%API_BASE%/aips/rewards/calculate?limit=50"

echo.
echo ============================================================
echo STEP 8. DQN Reward Log Schema / Sync / Dashboard
echo ============================================================
call :POST "%API_BASE%/aips/reward-log/ensure-schema"
call :POST "%API_BASE%/aips/reward-log/sync"
call :GET "%API_BASE%/aips/reward-log/dashboard?time_range=ALL&limit=120"

echo.
echo ============================================================
echo STEP 9. 執行 AI 一鍵重排 / Dashboard Summary
echo ============================================================
call :POST "%API_BASE%/aips/cnc-dashboard/ai-reschedule?schedule_date=%RUN_DATE%"
call :GET "%API_BASE%/aips/cnc-dashboard/summary?schedule_date=%RUN_DATE%"

echo.
echo ============================================================
echo STEP 10. 最後檢查
echo ============================================================
call :GET "%API_BASE%/aips/cnc-dashboard/summary?schedule_date=%RUN_DATE%"
call :GET "%API_BASE%/aips/cnc-daily-schedule/gantt?schedule_date=%RUN_DATE%"
call :GET "%API_BASE%/aips/reward-log/dashboard?time_range=ALL&limit=120"

echo.
echo ============================================================
echo 完成！
echo 前端：
echo http://127.0.0.1:5074
echo http://114.34.58.174:5074
echo 日期請選：%RUN_DATE%
echo ============================================================
goto :END_OK

:CHECK_CURL
where curl >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 找不到 curl。請確認 Windows 10/11 已有 curl。
  exit /b 1
)
exit /b 0

:ENSURE_CUDA_SERVICE
echo [CHECK] 檢查 CUDA DQN / Reward service 9001
curl -s "http://127.0.0.1:9001/health" >nul 2>nul
if not errorlevel 1 (
  echo [OK] CUDA service 已啟動。
  exit /b 0
)

if not exist "%CUDA_SERVICE_DIR%" (
  echo [WARN] 找不到 CUDA service 資料夾，略過：
  echo %CUDA_SERVICE_DIR%
  exit /b 0
)

echo [INFO] 嘗試啟動 CUDA service...
start "AIPS CUDA DQN Reward Service 9001" cmd /k "cd /d "%CUDA_SERVICE_DIR%" && if exist run_cuda_dqn_service.bat call run_cuda_dqn_service.bat"

timeout /t 5 /nobreak >nul
curl -s "http://127.0.0.1:9001/health" >nul 2>nul
if not errorlevel 1 (
  echo [OK] CUDA service 啟動完成。
) else (
  echo [WARN] CUDA service 尚未確認啟動，後端會降級 Python fallback。
)
exit /b 0

:ENSURE_BACKEND
echo [CHECK] 檢查後端是否已啟動：%API_HOST%
curl -s "%API_HOST%/api/health" >nul 2>nul
if not errorlevel 1 (
  echo [OK] 後端已啟動。
  exit /b 0
)

curl -s "%API_HOST%/health" >nul 2>nul
if not errorlevel 1 (
  echo [OK] 後端已啟動。
  exit /b 0
)

echo [INFO] 後端尚未啟動，嘗試自動啟動 FastAPI...
if not exist "%BND_DIR%" (
  echo [ERROR] 找不到後端資料夾：
  echo %BND_DIR%
  echo 請修改本 BAT 最上方 BND_DIR。
  exit /b 1
)

start "AIPS FastAPI Backend 8999" cmd /k "cd /d "%BND_DIR%" && if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8999"

echo [WAIT] 等待後端啟動...
for /L %%S in (1,1,60) do (
  timeout /t 2 /nobreak >nul
  curl -s "%API_HOST%/api/health" >nul 2>nul
  if not errorlevel 1 (
    echo [OK] 後端啟動完成。
    exit /b 0
  )
  curl -s "%API_HOST%/health" >nul 2>nul
  if not errorlevel 1 (
    echo [OK] 後端啟動完成。
    exit /b 0
  )
  echo 等待中 %%S/60 ...
)

echo [ERROR] 後端 8999 啟動逾時。
exit /b 1

:START_FRONTEND
if not exist "%FND_DIR%" (
  echo [WARN] 找不到前端資料夾，略過自動啟動前端：
  echo %FND_DIR%
  exit /b 0
)
echo [INFO] 嘗試啟動前端 React / Vite port %FRONT_PORT% ...
start "AIPS React Frontend %FRONT_PORT%" cmd /k "cd /d "%FND_DIR%" && npm run dev -- --host %FRONT_HOST% --port %FRONT_PORT%"
exit /b 0

:POST
echo.
echo [POST] %~1
curl -s -X POST "%~1"
if errorlevel 1 (
  echo.
  echo [WARN] POST 失敗：%~1
) else (
  echo.
  echo [OK] POST 完成
)
exit /b 0

:GET
echo.
echo [GET] %~1
curl -s "%~1"
if errorlevel 1 (
  echo.
  echo [WARN] GET 失敗：%~1
) else (
  echo.
  echo [OK] GET 完成
)
exit /b 0

:END_OK
echo.
if "%PAUSE_AT_END%"=="1" pause
exit /b 0

:END_FAIL
echo.
echo 執行失敗，請查看上方錯誤訊息。
if "%PAUSE_AT_END%"=="1" pause
exit /b 1
