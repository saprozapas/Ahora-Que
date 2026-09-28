@echo off
rem Abre la vista previa del rediseno (datos de ejemplo, no toca la base).
rem Doble clic para abrirla; cerra esta ventana para apagarla.

cd /d "%~dp0.."
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:5058/demo"
python redesign-screens\preview.py
pause
