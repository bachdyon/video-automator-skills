@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Chua cai dat. Hay chay Install.bat truoc.
    pause
    exit /b 2
)

.venv\Scripts\python.exe -m tools.asset_index.service status
echo.
pause >nul
endlocal
