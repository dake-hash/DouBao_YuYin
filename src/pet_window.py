"""
pet_window.py — 桌宠窗口

P1: 透明、置顶、无边框、可拖动的桌面宠物窗口。
通过 paintEvent 直接绘制 GIF 帧，彻底解决透明渲染问题。
支持区分「拖动」和「点击」操作。
"""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent, QPainter
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
    """

    DRAG_THRESHOLD = 5

    def __init__(self, size: int = 200) -> None:
        super().__init__()
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
        """直接在透明窗口上绘制当前动画帧。"""
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
            from PySide6.QtGui import QColor, QBrush, QPen
            painter.setBrush(QColor("#6C5CE7"))
            painter.setPen(QPen(QColor("#4A3DB5"), 2))
            cx, cy = self.width() // 2, self.height() // 2
            r = min(cx, cy) - 4
            painter.drawEllipse(QPoint(cx, cy), r, r)

        painter.end()

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
        """点击桌宠回调。P1 仅打日志，P2 改为弹出菜单。"""
        print("[PetWindow] 桌宠被点击")
