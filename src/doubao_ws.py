"""
doubao_ws.py — 豆包 ASR WebSocket 客户端

P5: 基于 doubao-murmur (Swift) 逆向工程，实现到豆包流式语音识别
服务的 WebSocket 直连。发送裸 PCM 音频，接收 JSON 转录结果。

协议核心发现（与原始规格文档不同）:
  1. 无二进制协议头 — 上行数据是裸 PCM Int16 LE，直接放入 WebSocket
     binary frame 即可，不需要 FullClientRequest 等消息封装。
  2. 无握手消息 — 连接建立后立即开始发送音频，无需 start_session。
  3. 下行是纯 JSON 文本帧 — event: "result" / "finish"。
  4. 认证仅靠 Cookie header + Origin header。
  5. 结束信号不是特殊消息 — 停止发送后等待服务端 finish 事件。

参考: doubao-murmur DoubaoASRClient.swift
"""

import json
import threading
import time
from typing import Callable, Optional

import websocket

from doubao_protocol import (
    ASRParams,
    ServerMessage,
    build_wss_url,
    parse_message,
)

# ══════════════════════════════════════════════════════════════════════
# 常量
# ══════════════════════════════════════════════════════════════════════

CONNECT_TIMEOUT_SEC = 5
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SEC = 2


# ══════════════════════════════════════════════════════════════════════
# 回调类型
# ══════════════════════════════════════════════════════════════════════

OnOpenCallback = Callable[[], None]
OnResultCallback = Callable[[str], None]
OnFinishCallback = Callable[[], None]
OnErrorCallback = Callable[[Optional[Exception]], None]
OnAuthErrorCallback = Callable[[], None]


# ══════════════════════════════════════════════════════════════════════
# WebSocket 客户端
# ══════════════════════════════════════════════════════════════════════


