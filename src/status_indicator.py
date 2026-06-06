"""
status_indicator.py — 状态浮窗

P8: 半透明浮窗，显示当前录音/识别/完成/失败状态，带淡入淡出动画。
位于屏幕底部居中，自动消失。
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout


class StatusIndicator(QWidget):
    """半透明状态浮窗。

    用法:
        indicator = StatusIndicator()
        indicator.show_status("listening")   # 一直显示到下一次调用
        indicator.show_status("thinking")
        indicator.show_status("done")        # 1 秒后自动消失
        indicator.show_status("error", "网络连接失败")  # 2 秒后自动消失
        indicator.hide_status()              # 立即隐藏
    """

    STATES = {
        "listening": ("🎤 正在聆听...", "#1976D2", 0),      # 蓝色，不自动消失
        "thinking":  ("🤔 识别中...",   "#7B1FA2", 0),      # 紫色，不自动消失
        "done":      ("✅ 已输入",      "#388E3C", 1500),   # 绿色，1.5 秒消失
        "error":     ("❌ 识别失败",    "#D32F2F", 2500),   # 红色，2.5 秒消失
        "idle":      None,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pet_window = None
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._fade_out)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._fading_out = False

        self._setup_ui()

    def set_pet_window(self, pet_window) -> None:
        self._pet_window = pet_window

    def _setup_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)

        self._label = QLabel("")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color: white; font-size: 15px; font-weight: 500;"
        )
        layout.addWidget(self._label)

        self.setFixedWidth(220)

    def _position_above_pet(self) -> None:
        """定位到桌宠上方居中；无桌宠引用时回退到屏幕底部居中。"""
        if self._pet_window is not None:
            pet_rect = self._pet_window.frameGeometry()
            x = pet_rect.center().x() - self.width() // 2
            y = pet_rect.top() - self.height() - 8
            self.move(x, y)
            return
        # 回退
        screen = QApplication.primaryScreen()
        if screen is None:
            self.move(600, 800)
            return
        geom = screen.availableGeometry()
        x = geom.center().x() - self.width() // 2
        y = geom.bottom() - 120
        self.move(x, y)

    def _set_color(self, hex_color: str) -> None:
        self.setStyleSheet(
            f"background-color: {hex_color}CC; border-radius: 18px;"
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def show_status(self, state: str, extra: str = "") -> None:
        """显示指定状态。state: listening / thinking / done / error / idle"""
        self._auto_hide_timer.stop()
        self._fading_out = False

        if state == "idle":
            self.hide_status()
            return

        cfg = self.STATES.get(state)
        if cfg is None:
            return

        text, color, duration_ms = cfg
        if extra:
            text = f"{text.split(' ')[0]} {extra}"

        self._label.setText(text)
        self._set_color(color)
        self.adjustSize()
        self._position_above_pet()

        # 淡入
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.88)
        self._fading_out = False
        self.show()
        self._fade_anim.start()

        if duration_ms > 0:
            self._auto_hide_timer.start(duration_ms)

    def hide_status(self) -> None:
        """立即淡出隐藏。"""
        self._auto_hide_timer.stop()
        self._fade_out()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _fade_out(self) -> None:
        if not self.isVisible():
            return
        self._fading_out = True
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._fading_out:
            self.hide()
            self._fading_out = False
