@echo off
powershell -ExecutionPolicy Bypass -File D:\AstraBridge\scripts\cleanup_stale_astrabridge_processes.ps1 -Quiet
cd /d D:\AstraBridge\apps\astrabridge-sidecar
D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m astrabridge_sidecar.server --serve --port 8852 --seed-root D:\AstraBridge 1>D:\AstraBridge\tmp\sidecar-8852.out.log 2>D:\AstraBridge\tmp\sidecar-8852.err.log