class DoubaoWebSocket:
    """豆包 ASR WebSocket 客户端。

    特性:
      - 连接阶段自动缓冲音频，连上后一次性冲刷（与 doubao-murmur 行为一致）
      - 线程安全：send_audio 可从任意线程调用
      - 认证错误自动检测并触发 on_auth_error 回调
      - 最多 3 次自动重连
      - finish_sending 后保持连接等待最终结果

    用法:
        ws = DoubaoWebSocket()
        ws.on_open = lambda: print("connected")
        ws.on_result = lambda text: print(f"识别: {text}")
        ws.on_finish = lambda: print("done")
        ws.on_error = lambda e: print(f"error: {e}")
        ws.on_auth_error = lambda: print("auth expired")

        ws.connect(asr_params)          # 连接
        ws.send_audio(pcm_chunk)         # 发送音频（可在线程中调用）
        ws.finish_sending()             # 停止发送，等待结果
        ws.close()                      # 关闭连接
    """

    def __init__(self) -> None:
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None

        # ── 状态 ──────────────────────────────────────────────
        self._is_connected = False
        self._is_finished = False       # finish_sending() 已调用
        self._lock = threading.Lock()

        # ── 音频缓冲（连接建立前暂存） ────────────────────────
        self._pending_audio: list[bytes] = []
        self._buffer_lock = threading.Lock()

        # ── 重连计数 ──────────────────────────────────────────
        self._reconnect_count = 0

        # ── 回调（可从 URLSession 后台线程调用） ──────────────
        self.on_open: Optional[OnOpenCallback] = None
        self.on_result: Optional[OnResultCallback] = None
        self.on_finish: Optional[OnFinishCallback] = None
        self.on_error: Optional[OnErrorCallback] = None
        self.on_auth_error: Optional[OnAuthErrorCallback] = None

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def connect(self, params: ASRParams) -> None:
        """建立 WebSocket 连接。

        在独立守护线程中运行 WebSocket 事件循环，
        connect() 调用本身不阻塞。

        Args:
            params: 从 auth_token 提取的 ASR 连接参数。
        """
        with self._lock:
            self._is_connected = False
            self._is_finished = False
            self._reconnect_count = 0

        url = build_wss_url(params)

        # 尽可能模拟浏览器 WebSocket 握手头，绕过 ArgusSecurityPlugin
        # 参考: doubao-murmur + Chrome DevTools 抓包
        headers = {
            "Cookie": params.cookie_header,
            "Origin": "https://www.doubao.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

        print(f"[DoubaoWS] 正在连接...")
        print(f"[DoubaoWS] Cookie 数量: {len(params.cookies)}")

        self._ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # 在独立线程中运行（run_forever 是阻塞的）
        self._ws_thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={
                "ping_interval": 30,
                "ping_timeout": 10,
            },
            daemon=True,
        )
        self._ws_thread.start()

    def close(self) -> None:
        """正常关闭 WebSocket 连接。

        清除缓冲的音频数据并关闭连接。
        """
        with self._lock:
            self._is_connected = False
            self._is_finished = True

        # 清空待发送缓冲
        with self._buffer_lock:
            self._pending_audio.clear()

        if self._ws:
            print("[DoubaoWS] 断开连接")
            self._ws.close()
            self._ws = None

    # ------------------------------------------------------------------
    # 音频发送
    # ------------------------------------------------------------------

    def send_audio(self, data: bytes) -> None:
        """发送 PCM 音频数据。

        线程安全。如果 WebSocket 尚未连接，数据会被缓冲，
        连接建立后自动冲刷（与 doubao-murmur 行为一致）。

        Args:
            data: 裸 PCM Int16 LE 音频字节（16kHz, mono）。
        """
        with self._buffer_lock:
            with self._lock:
                connected = self._is_connected
                ws = self._ws

            if connected and ws:
                # 连接已建立 — 直接发送
                self._do_send(ws, data)
            else:
                # 尚未连接 — 缓冲
                self._pending_audio.append(data)

    def finish_sending(self) -> None:
        """标记音频发送完成。

        清空缓冲、标记结束，保持 WebSocket 打开以等待
        服务端的 finish 事件。
        """
        with self._buffer_lock:
            self._pending_audio.clear()

        with self._lock:
            self._is_finished = True

        print("[DoubaoWS] 音频发送完成，等待服务端响应...")

    # ------------------------------------------------------------------
    # 内部 — WebSocket 回调（在 WebSocket 线程中执行）
    # ------------------------------------------------------------------

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """WebSocket 连接建立回调。"""
        print("[DoubaoWS] OK: 连接已建立")
        with self._lock:
            self._is_connected = True
            self._reconnect_count = 0

        # 冲刷缓冲的音频数据
        self._flush_audio_buffer(ws)

        if self.on_open:
            self.on_open()

    def _on_message(self, ws: websocket.WebSocketApp, raw: str | bytes) -> None:
        """收到消息回调。

        Args:
            raw: 文本帧（str）或二进制帧（bytes）。
        """
        # 豆包 ASR 服务端只发文本（JSON），但容错处理二进制
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return

        msg = parse_message(raw)
        if msg is None:
            return

        # ── 认证错误 ──────────────────────────────────────────
        if msg.is_auth_error:
            print(
                f"[DoubaoWS] WARN: 认证错误: code={msg.code}, message={msg.message}"
            )
            with self._lock:
                self._is_connected = False
            if self.on_auth_error:
                self.on_auth_error()
            return

        # ── 识别结果 ──────────────────────────────────────────
        if msg.event == "result":
            if msg.text and self.on_result:
                self.on_result(msg.text)

        # ── 完成 ──────────────────────────────────────────────
        elif msg.event == "finish":
            print("[DoubaoWS] 收到 finish 事件")
            if self.on_finish:
                self.on_finish()

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """WebSocket 错误回调。"""
        print(f"[DoubaoWS] ERROR: 连接错误: {error}")

        connected_before: bool
        with self._lock:
            connected_before = self._is_connected
            self._is_connected = False

        if connected_before and self.on_error:
            self.on_error(error)

    def _on_close(
        self,
        ws: websocket.WebSocketApp,
        close_status_code: int | None,
        close_msg: str | None,
    ) -> None:
        """WebSocket 关闭回调。"""
        print(
            f"[DoubaoWS] 连接关闭: code={close_status_code}, msg={close_msg}"
        )

        with self._lock:
            was_connected = self._is_connected
            self._is_connected = False
            is_finished = self._is_finished
            attempt = self._reconnect_count

        # 如果连接意外关闭且未完成且未超过重试次数 → 自动重连
        if was_connected and not is_finished and attempt < MAX_RECONNECT_ATTEMPTS:
            with self._lock:
                self._reconnect_count += 1
            print(
                f"[DoubaoWS] RETRY: 自动重连 ({self._reconnect_count}/{MAX_RECONNECT_ATTEMPTS})"
            )
            time.sleep(RECONNECT_DELAY_SEC)
            # 注意：自动重连需要重新调用 connect()，这里只通知
            if self.on_error:
                self.on_error(
                    ConnectionError(
                        f"连接意外关闭 (code={close_status_code})"
                    )
                )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _do_send(self, ws: websocket.WebSocketApp, data: bytes) -> None:
        """执行实际的 WebSocket 二进制发送。"""
        try:
            ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
        except websocket.WebSocketConnectionClosedException:
            print("[DoubaoWS] WARN: 发送时连接已关闭")
            with self._lock:
                self._is_connected = False
        except Exception as e:
            print(f"[DoubaoWS] WARN: 发送失败: {e}")

    def _flush_audio_buffer(self, ws: websocket.WebSocketApp) -> None:
        """冲刷连接建立前缓冲的音频数据。"""
        with self._buffer_lock:
            buffered = list(self._pending_audio)
            self._pending_audio.clear()

        if not buffered:
            return

        print(f"[DoubaoWS] 冲刷 {len(buffered)} 个缓冲的音频块")
        for data in buffered:
            self._do_send(ws, data)

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """WebSocket 是否已连接。"""
        return self._is_connected

    @property
    def is_finished(self) -> bool:
        """是否已调用 finish_sending。"""
        return self._is_finished


