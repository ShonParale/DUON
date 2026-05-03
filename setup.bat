@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   ================================================
echo   DUON — Installing Dependencies
echo   ================================================
echo.
pip install fastapi uvicorn websockets pydantic python-multipart
echo.
echo   Done! Run start_server.bat to launch DUON.
echo.
pause
