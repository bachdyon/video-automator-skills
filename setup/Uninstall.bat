@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Chua cai dat — khong co gi de go.
    pause
    exit /b 0
)

.venv\Scripts\python.exe -m tools.asset_index.service uninstall
echo.
echo Xong. Nhan phim bat ky de dong...
pause >nul
endlocal
