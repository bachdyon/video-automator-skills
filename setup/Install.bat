@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
echo Asset-index installer (Windows)

where python >nul 2>nul
if errorlevel 1 (
    echo Ban can Python 3.10+ tai https://www.python.org/downloads/
    pause
    exit /b 2
)

python tools\asset_index\bootstrap.py %*
echo.
echo Xong. Nhan phim bat ky de dong cua so...
pause >nul
endlocal
