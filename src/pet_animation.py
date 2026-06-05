"""
pet_animation.py — 动画管理

P1: 管理桌宠动画状态切换（idle / listening / thinking）。
从 assets/ 加载 GIF 文件，通过 paintEvent 方式渲染到透明窗口。
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import QWidget


class PetAnimation:
    """桌宠动画状态机。

    每个状态映射到 assets/ 下的 GIF 文件：
        idle      → pet_idle.gif      (待机)
        listening → pet_listening.gif  (录音中)
        thinking  → pet_thinking.gif   (识别中)

    如果某状态的 GIF 不存在，自动回退到 idle。
    不创建 QLabel，而是将 QMovie 提供给父窗口的 paintEvent 直接绘制。
    """

    STATE_FILES = {
        "idle": "pet_idle.gif",
        "listening": "pet_listening.gif",
        "thinking": "pet_thinking.gif",
    }

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._current_state = "idle"
        self._movies: dict[str, QMovie] = {}

        self._load_movies()
        self.play("idle")

    # ------------------------------------------------------------------
    # 资源加载
    # ------------------------------------------------------------------

    def _load_movies(self) -> None:
        """从 assets/ 加载所有可用的 GIF 文件为 QMovie 对象。"""
        assets_dir = Path(__file__).parent.parent / "assets"
        for state, filename in self.STATE_FILES.items():
            path = assets_dir / filename
            if path.exists():
                movie = QMovie(str(path))
                movie.setCacheMode(QMovie.CacheMode.CacheAll)
                # 帧变化时触发父窗口重绘
                movie.frameChanged.connect(self._parent.update)
                self._movies[state] = movie
                print(f"[PetAnimation] 已加载: {filename}")
            else:
                print(f"[PetAnimation] {filename} 不存在，状态 '{state}' 将回退到 idle")

    # ------------------------------------------------------------------
    # 状态切换
    # ------------------------------------------------------------------

    def play(self, state: str) -> None:
        """切换到指定动画状态。"""
        target = state if state in self._movies else "idle"

        if target == self._current_state:
            return

        # 停止当前
        if self._current_state in self._movies:
            self._movies[self._current_state].stop()

        self._current_state = target
        self._movies[target].start()
        print(f"[PetAnimation] 播放: {target}")

    # ------------------------------------------------------------------
    # 提供给 paintEvent 的接口
    # ------------------------------------------------------------------

    @property
    def current_pixmap(self):
        """返回当前帧的 QPixmap，供 paintEvent 绘制。"""
        movie = self._movies.get(self._current_state)
        if movie is not None:
            return movie.currentPixmap()
        return None

    @property
    def current_state(self) -> str:
        return self._current_state

    @property
    def size(self) -> tuple[int, int]:
        """返回动画原始尺寸（从当前 movie 获取）。"""
        movie = self._movies.get(self._current_state)
        if movie is not None:
            pixmap = movie.currentPixmap()
            if not pixmap.isNull():
                return (pixmap.width(), pixmap.height())
        return (200, 200)
