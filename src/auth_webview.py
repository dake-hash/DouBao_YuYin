"""
auth_webview.py — 豆包凭证提取 + WebView 持久化

P3: 通过内嵌 QWebEngineView 让用户登录豆包，自动提取 Cookie / Token
等认证凭证，保存到 Settings。

P5 联动: 登录后 WebView 不再销毁，改为隐藏到后台窗口。通过
WebViewASRBridge 从 JS 发起 WebSocket 连接，绕过 CDN 的 TLS 指纹检测。
"""

import json
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


DOUBAO_URL = "https://www.doubao.com/chat/"
POLL_INTERVAL_MS = 2000          # 每 2 秒检查一次登录状态
COOKIE_STORE_WAIT_MS = 800       # Cookie 收集等待时间
EXPIRY_DAYS = 7


# ------------------------------------------------------------------
# 凭证提取窗口
# ------------------------------------------------------------------


class AuthWebView(QDialog):
    """豆包登录对话框。

    内嵌 QWebEngineView 打开豆包网页版，用户登录后自动（或手动）
    提取 Cookie、localStorage、sessionStorage 中的凭证，
    保存到 settings.auth_token 并设置 7 天过期时间。

    登录完成后:
      - 如果 keep_alive=True: WebView 被移到隐藏后台窗口，供 P5 桥接使用
      - 如果 keep_alive=False: WebView 销毁释放内存

    Signals:
        login_completed: 凭证提取并保存成功后发射
    """

    login_completed = Signal()

    def __init__(self, settings, parent=None, keep_alive: bool = True) -> None:
        super().__init__(parent)
        self._settings = settings
        self._extracted = False
        self._cookies: list[QNetworkCookie] = []
        self._keep_alive = keep_alive
        self._background_window: Optional[QDialog] = None
        self._bridge = None  # WebViewASRBridge 实例

        self.setWindowTitle("登录豆包")
        self.resize(900, 650)
        self.setMinimumSize(600, 400)

        # ── UI 布局 ──────────────────────────────────────────────
        layout = QVBoxLayout(self)

        # 提示
        self._hint = QLabel(
            "请在下方窗口中登录豆包账号\n"
            "登录成功后凭证将自动提取，窗口自动关闭"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("padding: 6px; font-size: 13px;")
        layout.addWidget(self._hint)

        # WebEngine 视图 — 使用具名持久化 profile，跨进程/跨会话共享 Cookie
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        self._profile = QWebEngineProfile("doubao-pet", self)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        self._webview = QWebEngineView()
        _page = QWebEnginePage(self._profile, self._webview)
        self._webview.setPage(_page)
        self._webview.setUrl(QUrl(DOUBAO_URL))
        self._webview.urlChanged.connect(self._on_url_changed)
        layout.addWidget(self._webview, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self._extract_btn = QPushButton("已完成登录，手动提取")
        self._extract_btn.clicked.connect(self._extract_credentials)
        btn_layout.addWidget(self._extract_btn)
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # ── 自动轮询登录状态 ────────────────────────────────────
        self._poll_count = 0
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_login_state)
        self._poll_timer.start()

        print("[AuthWebView] 登录窗口已打开")

    # ------------------------------------------------------------------
    # 登录检测
    # ------------------------------------------------------------------

    def _on_url_changed(self, url: QUrl) -> None:
        """URL 变化回调，用于辅助判断登录状态。"""
        url_str = url.toString()
        print(f"[AuthWebView] URL → {url_str[:100]}")

    def _poll_login_state(self) -> None:
        """定时执行 JS 检查是否已登录。"""
        self._poll_count += 1

        js = """
        (function() {
            try {
                // 1. 逐 Cookie 名称检查（仅匹配名称，不匹配值，避免子串误判）
                var pairs = document.cookie.split(';');
                var authNamePatterns = [
                    'sessionid=', 'passport_', 'passport_token',
                    'login_token', 'account_token', 'auth_token',
                    'sid='  // 通用的 session id cookie（非 slardar 跟踪类）
                ];
                var hasAuthCookie = false;
                for (var i = 0; i < pairs.length; i++) {
                    var name = pairs[i].trim().split('=')[0];
                    if (!name) continue;
                    var kv = name + '=';
                    for (var j = 0; j < authNamePatterns.length; j++) {
                        if (kv === authNamePatterns[j] ||
                            name.indexOf(authNamePatterns[j].replace('=','')) === 0) {
                            hasAuthCookie = true;
                            break;
                        }
                    }
                    if (hasAuthCookie) break;
                }

                // 2. 检查 localStorage 中是否有认证 token
                var hasLocalToken = false;
                var tokenKeys = ['token', 'access_token', 'auth_token',
                    'login_info', 'account_info', 'user_info',
                    '__tea_cache_tokens_'];  // 豆包用户 token 缓存 key
                for (var i = 0; i < tokenKeys.length; i++) {
                    var val = localStorage.getItem(tokenKeys[i]);
                    if (val && val.length > 20) {  // 排除空值或过短的值
                        hasLocalToken = true;
                        break;
                    }
                }

                // 3. 检查页面上是否存在登录入口（存在 = 未登录）
                //    豆包未登录时会显示手机号/扫码登录界面
                var hasLoginUI = false;
                var allNodes = document.body ? document.body.querySelectorAll('*') : [];
                for (var i = 0; i < Math.min(allNodes.length, 2000); i++) {
                    var node = allNodes[i];
                    // 只检查叶子节点（没有子元素的元素）
                    if (node.children.length === 0) {
                        var text = (node.textContent || '').trim();
                        if (text === '手机号登录' || text === '扫码登录' ||
                            text === '登录' || text === '登录/注册') {
                            hasLoginUI = true;
                            break;
                        }
                    }
                }

                return JSON.stringify({
                    hasAuthCookie: hasAuthCookie,
                    hasLocalToken: hasLocalToken,
                    hasLoginUI: hasLoginUI,
                    cookieLen: document.cookie.length,
                    cookieCount: pairs.filter(function(p){return p.trim()}).length
                });
            } catch(e) {
                return JSON.stringify({error: e.message});
            }
        })()
        """
        self._webview.page().runJavaScript(js, self._on_poll_result)

    def _on_poll_result(self, result: str) -> None:
        """处理 JS 轮询结果，判断是否已完成登录。"""
        if self._extracted or not result:
            return

        try:
            data = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return

        if "error" in data:
            return

        # 跳过前 3 次轮询（6 秒），等待页面完全加载
        if self._poll_count <= 3:
            return

        has_auth_cookie = data.get("hasAuthCookie", False)
        has_local_token = data.get("hasLocalToken", False)
        has_login_ui = data.get("hasLoginUI", False)
        cookie_count = data.get("cookieCount", 0)

        print(f"[AuthWebView] 轮询 #{self._poll_count}: "
              f"auth_cookie={has_auth_cookie} local_token={has_local_token} "
              f"login_ui={has_login_ui} cookie_count={cookie_count}")

        # 判定：有认证凭据 + 登录界面消失 → 已登录
        # 注意：不再使用 hasChatUI，因为 /chat/ 页面预登录就有聊天骨架
        has_credential = has_auth_cookie or has_local_token
        login_gone = not has_login_ui

        if has_credential and login_gone:
            print(f"[AuthWebView] 自动检测到登录状态!")
            self._extract_credentials()

    # ------------------------------------------------------------------
    # 凭证提取
    # ------------------------------------------------------------------

    def _extract_credentials(self) -> None:
        """从 WebView 中提取所有认证凭证并保存。"""
        if self._extracted:
            return
        self._extracted = True

        self._hint.setText("正在提取凭证，请稍候...")
        self._extract_btn.setEnabled(False)
        self._poll_timer.stop()

        # 第1步：JS 提取 document.cookie + localStorage + sessionStorage
        js = """
        (function() {
            try {
                var ls = {};
                for (var i = 0; i < localStorage.length; i++) {
                    var k = localStorage.key(i);
                    ls[k] = localStorage.getItem(k);
                }
                var ss = {};
                for (var i = 0; i < sessionStorage.length; i++) {
                    var k = sessionStorage.key(i);
                    ss[k] = sessionStorage.getItem(k);
                }
                return JSON.stringify({
                    cookies: document.cookie,
                    localStorage: ls,
                    sessionStorage: ss,
                    url: window.location.href
                });
            } catch(e) {
                return JSON.stringify({error: e.message});
            }
        })()
        """
        self._webview.page().runJavaScript(js, self._on_js_extracted)

        # 第2步：通过 CookieStore 收集完整 Cookie（含 HttpOnly）
        profile: QWebEngineProfile = self._webview.page().profile()
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)
        cookie_store.loadAllCookies()

        # 设置超时：等待 COOKIE_STORE_WAIT_MS 后保存并关闭
        QTimer.singleShot(COOKIE_STORE_WAIT_MS, self._finalize_and_close)

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        """接收 CookieStore 返回的每个 Cookie。"""
        self._cookies.append(cookie)

    def _on_js_extracted(self, result: str) -> None:
        """接收 JS 端提取的凭证。"""
        if not result:
            print("[AuthWebView] JS 提取返回空结果")
            return

        try:
            data = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            print("[AuthWebView] JS 提取结果解析失败")
            return

        self._js_data = data
        print(f"[AuthWebView] JS 提取完成: cookie_len={len(data.get('cookies', ''))}, "
              f"localStorage_keys={len(data.get('localStorage', {}))}, "
              f"sessionStorage_keys={len(data.get('sessionStorage', {}))}")

    def _finalize_and_close(self) -> None:
        """整合所有凭证数据，保存到 settings，关闭窗口。"""
        js_data = getattr(self, "_js_data", {}) or {}

        # 序列化 CookieStore 的 Cookie
        cookie_list = []
        for c in self._cookies:
            cookie_list.append({
                "name": c.name().data().decode("utf-8", errors="replace"),
                "value": c.value().data().decode("utf-8", errors="replace"),
                "domain": c.domain(),
                "path": c.path(),
            })
        print(f"[AuthWebView] CookieStore 收集到 {len(cookie_list)} 个 Cookie")

        # 构建完整的 auth_token
        now = datetime.now(timezone.utc)
        auth_token = {
            "cookies": js_data.get("cookies", ""),
            "cookie_list": cookie_list,
            "local_storage": js_data.get("localStorage", {}),
            "session_storage": js_data.get("sessionStorage", {}),
            "source_url": js_data.get("url", DOUBAO_URL),
            "extracted_at": now.isoformat(),
        }

        self._settings.auth_token = auth_token
        self._settings.auth_expiry = (now + timedelta(days=EXPIRY_DAYS)).isoformat()

        print(f"[AuthWebView] 凭证已保存 (cookies={len(cookie_list)}, "
              f"expiry={self._settings.auth_expiry})")

        self.login_completed.emit()

        if self._keep_alive:
            self._move_to_background()
        else:
            self._destroy_webview()
        self.accept()  # 关闭对话框

    def _move_to_background(self) -> None:
        """将 WebView 移到隐藏后台窗口，供 P5 WebViewASRBridge 使用。"""
        self._poll_timer.stop()

        from PySide6.QtWidgets import QVBoxLayout
        from PySide6.QtCore import Qt as QtCore_Qt

        self._background_window = QDialog(None)
        self._background_window.setWindowTitle("Doubao Background")
        self._background_window.resize(800, 600)
        self._background_window.setVisible(False)
        self._background_window.setAttribute(QtCore_Qt.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self._background_window)
        layout.setContentsMargins(0, 0, 0, 0)
        self._webview.setParent(self._background_window)
        layout.addWidget(self._webview)
        self._background_window.hide()

        # 不刷新页面：登录完成后 WebView 已有完整的跨域 session，
        # 强制 setUrl 会重新加载，丢失内存中的 passport.bytedance.com Cookie。
        print("[AuthWebView] WebView 已移至后台隐藏窗口 (keep_alive=True，保留当前 session)")

    def _destroy_webview(self) -> None:
        """销毁 WebView 释放内存 (keep_alive=False)。"""
        print("[AuthWebView] 销毁 WebView (keep_alive=False)")

    def get_bridge(self):
        """获取 WebViewASRBridge 实例（需要 keep_alive=True）。

        延迟导入避免循环依赖。
        """
        if self._bridge is None and self._webview:
            from webview_asr_bridge import WebViewASRBridge
            self._bridge = WebViewASRBridge(self._webview)
        return self._bridge

    def destroy_background(self) -> None:
        """主动销毁后台 WebView（应用退出时调用）。"""
        if self._background_window:
            self._webview.setParent(None)
            self._webview.deleteLater()
            self._background_window.close()
            self._background_window = None
            self._webview = None
            self._bridge = None
            print("[AuthWebView] 后台 WebView 已销毁")

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """关闭时停止轮询。如果 keep_alive 且已提取凭证，WebView 被保留。"""
        self._poll_timer.stop()
        if not self._extracted:
            print("[AuthWebView] 用户取消登录")
            self._webview.setParent(None)
            self._webview.deleteLater()
        elif not self._keep_alive:
            self._webview.setParent(None)
            self._webview.deleteLater()
        # keep_alive + extracted: WebView 已在 _move_to_background 中重新 parent
        super().closeEvent(event)
