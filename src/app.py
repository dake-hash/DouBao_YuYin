"""
app.py — 应用生命周期管理

P0: DoubaoPetApp 负责创建 QApplication、初始化托盘、管理应用启动/退出。
"""

import sys

from PySide6.QtWidgets import QApplication

from settings import Settings
from tray import TrayIcon


class DoubaoPetApp:
    """豆包桌宠主应用。

    职责:
        - 创建 QApplication（不依赖系统命令行参数）
        - 初始化 Settings 和 TrayIcon
        - 连接托盘「退出」信号 → 优雅退出
        - 首次运行时标记 first_run = False
    """

    def __init__(self) -> None:
        # Qt 应用（不传 sys.argv 避免与 Python 参数混淆）
        self._app = QApplication([])
        self._app.setApplicationName("豆包桌宠")
        self._app.setQuitOnLastWindowClosed(False)

        # 设置 & 托盘
        self.settings = Settings()
        self.tray = TrayIcon()
        self.tray.set_tooltip("豆包桌宠 — 语音已关闭")
        self.tray.quit_requested.connect(self.quit)

        # 显示托盘图标
        self.tray.show()

        # 首次运行标记
        if self.settings.first_run:
            self.settings.first_run = False
            print("[App] 首次运行，已标记 first_run = False")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def run(self) -> int:
        """进入 Qt 事件循环。返回 exit code。"""
        return self._app.exec()

    def quit(self) -> None:
        """优雅退出：隐藏托盘 → 退出 Qt 事件循环。"""
        print("[App] 正在退出...")
        self.tray.hide()
        self._app.quit()
