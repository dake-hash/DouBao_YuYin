"""
tray.py — 系统托盘图标与菜单

P0: 使用 QSystemTrayIcon 在系统托盘显示图标，右键菜单包含「退出」。
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _create_fallback_icon(size: int = 32) -> QIcon:
    """生成一个简单的圆形占位图标（紫色），用于托盘图标缺失时。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#6C5CE7"))
    painter.setPen(QColor("#4A3DB5"))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    # 画一个简单的 "D" 字形中心
    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(None)  # use default
    font = painter.font()
    font.setPixelSize(size // 2)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, "D")  # Qt.AlignCenter
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标，右键菜单含「退出」。

    Signals:
        quit_requested: 用户点击「退出」菜单时发射。
    """

    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_icon()
        self._setup_menu()

    # ------------------------------------------------------------------
    # 图标
    # ------------------------------------------------------------------

    def _setup_icon(self) -> None:
        """加载托盘图标；文件不存在时使用代码生成的占位图标。"""
        icon_path = Path(__file__).parent.parent / "assets" / "tray_icon.png"
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            self.setIcon(_create_fallback_icon())

    def set_tooltip(self, text: str) -> None:
        self.setToolTip(text)

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _setup_menu(self) -> None:
        menu = QMenu()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.MessageIcon.Information, duration_ms: int = 3000) -> None:
        """弹出托盘气泡通知。"""
        if self.supportsMessages():
            self.showMessage(title, message, icon, duration_ms)
        else:
            print(f"[Tray] {title}: {message}")
