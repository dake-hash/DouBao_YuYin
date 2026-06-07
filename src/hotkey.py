"""
hotkey.py — 全局热键监听（右Ctrl 长按录音）

P6: 使用 pynput 监听键盘事件。
P7: 长按触发，松手停止。用 PostMessage WM_CHAR 直接投递文本到目标窗口，不依赖焦点。

逻辑：
    按下右Ctrl → 记录目标窗口，启动 200ms 计时
    200ms 内松手  → 短按，取消
    超过 200ms 未松手 → 开始录音
    松手 → 停止录音，注入文本
    录音超过 30 秒 → 自动停止，注入文本
"""

import ctypes
import threading
import time
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

try:
    from pynput import keyboard as _kb
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

_user32 = ctypes.windll.user32
WM_CHAR = 0x0102


def _get_focus_child(hwnd: int) -> int:
    """通过 AttachThreadInput 获取目标窗口的焦点子窗口句柄。"""
    current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    target_tid = _user32.GetWindowThreadProcessId(hwnd, None)
    if target_tid and target_tid != current_tid:
        _user32.AttachThreadInput(current_tid, target_tid, True)
        try:
            child = _user32.GetFocus()
            return child if child else hwnd
        finally:
            _user32.AttachThreadInput(current_tid, target_tid, False)
    return hwnd


def _post_text(hwnd: int, text: str) -> None:
    """直接向目标窗口投递字符，不依赖焦点。"""
    target = _get_focus_child(hwnd)
    for ch in text:
        _user32.PostMessageW(target, WM_CHAR, ord(ch), 0)
        time.sleep(0.002)


class HotkeyManager(QObject):
    """右Ctrl 长按录音管理器。

    信号:
        recording_started:  长按确认，开始录音
        recording_stopped:  松手或超时，停止录音
        hotkey_conflict(str): 保留接口兼容
    """

    recording_started = Signal()
    recording_stopped = Signal(int)   # 携带目标窗口 hwnd
    hotkey_conflict = Signal(str)

    HOLD_THRESHOLD_MS = 200
    POLL_INTERVAL_MS = 50
    MAX_RECORD_SECONDS = 30

    IDLE = 0
    WAITING_THRESHOLD = 1
    RECORDING = 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state: int = self.IDLE
        self._registered: bool = False
        self._listener: Optional[object] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._press_time: Optional[float] = None
        self._target_hwnd: int = 0
        self._settings = None
        self._tray = None
        self._inject_fn: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # 依赖注入
    # ------------------------------------------------------------------

    def set_settings(self, settings) -> None:
        self._settings = settings

    def set_tray(self, tray) -> None:
        self._tray = tray

    def set_inject_fn(self, fn: Callable[[str], None]) -> None:
        self._inject_fn = fn

    # ------------------------------------------------------------------
    # 注册 / 注销
    # ------------------------------------------------------------------

    def register(self) -> bool:
        if not HAS_PYNPUT:
            print("[Hotkey] pynput 不可用，跳过热键注册")
            return False
        if self._registered:
            return True

        self._listener = _kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        self._registered = True
        print("[Hotkey] [OK] 右Ctrl 热键注册成功")
        return True

    def unregister(self) -> None:
        if not self._registered:
            return
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._registered = False
        self._stop_event.set()
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1.0)
        self._state = self.IDLE
        print("[Hotkey] 热键已注销")

    # ------------------------------------------------------------------
    # pynput 回调
    # ------------------------------------------------------------------

    def _on_press(self, key) -> None:
        if key != _kb.Key.ctrl_r:
            return
        if self._state != self.IDLE:
            return
        print("[Hotkey] 识别到按键")

        if self._settings is not None and not self._settings.voice_enabled:
            print("[Hotkey] 语音未开启，忽略热键")
            return

        if self._settings is not None and not self._settings.auth_token:
            print("[Hotkey] 未登录豆包，忽略热键")
            if self._tray is not None:
                self._tray.show_message("豆包桌宠", "请先登录豆包")
            return

        # 按键前记录目标窗口（此时焦点还在用户的目标窗口）
        self._target_hwnd = _user32.GetForegroundWindow()

        self._state = self.WAITING_THRESHOLD
        self._press_time = time.monotonic()
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, args=(self._press_time,), daemon=True,
        )
        self._poll_thread.start()

    def _on_release(self, key) -> None:
        if key != _kb.Key.ctrl_r:
            return
        self._stop_event.set()

    # ------------------------------------------------------------------
    # 后台轮询线程
    # ------------------------------------------------------------------

    def _poll_loop(self, press_time: float) -> None:
        # 阶段 1: 等待 200ms 阈值
        deadline = press_time + self.HOLD_THRESHOLD_MS / 1000.0
        while not self._stop_event.is_set():
            if time.monotonic() >= deadline:
                break
            time.sleep(self.POLL_INTERVAL_MS / 1000.0)

        if self._stop_event.is_set():
            print("[Hotkey] 短按（< 200ms），取消")
            self._state = self.IDLE
            return

        # 阶段 2: 开始录音
        self._state = self.RECORDING
        self.recording_started.emit()
        print("[Hotkey] 长按确认，开始录音")

        recording_start = time.monotonic()

        # 阶段 3: 等待松手 / 30 秒超时
        while not self._stop_event.is_set():
            if time.monotonic() - recording_start >= self.MAX_RECORD_SECONDS:
                print("[Hotkey] 超过 30 秒，自动停止")
                break
            time.sleep(self.POLL_INTERVAL_MS / 1000.0)

        if not (time.monotonic() - recording_start >= self.MAX_RECORD_SECONDS):
            print("[Hotkey] 松手，停止录音")

        # 阶段 4: 停止录音，emit 信号通知 app.py（携带目标窗口句柄）
        self._state = self.IDLE
        self.recording_stopped.emit(self._target_hwnd)

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self.unregister()
