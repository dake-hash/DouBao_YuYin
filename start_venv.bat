@echo off
chcp 65001 >nul
title DouBao Desktop Pet Launcher (venv)

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
goto create_venv

:install_python
:: Check if bundled installer exists in runtime\
set INSTALLER=
for %%f in ("%~dp0runtime\python-*.exe") do set INSTALLER=%%f

if defined INSTALLER (
    echo Found bundled Python installer: %INSTALLER%
) else (
    echo No bundled installer found, downloading Python 3.13.2...
    curl -L -o "%TEMP%\python-3.13.2-amd64.exe" "https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe"
    if %errorlevel% neq 0 (
        echo Download failed. Please download Python from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set INSTALLER=%TEMP%\python-3.13.2-amd64.exe
)

echo Installing Python...
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo Installation failed. Please install Python manually.
    pause
    exit /b 1
)
echo Python installed. Please close this window and run start_venv.bat again.
pause
exit /b 0

:create_venv
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Checking dependencies...

:: Install uv if not available, then use it to install packages
where uv >nul 2>&1
if %errorlevel% equ 0 (
    uv pip install -r requirements.txt
) else (
    echo Installing uv package manager...
    pip install uv
    if %errorlevel% equ 0 (
        venv\Scripts\uv.exe pip install -r requirements.txt
    ) else (
        echo uv installation failed, falling back to pip...
        pip install -r requirements.txt
    )
)
if %errorlevel% neq 0 (
    echo Dependency installation failed. Check your network or run: pip install -r requirements.txt
    pause
    exit /b 1
)

:: Trim unused PySide6 files after first install (runs once, skipped on subsequent launches)
if not exist "venv\.cleaned" (
    echo Cleaning unused PySide6 files...
    python cleanup_pyside6.py
)

:run
echo Starting DouBao Desktop Pet...
python src/main.py
if %errorlevel% neq 0 (
    echo.
    echo Program exited with error code: %errorlevel%
    pause
    exit /b 1
)
pause
