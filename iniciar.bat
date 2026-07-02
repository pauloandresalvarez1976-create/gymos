@echo off
title GymOS
cd /d %~dp0

:: Matar procesos viejos en puerto 5001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

:: Arrancar backend
start "GymOS Backend" python app.py

:: Esperar que arranque
timeout /t 12 /nobreak >nul

:: Abrir Firefox
start firefox "http://127.0.0.1:5001"
