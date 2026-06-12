@echo off
cd /d %~dp0
echo === Health ===
curl http://127.0.0.1:9001/health
echo.
echo === Reward test ===
curl -X POST http://127.0.0.1:9001/reward -H "Content-Type: application/json" -d "{\"planned_processing_time\":2.5,\"actual_processing_time\":2.2,\"delay_hours\":0,\"shortage_occurred_flag\":false,\"machine_down_occurred_flag\":false,\"actual_yield_rate\":0.96,\"actual_oee\":0.82,\"energy_kwh\":12,\"expected_oee_improvement_rate\":0.04}"
echo.
pause
