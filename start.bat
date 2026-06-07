@echo off
chcp 65001 >nul
title 豆包桌宠启动器

echo 正在检查 Python 环境...

:: 检查 Python 是否已安装且版本 >= 3.12
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 未检测到 Python，正在通过 winget 安装 Python 3.12...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo 自动安装失败，请手动前往 https://www.python.org/downloads/ 下载安装 Python 3.12
        pause
        exit /b 1
    )
    echo Python 3.12 安装完成
    :: 刷新环境变量
    call refreshenv >nul 2>&1
)

:: 再次确认 python 可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 安装后仍无法识别，请重启本脚本或手动运行。
    pause
    exit /b 1
)

echo 正在检查依赖...

:: 先单独处理 PyAudio（Windows 上需要 pipwin）
python -c "import pyaudio" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装 PyAudio...
    pip install pipwin -q
    pipwin install pyaudio
)

:: 安装 requirements.txt 其余依赖（已满足版本的包会自动跳过）
pip install -r requirements.txt -q

echo 正在启动豆包桌宠...
python src/main.py
