"""
pet_menu.py — 桌宠右键/点击菜单

P2: 点击桌宠弹出菜单，包含语音识别开关、设置、关于、退出。
语音开关状态通过 Settings 持久化，切换后发射信号通知其他模块。
"""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


# ------------------------------------------------------------------
# 设置窗口
# ------------------------------------------------------------------


class SettingsDialog(QDialog):
    """极简设置窗口。

    显示:
        - 热键配置（只读，P6 后可修改）
        - 豆包登录状态（P3 后联动）
    """

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("设置")
        self.setFixedSize(300, 150)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
        )

        layout = QFormLayout(self)

        # 热键（只读）
        self._hotkey_edit = QLineEdit(settings.hotkey)
        self._hotkey_edit.setReadOnly(True)
        layout.addRow("热键:", self._hotkey_edit)

        # 登录状态
        login_text = "已登录" if settings.auth_token else "未登录"
        self._login_label = QLabel(login_text)
        layout.addRow("登录状态:", self._login_label)

        # 确定按钮
        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        layout.addRow(btn)


# ------------------------------------------------------------------
# 桌宠点击菜单
# ------------------------------------------------------------------


class PetMenu(QMenu):
    """桌宠点击弹出菜单。

    Signals:
        voice_toggled(bool):  语音开关变化时发射，新状态为参数
        quit_requested:       用户点击「退出」时发射
    """

    voice_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent, settings) -> None:
        super().__init__(parent)
        self._settings = settings

        # 语音开关（文字动态切换）
        self._voice_action = QAction(self)
        self._voice_action.triggered.connect(self._on_voice_toggle)
        self.addAction(self._voice_action)

        self.addSeparator()

        # 设置
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._on_settings)
        self.addAction(settings_action)

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        self.addAction(about_action)

        self.addSeparator()

        # 退出
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self.addAction(quit_action)

    # ------------------------------------------------------------------
    # 菜单项逻辑
    # ------------------------------------------------------------------

    def _refresh_voice_action(self) -> None:
        """根据当前 voice_enabled 状态更新开关菜单项的显示文字。"""
        if self._settings.voice_enabled:
            self._voice_action.setText("关闭语音识别")
        else:
            self._voice_action.setText("开启语音识别")

    def _on_voice_toggle(self) -> None:
        """切换语音识别开关。"""
        new_state = not self._settings.voice_enabled
        self._settings.voice_enabled = new_state
        self._refresh_voice_action()
        self.voice_toggled.emit(new_state)
        print(f"[PetMenu] 语音识别 → {'开启' if new_state else '关闭'}")

    def _on_settings(self) -> None:
        """打开设置窗口。"""
        dlg = SettingsDialog(self._settings, self.parent())
        dlg.exec()

    def _on_about(self) -> None:
        """显示关于信息。"""
        QMessageBox.about(
            self.parent(),
            "关于 豆包桌宠",
            "豆包桌宠 — 语音输入工具\n\n"
            "🎤 按住右Shift 说话，松手输出文字\n"
            "使用豆包免费 ASR 服务\n\n"
            "技术栈: Python + PySide6 + WebSocket",
        )

    # ------------------------------------------------------------------
    # 弹出
    # ------------------------------------------------------------------

    def show_at(self, pos: QPoint) -> None:
        """在指定位置弹出菜单。弹出前自动刷新开关项文字。"""
        self._refresh_voice_action()
        self.popup(pos)