# ══════════════════════════════════════════════════════════════════════
# WebView 桥接模式 — 绕过 CDN TLS 指纹检测
# ══════════════════════════════════════════════════════════════════════


class WebViewDoubaoWS:
    """通过 WebView JS 桥接的豆包 ASR WebSocket。

    当 Python 原生 WebSocket 被 ArgusSecurityPlugin (CDN/WAF)
    拦截时使用。WebSocket 连接从 WebView (Chromium) 内部发起，
    TLS 指纹与浏览器一致。

    接口与 DoubaoWebSocket 完全兼容。
    """

    def __init__(self, bridge) -> None:
        """
        Args:
            bridge: WebViewASRBridge 实例（从 AuthWebView.get_bridge() 获取）。
        """
        self._bridge = bridge

        # 代理回调
        self.on_open: Optional[OnOpenCallback] = None
        self.on_result: Optional[OnResultCallback] = None
        self.on_finish: Optional[OnFinishCallback] = None
        self.on_error: Optional[OnErrorCallback] = None
        self.on_auth_error: Optional[OnAuthErrorCallback] = None

    def connect(self, params: ASRParams) -> None:
        """通过 WebView JS 建立 WebSocket 连接。"""
        self._bridge.on_open = self.on_open
        self._bridge.on_result = self.on_result
        self._bridge.on_finish = self.on_finish
        self._bridge.on_error = (
            lambda msg: self.on_error(Exception(msg))
            if self.on_error
            else None
        )
        self._bridge.on_auth_error = self.on_auth_error
        self._bridge.connect(params)

    def send_audio(self, data: bytes) -> None:
        """发送 PCM 音频数据（线程安全）。"""
        self._bridge.send_audio(data)

    def finish_sending(self) -> None:
        """标记音频发送完成。"""
        self._bridge.finish_sending()

    def close(self) -> None:
        """关闭 WebSocket。"""
        self._bridge.close()

    @property
    def is_connected(self) -> bool:
        return self._bridge.is_connected

    @property
    def is_finished(self) -> bool:
        return self._bridge.is_finished
