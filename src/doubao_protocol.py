"""
doubao_protocol.py — 豆包 ASR WebSocket 协议编解码

P5: 基于 doubao-murmur (Swift) 逆向工程，实现豆包 WSS 流式语音识别的
URL 构建、参数提取和 JSON 响应解析。

协议要点（来自 doubao-murmur 逆向分析）:
  - WebSocket 端点: wss://ws-samantha.doubao.com/samantha/audio/asr
  - 认证: Cookie header（从 P3 WebView 登录中提取）+ Origin header
  - 上行: 裸 PCM Int16 LE 音频，直接作为 WebSocket binary frame 发送
    （无二进制协议头 / 帧封装 — 与原始规格文档的假设不同！）
  - 下行: JSON 文本消息，event 类型为 "result" 和 "finish"
  - 无需 start_session / finish_session 等握手消息，连接即开始
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode


# ══════════════════════════════════════════════════════════════════════
# 常量（来自 doubao-murmur 源码 + 前端 JS 逆向）
# ══════════════════════════════════════════════════════════════════════

WSS_BASE_URL = "wss://ws-samantha.doubao.com/samantha/audio/asr"

FIXED_QUERY_PARAMS: dict[str, str] = {
    "version_code": "20800",
    "language": "zh",
    "device_platform": "web",
    "aid": "497858",
    "real_aid": "497858",
    "pkg_type": "release_version",
    "pc_version": "3.12.3",
    "region": "",
    "sys_region": "",
    "samantha_web": "1",
    "use-olympus-account": "1",
    "format": "pcm",
}

# localStorage keys that hold device_id and web_id
LOCAL_STORAGE_KEY_DEVICE_ID = "samantha_web_web_id"
LOCAL_STORAGE_KEY_WEB_ID = "__tea_cache_tokens_497858"

# Auth error codes from server
AUTH_ERROR_CODES = {
    709599054,  # Invalid — often cookie/session related
}

AUTH_ERROR_KEYWORDS = (
    "cookie", "auth", "login", "session", "unauthorized", "expired",
)


# ══════════════════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════════════════


@dataclass
class ASRParams:
    """豆包 ASR WebSocket 连接所需的完整参数。

    从 P3 提取的 auth_token 中解析而来。
    """

    cookies: dict[str, str] = field(default_factory=dict)
    device_id: str = ""
    web_id: str = ""

    @property
    def cookie_header(self) -> str:
        """构建 Cookie HTTP 头的值。"""
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    @property
    def is_valid(self) -> bool:
        """是否具备连接所需的所有参数。"""
        return bool(self.cookies and self.device_id and self.web_id)

    @classmethod
    def from_auth_token(cls, auth_token: dict | None) -> Optional["ASRParams"]:
        """从 settings.auth_token 中提取 ASR 连接参数。

        Args:
            auth_token: P3 保存的 auth_token 字典，包含:
                - cookie_list: [{name, value, domain, path}, ...]
                - local_storage: {key: value, ...}

        Returns:
            ASRParams 实例，若缺少必要参数则返回 None。
        """
        if not auth_token:
            return None

        # ── 1. 提取 Cookie ──────────────────────────────────────
        cookies: dict[str, str] = {}

        # 1a. 从 document.cookie 字符串解析（JS 端提取，含非 httpOnly cookie）
        raw_cookies = auth_token.get("cookies", "")
        if raw_cookies:
            for part in raw_cookies.split(";"):
                part = part.strip()
                if "=" in part:
                    name, _, value = part.partition("=")
                    name = name.strip()
                    if name:
                        cookies[name] = value

        # 1b. 从 CookieStore 列表补充（含 httpOnly cookie，优先级更高）
        cookie_list = auth_token.get("cookie_list", [])
        for c in cookie_list:
            domain = c.get("domain", "")
            # 只保留 doubao.com 域的 cookie（doubao-murmur 的做法）
            if "doubao.com" in domain:
                cookies[c["name"]] = c["value"]  # 覆盖 1a 的同名 cookie

        if not cookies:
            print("[DoubaoProtocol] WARN: 未找到 doubao.com 域的 cookie")
            return None

        # ── 2. 提取 device_id ───────────────────────────────────
        local_storage = auth_token.get("local_storage", {})
        device_id = _extract_from_local_storage(
            local_storage, LOCAL_STORAGE_KEY_DEVICE_ID, "web_id"
        )

        # ── 3. 提取 web_id / tea_uuid ───────────────────────────
        web_id = _extract_from_local_storage(
            local_storage, LOCAL_STORAGE_KEY_WEB_ID, "web_id"
        )

        if not device_id or not web_id:
            print(
                f"[DoubaoProtocol] WARN: 缺少必要参数: "
                f"device_id={'OK' if device_id else 'MISSING'}, "
                f"web_id={'OK' if web_id else 'MISSING'}"
            )
            return None

        print(
            f"[DoubaoProtocol] OK: ASR 参数提取成功 "
            f"(cookies={len(cookies)}, device_id={device_id[:8]}..., web_id={web_id[:8]}...)"
        )
        return cls(cookies=cookies, device_id=device_id, web_id=web_id)


# ══════════════════════════════════════════════════════════════════════
# URL 构建
# ══════════════════════════════════════════════════════════════════════


def build_wss_url(params: ASRParams) -> str:
    """构建完整的豆包 ASR WebSocket URL。

    包含所有固定参数 + 动态参数（device_id, web_id, web_tab_id）。

    Args:
        params: 从 auth_token 中提取的 ASR 连接参数。

    Returns:
        完整的 WebSocket URL，如 wss://ws-samantha.doubao.com/...?version_code=...&...
    """
    query: dict[str, str] = dict(FIXED_QUERY_PARAMS)
    query["device_id"] = params.device_id
    query["web_id"] = params.web_id
    query["tea_uuid"] = params.web_id  # tea_uuid 与 web_id 相同
    query["web_tab_id"] = uuid.uuid4().hex  # 每次连接随机生成

    return f"{WSS_BASE_URL}?{urlencode(query)}"


# ══════════════════════════════════════════════════════════════════════
# 消息解析
# ══════════════════════════════════════════════════════════════════════


@dataclass
class ServerMessage:
    """解析后的服务端消息。

    Attributes:
        event: 事件类型 — "result" | "finish" | "error" | "unknown"
        text: 识别的文本（仅 result 事件有效）
        code: 服务端错误码（0 = 成功）
        is_auth_error: 是否为认证错误
        raw: 原始 JSON 字符串
    """

    event: str
    text: str = ""
    code: int = 0
    message: str = ""
    is_auth_error: bool = False
    raw: str = ""


def parse_message(raw_text: str) -> Optional[ServerMessage]:
    """解析服务端发来的 JSON 消息。

    Args:
        raw_text: WebSocket 文本帧的原始内容。

    Returns:
        ServerMessage 实例，或 None（无法解析时）。
    """
    try:
        data: dict[str, Any] = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None

    code = data.get("code", 0)
    event = data.get("event", "")
    message = data.get("message", "")

    # ── 检查认证错误 ──────────────────────────────────────────
    is_auth_error = False
    if code != 0:
        lower_msg = message.lower()
        if code in AUTH_ERROR_CODES or any(
            kw in lower_msg for kw in AUTH_ERROR_KEYWORDS
        ):
            is_auth_error = True

    # ── 提取识别文本 ──────────────────────────────────────────
    text = ""
    if event == "result":
        result_obj = data.get("result")
        if isinstance(result_obj, dict):
            text = result_obj.get("Text", "") or ""

    return ServerMessage(
        event=event or "unknown",
        text=text,
        code=code,
        message=message,
        is_auth_error=is_auth_error,
        raw=raw_text,
    )


# ══════════════════════════════════════════════════════════════════════
# 内部辅助
# ══════════════════════════════════════════════════════════════════════


def _extract_from_local_storage(
    local_storage: dict[str, str],
    key: str,
    field: str,
) -> str:
    """从 localStorage dump 中解析 JSON 并提取指定字段。

    Args:
        local_storage: localStorage 的完整 dump {key: json_string, ...}
        key: localStorage 的键名
        field: JSON 对象中要提取的字段名

    Returns:
        提取的字符串值，失败返回空字符串。
    """
    raw = local_storage.get(key)
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""
    if isinstance(data, dict):
        return str(data.get(field, ""))
    return ""
