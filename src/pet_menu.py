"""
pet_menu.py — 桌宠右键/点击菜单

P2: 点击桌宠弹出菜单，包含语音识别开关、设置、关于、退出。
语音开关状态通过 Settings 持久化，切换后发射信号通知其他模块。
Claude 语音助手: 新增 ClaudeNotifyConfigDialog，首次开启时引导配置。
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
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
# Claude 语音助手配置弹窗
# ------------------------------------------------------------------


class ClaudeNotifyConfigDialog(QDialog):
    """首次开启 Claude 语音助手时弹出，引导用户完成 Hook 配置。

    提供两个选项：
        一键配置  — 自动写入 ~/.claude/settings.json
        手动配置  — 展示 JSON 片段供用户自行填写
    """

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self.setWindowTitle("配置 Claude 语音助手")
        self.setFixedWidth(420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("您尚未配置 Claude Code Hook，语音助手无法工作。\n请选择配置方式：")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        self._auto_btn = QPushButton("一键配置")
        self._manual_btn = QPushButton("手动配置说明")
        self._auto_btn.clicked.connect(self._on_auto)
        self._manual_btn.clicked.connect(self._on_manual)
        btn_row.addWidget(self._auto_btn)
        btn_row.addWidget(self._manual_btn)
        layout.addLayout(btn_row)

        self._manual_area = QTextEdit()
        self._manual_area.setReadOnly(True)
        self._manual_area.setFont(QFont("Consolas", 9))
        self._manual_area.setMinimumHeight(200)
        self._manual_area.setVisible(False)
        layout.addWidget(self._manual_area)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _on_auto(self) -> None:
        from claude_notify import installer, hook_manager
        ok = installer.install(self._project_root)
        if ok:
            self._status_label.setText(
                "配置成功！请重启 Claude Code 使设置生效。"
            )
            self._auto_btn.setEnabled(False)
            self._manual_area.setVisible(False)
        else:
            self._status_label.setText(
                "写入失败，请检查 ~/.claude/ 目录权限，或改用手动配置。"
            )

    def _on_manual(self) -> None:
        from claude_notify import hook_manager
        text = hook_manager.get_manual_config_text(self._project_root)
        instructions = (
            "请打开 C:\\Users\\你的用户名\\.claude\\settings.json\n"
            "（不存在则新建），将以下内容写入，保存后重启 Claude Code：\n\n"
            + text
        )
        self._manual_area.setPlainText(instructions)
        self._manual_area.setVisible(True)
        self.adjustSize()


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
    login_requested = Signal()
    claude_notify_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent, settings) -> None:
        super().__init__(parent)
        self._settings = settings

        # 语音开关（文字动态切换）
        self._voice_action = QAction(self)
        self._voice_action.triggered.connect(self._on_voice_toggle)
        self.addAction(self._voice_action)

        self.addSeparator()

        # 登录豆包（文字动态切换）
        self._login_action = QAction(self)
        self._login_action.triggered.connect(self.login_requested.emit)
        self.addAction(self._login_action)

        # Claude 语音助手开关（可勾选）
        self._claude_notify_action = QAction("Claude 语音助手", self)
        self._claude_notify_action.setCheckable(True)
        self._claude_notify_action.setChecked(self._settings.claude_notify_enabled)
        self._claude_notify_action.triggered.connect(self._on_claude_notify_toggle)
        self.addAction(self._claude_notify_action)

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

    def _refresh_login_action(self) -> None:
        """根据当前 auth_token 状态更新登录菜单项文字。"""
        if self._settings.auth_token:
            self._login_action.setText("重新登录豆包")
        else:
            self._login_action.setText("登录豆包")

    def _on_voice_toggle(self) -> None:
        """切换语音识别开关。"""
        new_state = not self._settings.voice_enabled
        self._settings.voice_enabled = new_state
        self._refresh_voice_action()
        self.voice_toggled.emit(new_state)
        print(f"[PetMenu] 语音识别 → {'开启' if new_state else '关闭'}")

    def _on_claude_notify_toggle(self, checked: bool) -> None:
        """切换 Claude 语音助手开关。"""
        self.claude_notify_toggled.emit(checked)

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
            "按住右Ctrl 说话，松手输出文字\n"
            "使用豆包免费 ASR 服务\n\n"
            "技术栈: Python + PySide6 + WebSocket",
        )

    # ------------------------------------------------------------------
    # 弹出
    # ------------------------------------------------------------------

    def show_at(self, pos: QPoint) -> None:
        """在指定位置弹出菜单。弹出前自动刷新开关项和登录项文字。"""
        self._refresh_voice_action()
        self._refresh_login_action()
        self._claude_notify_action.setChecked(self._settings.claude_notify_enabled)
        self.popup(pos)
