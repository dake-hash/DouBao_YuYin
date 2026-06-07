@echo off
chcp 65001 >nul
title DouBao Desktop Pet Launcher

echo Checking Python environment...

python --version >nul 2>&1
if %errorlevel% neq 0 goto install_python

:: Check Python version >= 3.10
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if %PYMAJOR% LSS 3 goto install_python
if %PYMAJOR% EQU 3 if %PYMINOR% LSS 10 goto install_python
goto deps

:install_python
echo Downloading Python 3.12.9 installer...
curl -L -o "C:\python-3.12.9-amd64.exe" "https://mirrors.huaweicloud.com/python/3.12.9/python-3.12.9-amd64.exe"
if %errorlevel% neq 0 (
    echo Download failed. Please download Python 3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Installing Python 3.12.9...
"C:\python-3.12.9-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo Installation failed. Please install Python 3.12 manually.
    pause
    exit /b 1
)
echo Python 3.12.9 installed. Please close this window and run start.bat again.
pause
exit /b 0

:deps
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
