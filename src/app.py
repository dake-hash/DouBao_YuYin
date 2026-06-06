"""
app.py — 应用生命周期管理

P0: DoubaoPetApp 负责创建 QApplication、初始化托盘、管理应用启动/退出。
P1: 集成 PetWindow（透明置顶桌宠窗口）。
P4: 集成 AudioCapture + AudioBuffer 麦克风采集。
P6: 集成 HotkeyManager 全局热键（右Shift 长按）。
"""

from datetime import datetime, timezone

from PySide6.QtWidgets import QApplication

from audio_buffer import AudioBuffer
from audio_capture import AudioCapture
from hotkey import HotkeyManager
from pet_window import PetWindow
from settings import Settings
from tray import TrayIcon


class DoubaoPetApp:
    """豆包桌宠主应用。

    职责:
        - 创建 QApplication（不依赖系统命令行参数）
        - 初始化 Settings、PetWindow、TrayIcon
        - 初始化 AudioBuffer、AudioCapture、HotkeyManager
        - 编排各模块生命周期
        - 连接托盘「退出」信号 → 优雅退出
        - 首次运行时标记 first_run = False
    """

    def __init__(self) -> None:
        # Qt 应用（不传 sys.argv 避免与 Python 参数混淆）
        self._app = QApplication([])
        self._app.setApplicationName("豆包桌宠")
        self._app.setQuitOnLastWindowClosed(False)

        # 设置
        self.settings = Settings()

        # ── P4: 音频采集 ────────────────────────────────────────
        self.audio_buffer = AudioBuffer()
        self.audio_capture = AudioCapture(self.audio_buffer)

        # ── 桌宠窗口（P1 → P2: 集成 settings + 语音开关菜单）───
        self.pet_window = PetWindow(settings=self.settings)
        self.pet_window.voice_toggled.connect(self._on_voice_toggled)
        self.pet_window.login_completed.connect(self._on_login_completed)
        self.pet_window.show()

        # ── 系统托盘 ────────────────────────────────────────────
        self.tray = TrayIcon()
        self._update_tray_tooltip(self.settings.voice_enabled)
        self.tray.quit_requested.connect(self.quit)
        self.tray.show()

        # ── P6: 全局热键（右Shift 长按）─────────────────────────
        self.hotkey = HotkeyManager()
        self.hotkey.set_settings(self.settings)
        self.hotkey.set_tray(self.tray)
        self.hotkey.recording_started.connect(self._on_recording_started)
        self.hotkey.recording_stopped.connect(self._on_recording_stopped)
        self.hotkey.hotkey_conflict.connect(self._on_hotkey_conflict)
        self.hotkey.register()

        # P3: 启动时检查凭证是否过期
        self._check_auth_expiry()

        # 首次运行标记
        if self.settings.first_run:
            self.settings.first_run = False
            print("[App] 首次运行，已标记 first_run = False")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def run(self) -> int:
        """进入 Qt 事件循环。返回 exit code。"""
        return self._app.exec()

    def quit(self) -> None:
        """优雅退出：停止录音 → 注销热键 → 关闭桌宠 → 隐藏托盘 → 退出 Qt。"""
        print("[App] 正在退出...")
        self.audio_capture.stop()
        self.hotkey.cleanup()
        self.pet_window.close()
        self.tray.hide()
        self._app.quit()

    # ------------------------------------------------------------------
    # P2: 语音开关联动
    # ------------------------------------------------------------------

    def _on_voice_toggled(self, enabled: bool) -> None:
        """语音开关切换时更新托盘提示。"""
        self._update_tray_tooltip(enabled)

    def _update_tray_tooltip(self, enabled: bool) -> None:
        """根据语音开关状态更新托盘 tooltip。"""
        status = "语音已开启" if enabled else "语音已关闭"
        self.tray.set_tooltip(f"豆包桌宠 — {status}")
        print(f"[App] 托盘 tooltip → {status}")

    # ------------------------------------------------------------------
    # P6: 热键 → 录音联动
    # ------------------------------------------------------------------

    def _on_recording_started(self) -> None:
        """右Shift 长按确认 → 开始麦克风采集。"""
        self.audio_buffer.clear()
        self.audio_capture.start()

    def _on_recording_stopped(self) -> None:
        """松手 / 超时 → 停止麦克风采集，打印缓冲区统计。"""
        self.audio_capture.stop()
        available = self.audio_buffer.available_bytes
        print(f"[App] 录音结束，缓冲区数据: {available} bytes "
              f"({available / 32000:.1f} 秒 @ 16kHz mono)")

    def _on_hotkey_conflict(self, message: str) -> None:
        """热键注册失败时通知用户。"""
        self.tray.show_message("热键冲突", message)

    # ------------------------------------------------------------------
    # P3: 登录 & 凭证管理
    # ------------------------------------------------------------------

    def _on_login_completed(self) -> None:
        """登录成功后刷新托盘提示。"""
        self.tray.show_message("登录成功", "豆包凭证已保存，有效期 7 天")
        print("[App] 登录完成，凭证已保存")

    def _check_auth_expiry(self) -> None:
        """检查凭证是否过期，过期则弹出托盘通知。"""
        expiry_str = self.settings.auth_expiry
        if not expiry_str:
            return

        try:
            expiry = datetime.fromisoformat(expiry_str)
        except (ValueError, TypeError):
            return

        now = datetime.now(timezone.utc)
        if now > expiry:
            print("[App] 凭证已过期")
            self.settings.auth_token = None
            self.settings.auth_expiry = None
            self.tray.show_message(
                "豆包桌宠",
                "登录已过期，请重新登录豆包",
            )
