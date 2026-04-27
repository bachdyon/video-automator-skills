@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Chua cai dat. Hay chay Install.bat truoc.
    pause
    exit /b 2
)

echo Go truy van tim kiem (Ctrl+C de thoat). Tieng Viet co dau OK.
:loop
set "QUERY="
set /p QUERY=? 
if "%QUERY%"=="" goto loop
.venv\Scripts\python.exe -m tools.asset_index.search "%QUERY%" --top 5
goto loop
