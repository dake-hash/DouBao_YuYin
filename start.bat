@echo off
chcp 65001 >nul
title DouBao Desktop Pet Launcher

echo Checking Python environment...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Auto-install failed. Please download Python 3.12 from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Python 3.12 installed. Please close this window and run start.bat again.
    pause
    exit /b 0
)

echo Checking dependencies...

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
if %errorlevel% neq 0 (
    echo Dependency installation failed. Check your network or run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting DouBao Desktop Pet...
python src/main.py
if %errorlevel% neq 0 (
    echo.
    echo Program exited with error code: %errorlevel%
    pause
    exit /b 1
)
pause
