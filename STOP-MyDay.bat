@echo off
title MyDay Stop
echo Apagando MyDay, Transcribe y TimeTracker...
echo.

REM --- Matar lo que escuche en los puertos de las tres apps (preciso, no toca otros python) ---
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,8088,8787 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

REM --- Matar el monitor de captura de TimeTracker (pythonw monitor.py) ---
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*monitor.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Listo. Todo apagado.
timeout /t 2 /nobreak >nul
