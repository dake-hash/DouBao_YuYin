"""
auth_webview.py — 豆包凭证提取

P3: 通过内嵌 QWebEngineView 让用户登录豆包，自动提取 Cookie / Token
等认证凭证，保存到 Settings。登录完成后销毁 WebView 释放内存。
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

    Signals:
        login_completed: 凭证提取并保存成功后发射
    """

    login_completed = Signal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._extracted = False
        self._cookies: list[QNetworkCookie] = []

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

        # WebEngine 视图
        self._webview = QWebEngineView()
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
        js = """
        (function() {
            try {
                var url = window.location.href;
                var cookies = document.cookie;
                var hasSession = cookies.length > 50;  // 登录后 cookie 明显变多
                var isLoginPage = url.indexOf('login') > -1;
                var hasChatUI = document.querySelector('.chat-container') !== null
                    || document.querySelector('[class*="chat"]') !== null
                    || document.querySelector('.sidebar') !== null;
                return JSON.stringify({
                    url: url,
                    isLoginPage: isLoginPage,
                    hasSessionCookie: hasSession,
                    hasChatUI: hasChatUI,
                    cookieLen: cookies.length
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

        # 启发式判断：不在登录页 + 有较多 cookie → 已登录
        is_login_page = data.get("isLoginPage", True)
        has_session = data.get("hasSessionCookie", False)
        cookie_len = data.get("cookieLen", 0)

        if not is_login_page and has_session and cookie_len > 50:
            print(f"[AuthWebView] 自动检测到登录状态 (cookie_len={cookie_len})")
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
        self.accept()  # 关闭对话框

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """关闭时停止轮询并释放 WebView。"""
        self._poll_timer.stop()
        if not self._extracted:
            print("[AuthWebView] 用户取消登录")
        # 显式清理 WebView 释放资源
        self._webview.setParent(None)
        self._webview.deleteLater()
        super().closeEvent(event)
