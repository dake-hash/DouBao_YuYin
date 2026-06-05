"""
pet_window.py — 桌宠窗口

P1: 透明、置顶、无边框、可拖动的桌面宠物窗口。
通过 paintEvent 直接绘制 GIF 帧，彻底解决透明渲染问题。
支持区分「拖动」和「点击」操作。
P2: 集成 PetMenu 点击菜单 + 语音开关状态指示器。
"""

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from pet_animation import PetAnimation


class PetWindow(QWidget):
    """透明桌面宠物窗口。

    特性:
        - 无边框 + 透明背景 → 仅宠物角色可见
        - 始终置顶（在所有窗口上方）
        - 初始位置: 屏幕右下角
        - 可拖动到任意位置
        - 区分拖动与点击（移动 < 5px 视为点击）
        - 点击弹出语音开关菜单（P2）

    Signals:
        voice_toggled(bool):  语音开关状态变化时发射
    """

    DRAG_THRESHOLD = 5

    # 指示器样式
    INDICATOR_RADIUS = 6
    INDICATOR_MARGIN = 8
    INDICATOR_ON = QColor("#00E676")   # 绿色 — 语音已开启
    INDICATOR_OFF = QColor("#9E9E9E")  # 灰色 — 语音已关闭

    voice_toggled = Signal(bool)
    login_completed = Signal()

    def __init__(self, settings=None, size: int = 200) -> None:
        super().__init__()
        self._settings = settings
        self._drag_start_global: QPoint | None = None
        self._drag_start_pos: QPoint | None = None
        self._was_dragged = False

        self._setup_ui(size)
        self._position_bottom_right()

    # ------------------------------------------------------------------
    # UI 初始化
    # ------------------------------------------------------------------

    def _setup_ui(self, size: int) -> None:
        """配置无边框透明窗口。"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(size, size)

        # 动画管理器（不创建 QLabel，通过 paintEvent 绘制）
        self.animation = PetAnimation(self)

    def _position_bottom_right(self) -> None:
        """将窗口定位到主屏幕右下角（距边缘 20px）。"""
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            x = geom.right() - self.width() - 20
            y = geom.bottom() - self.height() - 20
        else:
            x, y = 1000, 600
        print(f"[PetWindow] 初始位置: ({x}, {y})")
        self.move(x, y)

    # ------------------------------------------------------------------
    # 绘制（透明背景 + GIF 帧）
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """直接在透明窗口上绘制当前动画帧 + 语音状态指示器。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pixmap = self.animation.current_pixmap
        if pixmap is not None and not pixmap.isNull():
            # 将 GIF 帧缩放到窗口大小
            scaled = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 居中绘制
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # 保底：画一个紫色圆形，至少能看到东西
            painter.setBrush(QColor("#6C5CE7"))
            painter.setPen(QPen(QColor("#4A3DB5"), 2))
            cx, cy = self.width() // 2, self.height() // 2
            r = min(cx, cy) - 4
            painter.drawEllipse(QPoint(cx, cy), r, r)

        # P2: 语音状态指示器（右上角圆点）
        self._draw_indicator(painter)

        painter.end()

    def _draw_indicator(self, painter: QPainter) -> None:
        """在窗口右上角绘制语音状态指示圆点。"""
        if self._settings is None:
            return

        enabled = self._settings.voice_enabled
        color = self.INDICATOR_ON if enabled else self.INDICATOR_OFF

        # 右上角定位
        cx = self.width() - self.INDICATOR_MARGIN - self.INDICATOR_RADIUS
        cy = self.INDICATOR_MARGIN + self.INDICATOR_RADIUS

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawEllipse(QPoint(cx, cy), self.INDICATOR_RADIUS, self.INDICATOR_RADIUS)

    # ------------------------------------------------------------------
    # 拖动 & 点击
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()
            self._was_dragged = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_global is not None:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            if delta.manhattanLength() >= self.DRAG_THRESHOLD:
                self._was_dragged = True
            if self._was_dragged:
                self.move(self._drag_start_pos + delta)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._was_dragged:
                self._on_clicked()
            self._drag_start_global = None
            self._drag_start_pos = None

    def _on_clicked(self) -> None:
        """点击桌宠回调 — 弹出语音开关菜单。"""
        if self._settings is None:
            print("[PetWindow] 桌宠被点击（无 settings 引用，无法弹出菜单）")
            return

        from pet_menu import PetMenu

        menu = PetMenu(self, self._settings)
        menu.voice_toggled.connect(self._on_voice_toggled)
        menu.login_requested.connect(self._on_login_requested)
        menu.quit_requested.connect(QApplication.instance().quit)

        # 在鼠标点击位置弹出菜单
        cursor_pos = self.cursor().pos()
        global_pos = self.mapToGlobal(cursor_pos)
        menu.show_at(global_pos)

    def _on_voice_toggled(self, enabled: bool) -> None:
        """语音开关切换后刷新指示器并转发信号。"""
        self.update()  # 重绘指示器
        self.voice_toggled.emit(enabled)
        print(f"[PetWindow] 语音{'已开启' if enabled else '已关闭'}")

    def _on_login_requested(self) -> None:
        """打开豆包登录窗口，完成后重绘指示器并转发信号。"""
        from auth_webview import AuthWebView

        dlg = AuthWebView(self._settings, self)
        if dlg.exec() == AuthWebView.DialogCode.Accepted:
            self.update()  # 指示器状态可能变化
            self.login_completed.emit()
            print("[PetWindow] 登录完成")
