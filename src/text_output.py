"""
text_output.py — 文本注入到活动窗口

P7: 剪贴板 + Ctrl+V 方案，注入前通过 AttachThreadInput 恢复目标窗口焦点。
    备用方案：SendInput Unicode 逐字符。
"""

import time
import ctypes
from ctypes import wintypes
from typing import Optional

import win32clipboard
import win32con


# ------------------------------------------------------------------
# Win32 常量
# ------------------------------------------------------------------

_INPUT_KEYBOARD   = 1
_KEYEVENTF_KEYUP  = 0x0002
_KEYEVENTF_UNICODE = 0x0004

_user32   = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32


# ------------------------------------------------------------------
# SendInput 结构体
# ------------------------------------------------------------------

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_", _INPUT_UNION)]


def _send_vk(vk: int, flags: int = 0) -> None:
    inp = _INPUT()
    inp.type = _INPUT_KEYBOARD
    inp._.ki.wVk = vk
    inp._.ki.dwFlags = flags
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_unicode_char(ch: str) -> None:
    code = ord(ch)
    for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
        inp = _INPUT()
        inp.type = _INPUT_KEYBOARD
        inp._.ki.wVk = 0
        inp._.ki.wScan = code & 0xFFFF
        inp._.ki.dwFlags = flags
        _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ------------------------------------------------------------------
# TextOutput
# ------------------------------------------------------------------

class TextOutput:
    """将文本注入到目标窗口。

    流程：
      1. 把文本写入剪贴板
      2. 用 SetForegroundWindow + AllowSetForegroundWindow 把目标窗口切到前台
      3. 发送 Ctrl+V
      4. 恢复原剪贴板
    """

    def output(self, text: str, target_hwnd: int = 0) -> bool:
        if not text:
            return False
        print(f"[TextOutput] 注入文本: {text!r}")
        success = self._paste_via_clipboard(text, target_hwnd)
        if not success:
            print("[TextOutput] 剪贴板方案失败，回退到 SendInput")
            if target_hwnd:
                self._restore_foreground(target_hwnd)
            self._paste_via_sendinput(text)
        return True

    # ------------------------------------------------------------------
    # 剪贴板 + Ctrl+V
    # ------------------------------------------------------------------

    def _paste_via_clipboard(self, text: str, target_hwnd: int) -> bool:
        original = self._clipboard_get()
        try:
            self._clipboard_set(text)
            if target_hwnd:
                ok = self._restore_foreground(target_hwnd)
                if not ok:
                    return False
            # Ctrl+V
            _send_vk(win32con.VK_CONTROL)
            _send_vk(ord('V'))
            _send_vk(ord('V'), _KEYEVENTF_KEYUP)
            _send_vk(win32con.VK_CONTROL, _KEYEVENTF_KEYUP)
            time.sleep(0.15)
            return True
        except Exception as e:
            print(f"[TextOutput] 剪贴板方案异常: {e}")
            return False
        finally:
            if original is not None:
                try:
                    self._clipboard_set(original)
                except Exception:
                    pass

    def _restore_foreground(self, hwnd: int) -> bool:
        """把目标窗口切到前台，返回是否成功。"""
        # AllowSetForegroundWindow 让其他进程可以切前台
        _user32.AllowSetForegroundWindow(0xFFFFFFFF)
        result = _user32.SetForegroundWindow(hwnd)
        time.sleep(0.08)
        actual = _user32.GetForegroundWindow()
        if actual != hwnd:
            print(f"[TextOutput] SetForegroundWindow 被系统拒绝 "
                  f"(target={hwnd:#x}, actual={actual:#x})")
            return False
        return True

    # ------------------------------------------------------------------
    # 剪贴板读写
    # ------------------------------------------------------------------

    def _clipboard_get(self) -> Optional[str]:
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        except Exception:
            return None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _clipboard_set(self, text: str) -> None:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    # ------------------------------------------------------------------
    # SendInput Unicode（备用）
    # ------------------------------------------------------------------

    def _paste_via_sendinput(self, text: str) -> None:
        for ch in text:
            _send_unicode_char(ch)
            time.sleep(0.005)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def get_active_window(self) -> Optional[int]:
        hwnd = _user32.GetForegroundWindow()
        return hwnd if hwnd else None
