"""
app.py — 应用生命周期管理

P0: DoubaoPetApp 负责创建 QApplication、初始化托盘、管理应用启动/退出。
P1: 集成 PetWindow（透明置顶桌宠窗口）。
P4: 集成 AudioCapture + AudioBuffer 麦克风采集。
P6: 集成 HotkeyManager 全局热键（右Ctrl 长按）。
P7: 集成 TextOutput 文本注入到活动窗口。
P8: 全流程串联 + StatusIndicator 状态浮窗 + WebViewASRBridge 接入。
"""

from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from audio_buffer import AudioBuffer
from audio_capture import AudioCapture
from doubao_protocol import ASRParams
from hotkey import HotkeyManager, _post_text
from pet_window import PetWindow
from settings import Settings
from status_indicator import StatusIndicator
from text_output import TextOutput
from tray import TrayIcon


class DoubaoPetApp:
    """豆包桌宠主应用。"""

    def __init__(self) -> None:
        self._app = QApplication([])
        self._app.setApplicationName("豆包桌宠")
        self._app.setQuitOnLastWindowClosed(False)

        self.settings = Settings()

        # ── P4: 音频采集 ────────────────────────────────────────
        self.audio_buffer = AudioBuffer()
        self.audio_capture = AudioCapture(self.audio_buffer)

        # ── P1/P2: 桌宠窗口 ─────────────────────────────────────
        self.pet_window = PetWindow(settings=self.settings)
        self.pet_window.voice_toggled.connect(self._on_voice_toggled)
        self.pet_window.login_completed.connect(self._on_login_completed)
        self.pet_window.login_requested.connect(self._on_login_requested)
        self.pet_window.show()

        # ── 系统托盘 ────────────────────────────────────────────
        self.tray = TrayIcon()
        self._update_tray_tooltip(self.settings.voice_enabled)
        self.tray.quit_requested.connect(self.quit)
        self.tray.show()

        # ── P8: 状态浮窗 ────────────────────────────────────────
        self.status = StatusIndicator()
        self.status.set_pet_window(self.pet_window)

        # ── P6: 全局热键 ────────────────────────────────────────
        self.hotkey = HotkeyManager()
        self.hotkey.set_settings(self.settings)
        self.hotkey.set_tray(self.tray)
        self.hotkey.recording_started.connect(self._on_recording_started)
        self.hotkey.recording_stopped.connect(self._on_recording_stopped)
        self.hotkey.hotkey_conflict.connect(self._on_hotkey_conflict)

        # ── P7: 文本注入 ────────────────────────────────────────
        self.text_output = TextOutput()

        # ── P8: ASR 桥接（延迟初始化，登录后创建）────────────────
        self._asr_bridge = None
        self._auth_webview = None
        self._pending_target_hwnd: int = 0
        self._last_asr_text: str = ""

        # ── P8: 音频流式推送定时器（录音时每 100ms 推送一次）────────
        self._stream_timer = QTimer()
        self._stream_timer.setInterval(100)
        self._stream_timer.timeout.connect(self._push_audio_to_asr)

        self.hotkey.register()

        self._check_auth_expiry()

        # 有有效凭证时自动在后台静默创建 WebView，无需用户手动重新登录
        if self.settings.auth_token:
            self._auto_init_webview()

        if self.settings.first_run:
            self.settings.first_run = False
            print("[App] 首次运行，已标记 first_run = False")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def run(self) -> int:
        return self._app.exec()

    def quit(self) -> None:
        print("[App] 正在退出...")
        self._stream_timer.stop()
        self.audio_capture.stop()
        self.hotkey.cleanup()
        self.pet_window.close()
        self.tray.hide()
        self.status.hide()
        if self._auth_webview is not None:
            self._auth_webview.destroy_background()
        self._app.quit()

    # ------------------------------------------------------------------
    # P2: 语音开关联动
    # ------------------------------------------------------------------

    def _on_voice_toggled(self, enabled: bool) -> None:
        self._update_tray_tooltip(enabled)

    def _update_tray_tooltip(self, enabled: bool) -> None:
        status = "语音已开启" if enabled else "语音已关闭"
        self.tray.set_tooltip(f"豆包桌宠 — {status}")
        print(f"[App] 托盘 tooltip → {status}")

    # ------------------------------------------------------------------
    # P6: 热键 → 录音联动
    # ------------------------------------------------------------------

    def _on_recording_started(self) -> None:
        """右Ctrl 长按确认 → 开始录音，连接 ASR，启动流式推送。"""
        print("[App] 录音开始")
        self.audio_buffer.clear()
        self.audio_capture.start()
        self.pet_window.animation.play("listening")
        self.status.show_status("listening")

        bridge = self._get_or_create_bridge()
        if bridge is None:
            print("[App] ASR 桥接不可用，跳过连接")
            return

        params = ASRParams.from_auth_token(self.settings.auth_token)
        if params is None:
            print("[App] ASR 参数提取失败，跳过连接")
            self.tray.show_message("豆包桌宠", "凭证无效，请重新登录豆包")
            return

        bridge.on_result = self._on_asr_result
        bridge.on_finish = self._on_asr_finish
        bridge.on_error = self._on_asr_error
        bridge.on_auth_error = self._on_asr_auth_error

        self._last_asr_text = ""
        bridge.connect(params)
        self._stream_timer.start()  # 开始每 100ms 推送音频

    def _on_recording_stopped(self, target_hwnd: int) -> None:
        """松手 / 超时 → 停止录音，直接注入已识别文本，不等 finish 事件。"""
        print("[App] 录音停止")
        self._stream_timer.stop()
        self.audio_capture.stop()
        self.pet_window.animation.play("idle")
        self.status.show_status("thinking")

        bridge = self._asr_bridge
        if bridge is not None:
            remaining = self.audio_buffer.read_all()
            if remaining:
                bridge.send_audio(remaining)
            bridge.finish_sending()

        # 松手时 _last_asr_text 已有最新识别结果（流式实时更新）
        # 不依赖 finish 事件，直接注入，与 P7 验收方案一致
        text = self._last_asr_text.strip()
        print(f"[App] 注入文本: {text!r}")
        if text and target_hwnd:
            self.status.show_status("done")
            _post_text(target_hwnd, text)
        elif not text:
            self.status.show_status("idle")

        self._last_asr_text = ""

    def _on_hotkey_conflict(self, message: str) -> None:
        self.tray.show_message("热键冲突", message)

    # ------------------------------------------------------------------
    # P8: 音频 → ASR 流式推送（QTimer 每 100ms 触发）
    # ------------------------------------------------------------------

    def _push_audio_to_asr(self) -> None:
        """定时从缓冲区读取音频块并推送给 ASR 桥接。"""
        bridge = self._asr_bridge
        if bridge is None:
            return
        chunk = self.audio_buffer.read_all()
        if chunk:
            bridge.send_audio(chunk)

    # ------------------------------------------------------------------
    # P8: ASR 回调
    # ------------------------------------------------------------------

    def _on_asr_result(self, text: str) -> None:
        """收到流式识别结果（可能多次调用，每次是最新完整文本）。"""
        print(f"[App] ASR 结果: {text!r}")
        self._last_asr_text = text

    def _on_asr_finish(self) -> None:
        """ASR 识别完成，注入最终文本。"""
        text = self._last_asr_text.strip()
        print(f"[App] ASR 完成，最终文本: {text!r}")

        if text:
            self.status.show_status("done")
            if self._pending_target_hwnd:
                _post_text(self._pending_target_hwnd, text)
            else:
                print("[App] 无目标窗口句柄，跳过注入")
        else:
            self.status.show_status("error", "未识别到语音")
            print("[App] 识别结果为空")

        self._pending_target_hwnd = 0
        self._last_asr_text = ""

    def _on_asr_error(self, msg: str) -> None:
        print(f"[App] ASR 错误: {msg}")
        self.status.show_status("error")
        self._pending_target_hwnd = 0

    def _on_asr_auth_error(self) -> None:
        print("[App] ASR 认证失败，凭证已过期")
        self.status.show_status("error", "请重新登录")
        self.settings.auth_token = None
        self.settings.auth_expiry = None
        self.tray.show_message("豆包桌宠", "登录已过期，请重新登录豆包")
        self._asr_bridge = None
        self._pending_target_hwnd = 0

    # ------------------------------------------------------------------
    # P8: ASR 桥接 — 延迟初始化
    # ------------------------------------------------------------------

    def _get_or_create_bridge(self):
        """获取 ASR 桥接实例；若 WebView 不存在则无法创建，返回 None。"""
        if self._asr_bridge is not None:
            return self._asr_bridge

        if self._auth_webview is not None:
            self._asr_bridge = self._auth_webview.get_bridge()
            return self._asr_bridge

        print("[App] 尚未登录豆包，无法创建 ASR 桥接")
        return None

    def _auto_init_webview(self) -> None:
        """启动时自动在后台静默创建 WebView，复用已有 profile session。

        用户上次登录的 session 由 QWebEngineProfile("doubao-pet") 持久化在
        磁盘上，Chromium 启动时自动加载，不需要用户重新登录。
        """
        from auth_webview import AuthWebView
        print("[App] 检测到有效凭证，自动在后台初始化 WebView...")
        dlg = AuthWebView(self.settings, keep_alive=True)
        dlg._extracted = True          # 跳过登录检测
        dlg._poll_timer.stop()
        dlg._move_to_background()
        self._auth_webview = dlg
        print("[App] 后台 WebView 已就绪，可直接使用语音功能")

    # ------------------------------------------------------------------
    # P3: 登录 & 凭证管理
    # ------------------------------------------------------------------

    def _on_login_requested(self) -> None:
        """处理登录请求：先销毁旧后台 WebView，再弹出登录窗口。

        必须在 app 层处理，因为 QWebEngineProfile("doubao-pet") 是进程级单例，
        同时存在两个绑定该 profile 的 WebView 会导致新窗口全白无法交互。
        """
        from auth_webview import AuthWebView

        # 先销毁后台 WebView，释放 profile 占用
        if self._auth_webview is not None:
            print("[App] 销毁旧后台 WebView，准备重新登录...")
            self._auth_webview.destroy_background()
            self._auth_webview = None
            self._asr_bridge = None

        dlg = AuthWebView(self.settings, self.pet_window)
        dlg.login_completed.connect(lambda: self._on_auth_dialog_accepted(dlg))
        dlg.exec()

    def _on_auth_dialog_accepted(self, dlg) -> None:
        """登录弹窗完成后更新引用并通知其他模块。"""
        self._auth_webview = dlg
        self._asr_bridge = None  # 下次录音时重新从新 WebView 取 bridge
        self.pet_window.update()
        self.pet_window.login_completed.emit()
        self.tray.show_message("登录成功", "豆包凭证已保存，有效期 7 天")
        print("[App] 登录完成，凭证已保存，新 WebView 已就绪")

    def _on_login_completed(self) -> None:
        """保留此信号槽供 pet_window.login_completed 转发时使用。"""
        pass

    def _check_auth_expiry(self) -> None:
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
            self.tray.show_message("豆包桌宠", "登录已过期，请重新登录豆包")
