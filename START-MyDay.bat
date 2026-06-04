@echo off
REM Lanzador delgado: ejecuta START-MyDay.ps1 (logica idempotente real).
title MyDay Launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START-MyDay.ps1"
