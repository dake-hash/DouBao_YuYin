"""
paths.py — 路径解析工具

开发模式: __file__ 在 src/ 下，根目录 = src/..
打包模式: PyInstaller 将所有文件解压到 sys._MEIPASS，
          可执行文件本身在 sys.executable 所在目录。
          - assets/  打包进 sys._MEIPASS/assets/
          - settings.json 写在 exe 同级目录（可写）
"""

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def assets_dir() -> Path:
    """返回 assets/ 目录路径（只读资源）。"""
    if _is_frozen():
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).parent.parent / "assets"


def app_data_dir() -> Path:
    """返回可写数据目录（settings.json 存放位置）。
    打包后使用 exe 所在目录，开发时使用项目根目录。
    """
    if _is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent
