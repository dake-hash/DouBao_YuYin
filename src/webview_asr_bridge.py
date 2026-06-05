"""
webview_asr_bridge.py — WebView JS WebSocket 桥接层

P5 补充: 当 Python 原生 websocket-client 被 ArgusSecurityPlugin (CDN/WAF)
因 TLS 指纹拦截时，改为从 QWebEngineView 内部的 JavaScript 发起 WebSocket
连接。WebView 使用 Chromium 网络栈，TLS 指纹与浏览器一致，不会被拦。

通信机制 (对应 doubao-murmur 的 WKScriptMessageHandler):
  - Python → JS: QWebChannel Signal → JS 回调
  - JS → Python: JS 调用 QWebChannel Slot → Python 方法
"""

import base64
import json
import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from doubao_protocol import ASRParams, build_wss_url

# ══════════════════════════════════════════════════════════════════════
# QWebChannel Bridge Object (Python ↔ JS)
# ══════════════════════════════════════════════════════════════════════


class _ASRBridgeObject(QObject):
    """QWebChannel 桥接对象 — JS 通过 QWebChannel 与此对象交互。"""

    # Python → JS 信号
    audioData = Signal(str)              # base64 PCM chunk
    finishSending = Signal()             # 音频发送完成
    connectASR = Signal(str, str, str)   # (wss_url, cookie_header, preloaded_b64)
    closeASR = Signal()                  # 关闭连接

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_result: Optional[Callable[[str], None]] = None
        self._on_finish: Optional[Callable[[], None]] = None
        self._on_open: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_auth_error: Optional[Callable[[str], None]] = None
        self._on_channel_ready: Optional[Callable[[], None]] = None

    # ── JS → Python 槽 ──────────────────────────────────────

    @Slot()
    def onChannelReady(self) -> None:
        """JS 调用: QWebChannel 握手完成，JS 已准备好接收信号。"""
        if self._on_channel_ready:
            self._on_channel_ready()

    @Slot(str)
    def onResult(self, text: str) -> None:
        """JS 调用: 收到识别结果。"""
        if text and self._on_result:
            self._on_result(text)

    @Slot()
    def onFinish(self) -> None:
        """JS 调用: 收到 finish 事件。"""
        if self._on_finish:
            self._on_finish()

    @Slot()
    def onOpen(self) -> None:
        """JS 调用: WebSocket 已连接。"""
        if self._on_open:
            self._on_open()

    @Slot(str)
    def onError(self, msg: str) -> None:
        """JS 调用: 连接/发送错误。"""
        if self._on_error:
            self._on_error(msg)

    @Slot(str)
    def onAuthError(self, msg: str) -> None:
        """JS 调用: 认证失败。"""
        if self._on_auth_error:
            self._on_auth_error(msg)


# ══════════════════════════════════════════════════════════════════════
# JS 注入脚本（QWebChannel + ASR WebSocket）
# ══════════════════════════════════════════════════════════════════════

# _qwebchannel.js 在模块加载时读取
def _load_qwebchannel_js() -> str:
    import os
    path = os.path.join(os.path.dirname(__file__), "_qwebchannel.js")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_QWEBCHANNEL_JS = _load_qwebchannel_js()

_ASR_BRIDGE_JS = """
// === 豆包 ASR WebSocket QWebChannel Bridge ===
// 依赖: qwebchannel.js (已注入)

(function() {
    'use strict';
    if (window.__doubaoASRBridgeReady) return;
    window.__doubaoASRBridgeReady = true;

    var bridge = null;
    var ws = null;
    var audioBuffer = [];
    var isConnected = false;
    var sendTimer = null;

    // ── 初始化 QWebChannel ────────────────────────────────
    function initChannel() {
        if (typeof QWebChannel === 'undefined') {
            setTimeout(initChannel, 100);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.bridge;

            // 监听 Python → JS 信号
            bridge.audioData.connect(function(b64) {
                pushAudio(b64);
            });
            bridge.finishSending.connect(function() {
                finishSending();
            });
            bridge.connectASR.connect(function(url, cookieHeader, preloadedB64) {
                connectASR(url, cookieHeader, preloadedB64);
            });
            bridge.closeASR.connect(function() {
                closeASR();
            });

            console.log('[doubaoASRBridge] QWebChannel ready');
            // 通知 Python：JS 端已完成握手，可以发送信号了
            bridge.onChannelReady();
        });
    }

    // ── WebSocket ─────────────────────────────────────────

    function connectASR(wssUrl, cookieHeader, preloadedB64) {
        if (ws) { try { ws.close(); } catch(e) {} }
        // 清空旧缓冲，但先把预加载音频写入（如果有）
        audioBuffer = [];
        isConnected = false;

        // 预加载音频：在建立连接前就存入缓冲，onopen 时立刻冲刷
        if (preloadedB64) {
            try {
                var binaryStr = atob(preloadedB64);
                var bytes = new Uint8Array(binaryStr.length);
                for (var i = 0; i < binaryStr.length; i++) {
                    bytes[i] = binaryStr.charCodeAt(i);
                }
                // 按 6400 字节（200ms）切片存入缓冲
                var chunkSize = 6400;
                for (var offset = 0; offset < bytes.length; offset += chunkSize) {
                    audioBuffer.push(bytes.slice(offset, offset + chunkSize).buffer);
                }
            } catch(e) {
                console.log('[doubaoASRBridge] preload decode error: ' + e.message);
            }
        }

        ws = new WebSocket(wssUrl);
        ws.binaryType = 'arraybuffer';

        ws.onopen = function() {
            isConnected = true;
            console.log('[doubaoASRBridge] onopen, buffer=' + audioBuffer.length + ' readyState=' + ws.readyState);
            flushAudio();           // 立刻冲刷预加载音频，无任何延迟
            console.log('[doubaoASRBridge] flush done, buffer=' + audioBuffer.length);
            if (bridge) bridge.onOpen();
        };

        ws.onmessage = function(event) {
            try {
                var raw = event.data;
                console.log('[doubaoASRBridge] onmessage raw: ' + (typeof raw === 'string' ? raw.substring(0, 200) : '[binary ' + raw.byteLength + ' bytes]'));
                var msg = JSON.parse(raw);
                if (msg.event === 'result') {
                    var text = (msg.result && msg.result.Text) || '';
                    console.log('[doubaoASRBridge] result text: ' + text);
                    if (bridge) bridge.onResult(text);
                } else if (msg.event === 'finish') {
                    console.log('[doubaoASRBridge] finish event, code=' + msg.code);
                    if (bridge) bridge.onFinish();
                } else {
                    console.log('[doubaoASRBridge] unknown event: ' + msg.event + ' code=' + msg.code + ' msg=' + msg.message);
                }
                // 检查认证/限流错误
                if (msg.code && msg.code !== 0) {
                    var errMsg = (msg.message || '').toLowerCase();
                    if (msg.code === 709599054 ||
                        msg.code === 710022013 ||
                        errMsg.indexOf('cookie') >= 0 ||
                        errMsg.indexOf('auth') >= 0 ||
                        errMsg.indexOf('session') >= 0 ||
                        errMsg.indexOf('tourist') >= 0 ||
                        errMsg.indexOf('limited') >= 0) {
                        console.log('[doubaoASRBridge] auth/limit error: ' + msg.message);
                        if (bridge) bridge.onAuthError(msg.message || 'auth error');
                    }
                }
            } catch(e) {
                if (bridge) bridge.onError('parse: ' + e.message);
            }
        };

        ws.onerror = function(err) {
            console.log('[doubaoASRBridge] onerror');
            if (bridge) bridge.onError('WebSocket error');
        };

        ws.onclose = function(event) {
            isConnected = false;
            console.log('[doubaoASRBridge] WS closed: code=' + event.code + ' reason=' + event.reason + ' wasClean=' + event.wasClean);
        };
    }

    function pushAudio(b64) {
        try {
            var binaryStr = atob(b64);
            var bytes = new Uint8Array(binaryStr.length);
            for (var i = 0; i < binaryStr.length; i++) {
                bytes[i] = binaryStr.charCodeAt(i);
            }
            if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(bytes.buffer);
            } else {
                audioBuffer.push(bytes.buffer);
                if (audioBuffer.length > 500) audioBuffer.shift();
            }
        } catch(e) {
            if (bridge) bridge.onError('pushAudio: ' + e.message);
        }
    }

    function finishSending() {
        flushAudio();
        audioBuffer = [];
        if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
        // 发一帧空 PCM 作为 EOF 标志，再关闭 WS，触发服务端 finish 事件
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(new ArrayBuffer(0));
            setTimeout(function() {
                if (ws && ws.readyState === WebSocket.OPEN) ws.close(1000, 'done');
            }, 300);
        }
    }

    function closeASR() {
        audioBuffer = [];
        if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
        if (ws) { try { ws.close(1000, '1000-'); } catch(e) {}; ws = null; }
        isConnected = false;
    }

    function flushAudio() {
        if (!ws || !isConnected || audioBuffer.length === 0) return;
        var chunks = audioBuffer.splice(0, audioBuffer.length);
        for (var i = 0; i < chunks.length; i++) {
            if (ws.readyState === WebSocket.OPEN) ws.send(chunks[i]);
        }
    }

    // 每 100ms 冲刷缓冲
    sendTimer = setInterval(flushAudio, 100);

    // ── 启动 ──────────────────────────────────────────────
    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
        initChannel();
    } else {
        // 等待 qt.webChannelTransport 就绪
        var checkTimer = setInterval(function() {
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                clearInterval(checkTimer);
                initChannel();
            }
        }, 100);
    }
})();
"""

# ══════════════════════════════════════════════════════════════════════
# 完整 JS 注入脚本
# ══════════════════════════════════════════════════════════════════════

def _build_injection_script() -> str:
    """构建完整的 JS 注入脚本（qwebchannel.js + bridge.js）。"""
    return _QWEBCHANNEL_JS + "\n;\n" + _ASR_BRIDGE_JS


# ══════════════════════════════════════════════════════════════════════
# 公共 API
# ══════════════════════════════════════════════════════════════════════


class WebViewASRBridge(QObject):
    """管理 WebView 内的 JS WebSocket，提供与 DoubaoWebSocket 兼容的 API。

    使用 QWebChannel 进行 Python ↔ JS 双向通信：
      - JS→Python: 调用 bridge object 的 Slot
      - Python→JS: emit bridge object 的 Signal

    用法:
        bridge = WebViewASRBridge(webview)
        bridge.on_open = lambda: print("connected")
        bridge.on_result = lambda text: print(f"result: {text}")
        bridge.connect(asr_params)
        bridge.send_audio(pcm_bytes)
        bridge.finish_sending()
        bridge.close()
    """

    def __init__(self, webview: QWebEngineView) -> None:
        super().__init__()
        self._webview = webview
        self._injected = False
        self._lock = threading.Lock()

        # ── 回调 ──────────────────────────────────────────────
        self.on_open: Optional[Callable[[], None]] = None
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_finish: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_auth_error: Optional[Callable[[], None]] = None

        # ── 状态 ──────────────────────────────────────────────
        self._is_connected = False
        self._is_finished = False
        # JS 端 QWebChannel 握手是否完成
        self._channel_ready = False
        # connect() 在握手完成前被调用时，暂存 (url, cookie, preload_b64) 等握手完成再发
        self._pending_connect: Optional[tuple[str, str, str]] = None

        # ── 创建 QWebChannel + Bridge Object ──────────────────
        self._bridge_obj = _ASRBridgeObject(self)
        self._bridge_obj._on_channel_ready = self._handle_channel_ready
        self._bridge_obj._on_result = self._handle_result
        self._bridge_obj._on_finish = self._handle_finish
        self._bridge_obj._on_open = self._handle_open
        self._bridge_obj._on_error = self._handle_error
        self._bridge_obj._on_auth_error = self._handle_auth_error

        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge_obj)
        self._webview.page().setWebChannel(self._channel)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def connect(self, params: ASRParams, preload_audio: bytes = b"") -> None:
        """通过 WebView JS 建立 WebSocket 连接。

        preload_audio: 连接前预加载的 PCM 数据。JS 端在 ws.onopen 时立刻冲刷，
        避免服务端因无音频超时关闭（close 1000）。

        JS 端 QWebChannel 握手可能尚未完成，因此先暂存参数。
        握手完成后 _handle_channel_ready() 会自动发出 connectASR 信号。
        若握手已完成则直接发信号。
        """
        self._ensure_injected()

        with self._lock:
            self._is_connected = False
            self._is_finished = False
            channel_ready = self._channel_ready

        url = build_wss_url(params)
        cookie = params.cookie_header
        preload_b64 = base64.b64encode(preload_audio).decode("ascii") if preload_audio else ""

        print(f"[WebViewASRBridge] 正在通过 WebView 连接...")
        print(f"[WebViewASRBridge] Cookies: {len(params.cookies)} 个")
        if preload_b64:
            print(f"[WebViewASRBridge] 预加载音频: {len(preload_audio)} bytes")

        if channel_ready:
            self._bridge_obj.connectASR.emit(url, cookie, preload_b64)
        else:
            with self._lock:
                self._pending_connect = (url, cookie, preload_b64)
            print("[WebViewASRBridge] 等待 QWebChannel 握手完成...")

    def send_audio(self, data: bytes) -> None:
        """发送 PCM 音频数据（线程安全）。"""
        if not data:
            return
        b64 = base64.b64encode(data).decode("ascii")
        self._bridge_obj.audioData.emit(b64)

    def finish_sending(self) -> None:
        """标记发送完成。"""
        with self._lock:
            self._is_finished = True
        self._bridge_obj.finishSending.emit()

    def close(self) -> None:
        """关闭 WebSocket。"""
        with self._lock:
            self._is_connected = False
            self._is_finished = True
        self._bridge_obj.closeASR.emit()

    # ------------------------------------------------------------------
    # 内部回调
    # ------------------------------------------------------------------

    def _handle_channel_ready(self) -> None:
        """JS 端 QWebChannel 握手完成回调。

        若有待发送的连接参数，在此发出 connectASR 信号。
        """
        print("[WebViewASRBridge] QWebChannel 握手完成，JS 端已就绪")
        with self._lock:
            self._channel_ready = True
            pending = self._pending_connect
            self._pending_connect = None

        if pending:
            url, cookie, preload_b64 = pending
            print("[WebViewASRBridge] 发出待处理的连接请求...")
            self._bridge_obj.connectASR.emit(url, cookie, preload_b64)

    def _handle_result(self, text: str) -> None:
        print(f"[WebViewASRBridge] 识别: {text}")
        if self.on_result:
            self.on_result(text)

    def _handle_finish(self) -> None:
        print("[WebViewASRBridge] finish 事件")
        if self.on_finish:
            self.on_finish()

    def _handle_open(self) -> None:
        print("[WebViewASRBridge] 连接已建立")
        with self._lock:
            self._is_connected = True
        if self.on_open:
            self.on_open()

    def _handle_error(self, msg: str) -> None:
        print(f"[WebViewASRBridge] 错误: {msg}")
        with self._lock:
            self._is_connected = False
        if self.on_error:
            self.on_error(msg)

    def _handle_auth_error(self, msg: str) -> None:
        print(f"[WebViewASRBridge] 认证错误: {msg}")
        with self._lock:
            self._is_connected = False
        if self.on_auth_error:
            self.on_auth_error()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _ensure_injected(self) -> None:
        """注入 QWebChannel + ASR bridge JS。

        必须在 setWebChannel() 之后、页面加载完成之后调用。
        """
        if self._injected:
            return
        script = _build_injection_script()
        self._webview.page().runJavaScript(script)
        self._injected = True
        print("[WebViewASRBridge] QWebChannel + ASR bridge JS 已注入")

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_finished(self) -> bool:
        return self._is_finished
