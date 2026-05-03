@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   ================================================
echo   DUON Mission Control Server
echo   ================================================
echo   Starting server...
echo   Open your browser at: http://localhost:5000
echo   On phone/iPad use:    http://YOUR-PC-IP:5000
echo   ================================================
echo.
python -m uvicorn web_server:app --host 0.0.0.0 --port 5000 --log-level info
pause
