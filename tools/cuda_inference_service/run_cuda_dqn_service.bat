@echo off
cd /d %~dp0
cuda_dqn_inference_service.exe 9001 dqn_policy_kernel.ptx
pause
