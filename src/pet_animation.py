"""
pet_animation.py — 动画管理

P1: 管理桌宠动画状态切换（idle / listening / thinking）。
从 assets/ 加载 GIF 文件，通过 paintEvent 方式渲染到透明窗口。
支持 GIF（动画）和 PNG（静态图）两种格式，GIF 优先。
"""

from pathlib import Path

from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QWidget


class PetAnimation:
    """桌宠动画状态机。

    每个状态优先加载 .gif，不存在则尝试 .png：
        idle      → pet_idle.gif / pet_idle.png
        listening → pet_listening.gif / pet_listening.png
        thinking  → pet_thinking.gif / pet_thinking.png

    不存在则自动回退到 idle。
    """

    STATE_FILES = {
        "idle":      ["pet_idle.gif",  "pet.gif",         "pet_idle.png"],
        "listening": ["listen.gif",    "pet_listening.gif", "listen.png"],
        "thinking":  ["pet_thinking.gif", "think.png"],
    }

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._current_state = ""  # 空字符串确保首次 play("idle") 不被跳过
        self._movies: dict[str, QMovie] = {}
        self._pixmaps: dict[str, QPixmap] = {}

        self._load_assets()
        self.play("idle")

    def _load_assets(self) -> None:
        assets_dir = Path(__file__).parent.parent / "assets"
        for state, filenames in self.STATE_FILES.items():
            for filename in filenames:
                path = assets_dir / filename
                if not path.exists():
                    continue
                if filename.endswith(".gif"):
                    movie = QMovie(str(path))
                    movie.setCacheMode(QMovie.CacheMode.CacheAll)
                    movie.frameChanged.connect(self._parent.update)
                    self._movies[state] = movie
                else:
                    self._pixmaps[state] = QPixmap(str(path))
                print(f"[PetAnimation] 已加载: {filename}")
                break
            else:
                print(f"[PetAnimation] 无素材，状态 '{state}' 将回退到 idle")

    def play(self, state: str) -> None:
        if state not in self._movies and state not in self._pixmaps:
            state = "idle"
        if state == self._current_state:
            return
        if self._current_state in self._movies:
            self._movies[self._current_state].stop()
        self._current_state = state
        if state in self._movies:
            self._movies[state].start()

    @property
    def current_pixmap(self):
        if self._current_state in self._movies:
            return self._movies[self._current_state].currentPixmap()
        if self._current_state in self._pixmaps:
            return self._pixmaps[self._current_state]
        if "idle" in self._pixmaps:
            return self._pixmaps["idle"]
        return None

    @property
    def current_state(self) -> str:
        return self._current_state

    @property
    def size(self) -> tuple[int, int]:
        movie = self._movies.get(self._current_state)
        if movie is not None:
            px = movie.currentPixmap()
            if not px.isNull():
                return (px.width(), px.height())
        px = self._pixmaps.get(self._current_state)
        if px is not None and not px.isNull():
            return (px.width(), px.height())
        return (200, 200)
