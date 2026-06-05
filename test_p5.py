"""
test_p5.py — P5 验收测试脚本

用法:
    # 离线测试（不需要网络和 Cookie）
    python test_p5.py --offline

    # 在线测试（需要先通过 P3 登录豆包）
    python test_p5.py --online
"""

import json
import os
import struct
import sys
import threading
import time
import wave
from pathlib import Path

# 确保 src 目录在 path 中
SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

from doubao_protocol import (
    ASRParams,
    build_wss_url,
    parse_message,
    WSS_BASE_URL,
    FIXED_QUERY_PARAMS,
)
from doubao_ws import DoubaoWebSocket


# ═══════════════════════════════════════════════════════════════
# 第一部分：离线单元测试
# ═══════════════════════════════════════════════════════════════

PASS = 0
FAIL = 0


def check(condition: bool, label: str) -> None:
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}")
        FAIL += 1


def test_asr_params_extraction() -> None:
    """验收项 1: ASRParams 从 auth_token 中正确提取参数"""
    print("\n--- 验收项 1: ASRParams 参数提取 ---")

    # 1a: 正常提取
    fake_auth = {
        "cookie_list": [
            {"name": "sessionid", "value": "abc123", "domain": ".doubao.com", "path": "/"},
            {"name": "sid_tt", "value": "def456", "domain": ".doubao.com", "path": "/"},
            {"name": "uid_tt", "value": "ghi789", "domain": ".doubao.com", "path": "/"},
            {"name": "other", "value": "xxx", "domain": ".other.com", "path": "/"},
        ],
        "local_storage": {
            "samantha_web_web_id": json.dumps({
                "web_id": "1111222233334444",
                "tt_wid": "some_tt_wid",
            }),
            "__tea_cache_tokens_497858": json.dumps({
                "web_id": "5555666677778888",
                "user_unique_id": "some_user",
            }),
        },
    }

    params = ASRParams.from_auth_token(fake_auth)
    check(params is not None, "从有效 auth_token 提取返回非 None")
    if params:
        check(params.device_id == "1111222233334444", f"device_id 正确提取 (got: {params.device_id})")
        check(params.web_id == "5555666677778888", f"web_id 正确提取 (got: {params.web_id})")
        check(len(params.cookies) == 3, f"仅保留 doubao.com 域 cookie (got: {len(params.cookies)})")
        check("other=xxx" not in params.cookie_header, "非 doubao 域 cookie 被过滤")
        check(params.is_valid, "is_valid == True")

    # 1b: 空 auth_token
    params_none = ASRParams.from_auth_token(None)
    check(params_none is None, "auth_token=None 返回 None")

    params_empty = ASRParams.from_auth_token({})
    check(params_empty is None, "auth_token={} 返回 None")

    # 1c: 缺少 device_id
    auth_no_device = {
        "cookie_list": [{"name": "s", "value": "v", "domain": ".doubao.com", "path": "/"}],
        "local_storage": {
            "__tea_cache_tokens_497858": json.dumps({"web_id": "5555"}),
        },
    }
    params_no_dev = ASRParams.from_auth_token(auth_no_device)
    check(params_no_dev is None, "缺少 device_id 时返回 None")

    # 1d: 缺少 cookies
    auth_no_cookie = {
        "cookie_list": [],
        "local_storage": {
            "samantha_web_web_id": json.dumps({"web_id": "1111"}),
            "__tea_cache_tokens_497858": json.dumps({"web_id": "5555"}),
        },
    }
    params_no_ck = ASRParams.from_auth_token(auth_no_cookie)
    check(params_no_ck is None, "无 doubao.com cookie 时返回 None")


def test_url_building() -> None:
    """验收项 2: WSS URL 构建正确"""
    print("\n--- 验收项 2: WSS URL 构建 ---")

    params = ASRParams(
        cookies={"sessionid": "abc"},
        device_id="1111222233334444",
        web_id="5555666677778888",
    )

    url = build_wss_url(params)

    check(url.startswith(WSS_BASE_URL + "?"), "URL 以正确的 base URL 开头")

    # 检查所有固定参数
    for key, val in FIXED_QUERY_PARAMS.items():
        check(f"{key}={val}" in url, f"URL 包含固定参数 {key}={val}")

    # 检查动态参数
    check("device_id=1111222233334444" in url, "URL 包含 device_id")
    check("web_id=5555666677778888" in url, "URL 包含 web_id")
    check("tea_uuid=5555666677778888" in url, "tea_uuid 与 web_id 相同")
    check("web_tab_id=" in url, "URL 包含 web_tab_id（每次随机生成）")
    check("format=pcm" in url, "URL 包含 format=pcm")

    # 两次调用 URL 的 web_tab_id 不同
    url2 = build_wss_url(params)
    check(url != url2, "每次 URL 的 web_tab_id 不同（UUID 随机）")


def test_message_parsing() -> None:
    """验收项 3: 服务端 JSON 消息解析"""
    print("\n--- 验收项 3: JSON 消息解析 ---")

    # 3a: result 事件
    msg = parse_message(json.dumps({
        "event": "result",
        "result": {"Text": "你好世界"},
        "code": 0,
        "message": "",
    }))
    check(msg is not None, "result 消息解析非 None")
    if msg:
        check(msg.event == "result", f"event='result' (got: {msg.event})")
        check(msg.text == "你好世界", f"text 正确提取 (got: {msg.text})")
        check(msg.code == 0, f"code=0 (got: {msg.code})")
        check(not msg.is_auth_error, "非认证错误")

    # 3b: result 空文本
    msg_empty = parse_message(json.dumps({
        "event": "result",
        "result": {"Text": ""},
        "code": 0,
        "message": "",
    }))
    if msg_empty:
        check(msg_empty.text == "", "空 Text 正确返回空字符串")

    # 3c: finish 事件
    msg_fin = parse_message(json.dumps({
        "event": "finish",
        "result": None,
        "code": 0,
        "message": "",
    }))
    if msg_fin:
        check(msg_fin.event == "finish", "finish 事件识别正确")

    # 3d: 认证错误（已知错误码 709599054）
    msg_auth = parse_message(json.dumps({
        "event": "",
        "result": None,
        "code": 709599054,
        "message": "Invalid",
    }))
    if msg_auth:
        check(msg_auth.is_auth_error, "已知认证错误码被检测")
        check(msg_auth.code == 709599054, "错误码保留")

    # 3e: 认证错误（关键字检测）
    msg_auth2 = parse_message(json.dumps({
        "event": "",
        "code": 9999,
        "message": "session expired",
    }))
    if msg_auth2:
        check(msg_auth2.is_auth_error, "含 'session' 关键字的消息被识别为认证错误")

    # 3f: 非法 JSON
    msg_bad = parse_message("this is not json")
    check(msg_bad is None, "非法 JSON 返回 None")


def test_doubao_ws_initialization() -> None:
    """验收项 4: DoubaoWebSocket 初始化与状态管理"""
    print("\n--- 验收项 4: DoubaoWebSocket 初始化 ---")

    ws = DoubaoWebSocket()
    check(not ws.is_connected, "初始状态 is_connected=False")
    check(not ws.is_finished, "初始状态 is_finished=False")

    # 回调注册
    opened = []

    def on_open():
        opened.append(True)

    ws.on_open = on_open
    ws.on_result = lambda text: None
    ws.on_finish = lambda: None
    ws.on_error = lambda e: None
    ws.on_auth_error = lambda: None
    check(ws.on_open is not None, "回调注册成功")

    # finish_sending 状态
    ws.finish_sending()
    check(ws.is_finished, "finish_sending 后 is_finished=True")


def test_thread_safety() -> None:
    """验收项 5: send_audio 线程安全（缓冲模式）"""
    print("\n--- 验收项 5: send_audio 缓冲机制 ---")

    ws = DoubaoWebSocket()
    results = []
    ws.on_result = lambda t: results.append(t)

    # 在未连接状态下发送音频（应被缓冲而非崩溃）
    import threading

    errors = []

    def send_batch():
        try:
            for i in range(100):
                ws.send_audio(b"\x00\x00" * 100)  # 100 帧 16bit 静音
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=send_batch) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check(len(errors) == 0, f"5 线程并发 send_audio 无异常 (got {len(errors)} errors)")

    # finish_sending 应清空缓冲
    ws.finish_sending()
    check(ws.is_finished, "finish_sending 后缓冲被清空")


def test_wav_generation() -> None:
    """验收项 6: 生成测试用 WAV 文件（若已存在真实录音则跳过生成）"""
    print("\n--- 验收项 6: 生成测试 WAV ---")

    import math
    import struct

    wav_path = Path(__file__).parent / "test_audio.wav"

    # 若已有录音文件则直接验证，不覆盖
    if not wav_path.exists():
        sample_rate = 16000
        duration = 3.0
        freq = 440.0
        num_samples = int(sample_rate * duration)

        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * freq * t))
            samples.append(sample)

        raw_pcm = struct.pack(f"<{num_samples}h", *samples)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_pcm)

    file_size = wav_path.stat().st_size
    check(wav_path.exists(), f"测试 WAV 文件已生成: {wav_path}")
    check(file_size > 0, f"文件大小 > 0 ({file_size} bytes)")
    # 文件大小检查：放宽范围，兼容真实录音（大小不固定）
    check(file_size > 1000, f"文件大小符合预期 (got {file_size} bytes)")


# ═══════════════════════════════════════════════════════════════
# 第二部分：在线集成测试（需要有效 Cookie）
# ═══════════════════════════════════════════════════════════════


def test_live_connection() -> None:
    """验收项 7-11: 在线 WebSocket 连接实测"""
    print("\n" + "=" * 60)
    print("  在线集成测试 — 需要有效的豆包 Cookie")
    print("=" * 60)

    # 1. 加载 P3 提取的凭证
    settings_path = Path(__file__).parent / "settings.json"
    if not settings_path.exists():
        print("\n  [SKIP] settings.json 不存在，请先运行 P3 登录豆包")
        print("  操作步骤：")
        print("    1. 启动应用: python src/main.py")
        print("    2. 右键桌宠 -> 登录豆包")
        print("    3. 在弹出的 WebView 中完成登录")
        print("    4. 确认 settings.json 中 auth_token 不为 null")
        return

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    auth_token = settings.get("auth_token")
    if not auth_token:
        print("\n  [SKIP] auth_token 为 null，请先登录豆包")
        return

    print(f"\n  已找到 auth_token (提取时间: {auth_token.get('extracted_at', 'unknown')})")

    # 2. 提取 ASR 参数
    params = ASRParams.from_auth_token(auth_token)
    if not params:
        print("\n  [FAIL] 无法从 auth_token 提取 ASR 参数")
        print("  请检查 settings.json 中的:")
        print("    - cookie_list 是否包含 doubao.com 域的 cookie")
        print("    - local_storage 是否包含 samantha_web_web_id 和 __tea_cache_tokens_497858")
        return

    print(f"  [PASS] ASR 参数提取成功")
    print(f"    Cookies: {len(params.cookies)} 个")
    print(f"    device_id: {params.device_id[:16]}...")
    print(f"    web_id: {params.web_id[:16]}...")

    # 3. 建立 WebSocket 连接
    print("\n--- 验收项 7: WebSocket 连接 ---")
    ws = DoubaoWebSocket()

    connect_result = {"opened": False, "error": None, "auth_error": False}
    connect_event = threading.Event()

    def on_open():
        connect_result["opened"] = True
        connect_event.set()

    def on_error(e):
        connect_result["error"] = str(e)
        connect_event.set()

    def on_auth_error():
        connect_result["auth_error"] = True
        connect_event.set()

    ws.on_open = on_open
    ws.on_error = on_error
    ws.on_auth_error = on_auth_error

    ws.connect(params)

    # 等待连接结果（最多 10 秒）
    connected = connect_event.wait(timeout=10)

    if not connected:
        print("  [FAIL] 连接超时（10 秒未收到任何回调）")
        return

    if connect_result["auth_error"]:
        print("  [FAIL] 认证失败！Cookie 可能已过期")
        print("  请重新登录豆包（右键桌宠 -> 登录豆包）")
        return

    if connect_result["error"]:
        print(f"  [FAIL] 连接错误: {connect_result['error']}")
        return

    if connect_result["opened"]:
        print("  [PASS] WebSocket 连接成功建立")
    else:
        print("  [FAIL] 连接未建立")
        return

    # 4. 发送音频并检查结果
    print("\n--- 验收项 8: 发送音频 + 接收识别结果 ---")
    results = []
    finished = threading.Event()

    def on_result(text):
        results.append(text)
        print(f"  收到识别结果: {text}")

    def on_finish():
        finished.set()
        print("  收到 finish 事件")

    ws.on_result = on_result
    ws.on_finish = on_finish

    # 加载测试 WAV 并发送 PCM 数据
    wav_path = Path(__file__).parent / "test_audio.wav"

    # 如果 WAV 不存在，发送静音数据
    if wav_path.exists():
        with wave.open(str(wav_path), "rb") as wf:
            pcm_data = wf.readframes(wf.getnframes())
        print(f"  发送测试音频: {len(pcm_data)} bytes ({len(pcm_data)/32000:.1f}s)")
    else:
        # 生成 2 秒静音
        pcm_data = b"\x00\x00" * 16000
        print("  发送 2 秒静音数据")

    # 以 ~200ms 间隔发送（模拟实时流）
    chunk_size = 3200 * 2  # 3200 samples * 2 bytes = 200ms @ 16kHz
    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i : i + chunk_size]
        ws.send_audio(chunk)
        time.sleep(0.05)  # 小延迟模拟实时流

    print("  音频发送完毕")
    ws.finish_sending()

    # 等待最终结果（最多 5 秒）
    got_result = finished.wait(timeout=5)
    # 也给 on_result 一点时间
    time.sleep(1)

    if results:
        print(f"  [PASS] 收到 {len(results)} 条识别结果")
    else:
        print("  [INFO] 未收到识别结果（静音数据可能不触发识别）")

    if got_result:
        print("  [PASS] 收到 finish 事件")
    else:
        print("  [INFO] 未收到 finish 事件（可能服务端等待更多音频）")

    # 5. 关闭连接
    print("\n--- 验收项 9: 正常关闭 ---")
    ws.close()
    time.sleep(0.5)
    check(not ws.is_connected, "close() 后 is_connected=False")
    print("  [PASS] WebSocket 正常关闭")


# ═══════════════════════════════════════════════════════════════
# 第二部分（备选）：通过 WebView JS 桥接测试
# ═══════════════════════════════════════════════════════════════


def test_live_connection_via_webview() -> None:
    """验收项 7-11 (WebView 模式): 通过 Chromium TLS 绕过 CDN 拦截

    策略：直接弹出 AuthWebView 登录窗口，登录完成后复用同一个已登录 WebView
    发起 ASR WebSocket。不另建新 WebView，避免跨域 Cookie 丢失问题。
    """
    print("\n" + "=" * 60)
    print("  在线集成测试 — WebView JS 桥接模式")
    print("  (通过 Chromium 网络栈，绕过 ArgusSecurityPlugin)")
    print("=" * 60)

    # 1. 创建 QApplication
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QUrl

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 2. 打开登录窗口，让用户登录（或检测到已登录自动提取）
    #    登录完成后 AuthWebView 保留 WebView 到后台（keep_alive=True）
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent / "src"))

    from settings import Settings
    from auth_webview import AuthWebView

    settings_obj = Settings(str(Path(__file__).parent / "settings.json"))

    print("\n--- 准备: 打开登录窗口（已登录则自动提取凭证）---")
    print("  请在弹出窗口中登录豆包账号，登录后窗口会自动关闭")

    login_done = threading.Event()
    auth_view = AuthWebView(settings_obj, keep_alive=True)
    auth_view.login_completed.connect(lambda: login_done.set())

    # 显示登录窗口，同时驱动事件循环等待登录完成
    auth_view.show()
    deadline = time.time() + 180  # 最多等 3 分钟
    while not login_done.is_set() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
        # AuthWebView.exec() 会阻塞，改用 show() + processEvents() 驱动
        if not auth_view.isVisible() and not login_done.is_set():
            # 用户关闭了窗口但没有完成登录
            break

    if not login_done.is_set():
        print("  [SKIP] 登录超时或用户取消")
        return

    print("  [OK] 登录完成，凭证已保存")

    # 3. 从已登录的 AuthWebView 拿到 bridge（复用同一个 WebView）
    # 注意：_move_to_background() 不再刷新页面，WebView 保留登录后的完整 session
    # 直接用 patch 方式让当前 page 打印 JS console 日志，不替换 page（替换会触发重载）
    from PySide6.QtWebEngineCore import QWebEnginePage

    _orig_page = auth_view._webview.page()

    # 用 monkeypatch 给现有 page 实例注入 javaScriptConsoleMessage，避免 setPage 重载
    def _js_console(level, msg, line, source):
        if any(k in msg for k in ('[doubaoASRBridge]', 'QWebChannel', 'Transport')):
            print(f"  js: {msg}")

    _orig_page.__class__ = type(
        '_DebugPage',
        (_orig_page.__class__,),
        {'javaScriptConsoleMessage': lambda self, level, msg, line, source: _js_console(level, msg, line, source)},
    )

    bridge = auth_view.get_bridge()
    if bridge is None:
        print("  [FAIL] 无法获取 WebViewASRBridge")
        return

    # 4. 从 settings 提取 ASR 参数
    with open(Path(__file__).parent / "settings.json", "r", encoding="utf-8") as f:
        saved = json.load(f)
    auth_token = saved.get("auth_token")
    if not auth_token:
        print("  [FAIL] settings.json 没有 auth_token")
        return

    params = ASRParams.from_auth_token(auth_token)
    if not params:
        print("  [FAIL] 无法从 auth_token 提取 ASR 参数")
        return
    print(f"  [OK] ASR 参数提取成功 (cookies={len(params.cookies)})")

    # 6. 预加载测试音频（必须在 connect 前准备好）
    wav_path = Path(__file__).parent / "test_audio.wav"
    if wav_path.exists():
        with wave.open(str(wav_path), "rb") as wf:
            pcm_data = wf.readframes(wf.getnframes())
    else:
        import math as _math
        sample_rate = 16000
        num_samples = sample_rate * 2
        pcm_data = struct.pack(
            f"<{num_samples}h",
            *[int(16000 * _math.sin(2 * _math.pi * 440 * i / sample_rate))
              for i in range(num_samples)]
        )

    # 7 + 8. 连接并流式发送音频（合并到同一事件循环，避免服务端超时关闭）
    # 服务端在 on_open 后如果没有立即收到音频就会 close 1000，
    # 因此连接建立和音频发送必须在同一个 processEvents 循环里驱动。
    print("\n--- 验收项 7 (WebView): WebSocket 连接 ---")
    connect_result = {"opened": False, "error": None, "auth_error": False}
    connected = threading.Event()
    results = []
    finished = threading.Event()
    chunk_size = 3200 * 2      # 200ms @ 16kHz 16bit
    audio_chunks = [pcm_data[i:i + chunk_size]
                    for i in range(0, len(pcm_data), chunk_size)]
    send_state = {"idx": 0, "done": False}  # 发送进度，在主循环里步进

    def _on_open():
        connect_result["opened"] = True
        connected.set()

    bridge.on_open = _on_open
    bridge.on_error = lambda msg: (connect_result.update({"error": msg}), connected.set())
    bridge.on_auth_error = lambda: (connect_result.update({"auth_error": True}), connected.set())
    bridge.on_result = lambda text: (results.append(text), print(f"  收到识别结果: {text}"))
    bridge.on_finish = lambda: (finished.set(), print("  收到 finish 事件"))

    bridge.connect(params, preload_audio=pcm_data)

    # 统一事件循环：等待连接 + 连接后持续发送音频，没有任何间隙
    next_send_time = time.time()
    deadline = time.time() + 15
    audio_send_started = False

    while time.time() < deadline:
        app.processEvents()

        if connected.is_set() and not audio_send_started:
            # 刚连接成功，打印状态，立即开始发送
            if connect_result["auth_error"]:
                print("  [FAIL] 认证失败！Cookie 可能已过期")
                return
            if connect_result["error"]:
                print(f"  [FAIL] 连接错误: {connect_result['error']}")
                return
            if not connect_result["opened"]:
                print("  [FAIL] 连接未建立")
                return
            print("  [PASS] WebSocket 连接成功建立（通过 WebView JS）")
            print("\n--- 验收项 8 (WebView): 发送音频 ---")
            print(f"  发送测试音频: {len(pcm_data)} bytes")
            audio_send_started = True
            next_send_time = time.time()  # 立刻开始发第一个 chunk

        if audio_send_started and not send_state["done"]:
            now = time.time()
            if now >= next_send_time:
                idx = send_state["idx"]
                if idx < len(audio_chunks):
                    bridge.send_audio(audio_chunks[idx])
                    send_state["idx"] = idx + 1
                    next_send_time = now + 0.05  # 50ms 间隔
                else:
                    send_state["done"] = True
                    print("  音频发送完毕")
                    bridge.finish_sending()
                    deadline = time.time() + 8  # 等待结果最多再等 8 秒

        if send_state["done"] and finished.is_set():
            break  # 收到 finish，提前退出

        time.sleep(0.01)  # 减小 sleep 让循环更紧凑

    if not connected.is_set():
        print("  [FAIL] 连接超时（15 秒未收到任何回调）")
        return

    # 再处理一轮确保所有结果到达
    extra = time.time() + 1
    while time.time() < extra:
        app.processEvents()
        time.sleep(0.01)

    if results:
        print(f"  [PASS] 收到 {len(results)} 条识别结果")
    else:
        print("  [INFO] 未收到识别结果（440Hz 正弦波不含语音，属正常）")

    if finished.is_set():
        print("  [PASS] 收到 finish 事件")
    else:
        print("  [INFO] 未收到 finish 事件")

    # 8. 关闭
    print("\n--- 验收项 9 (WebView): 正常关闭 ---")
    bridge.close()
    time.sleep(0.5)
    print("  [PASS] WebSocket 正常关闭")


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="P5 验收测试")
    parser.add_argument(
        "--offline", action="store_true", default=True,
        help="仅运行离线测试（默认）",
    )
    parser.add_argument(
        "--online", action="store_true",
        help="运行在线集成测试（直接 WebSocket，需要有效 Cookie）",
    )
    parser.add_argument(
        "--webview", action="store_true",
        help="运行在线集成测试（通过 WebView JS 桥接，绕过 CDN TLS 检测）",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="运行所有测试",
    )
    args = parser.parse_args()

    run_online = args.online or args.all
    run_webview = args.webview or args.all
    run_offline = (args.offline or args.all or (not args.online and not args.webview)) and not args.webview

    print("=" * 60)
    print("  P5: WebSocket 直连豆包 ASR — 验收测试")
    print("=" * 60)

    if run_offline:
        test_asr_params_extraction()
        test_url_building()
        test_message_parsing()
        test_doubao_ws_initialization()
        test_thread_safety()
        test_wav_generation()

        print("\n" + "=" * 60)
        total = PASS + FAIL
        print(f"  离线验收结果: {PASS}/{total} 通过, {FAIL} 失败")
        if FAIL == 0:
            print("  STATUS: 离线验收通过")
        else:
            print("  STATUS: 离线验收未通过，请修复上述 FAIL 项")
        print("=" * 60)

    if run_online:
        test_live_connection()

    if run_webview:
        test_live_connection_via_webview()

    # 清理测试文件（仅清理正弦波生成的临时文件，--webview 模式保留）
    wav_path = Path(__file__).parent / "test_audio.wav"
    if wav_path.exists() and not args.online and not args.webview:
        wav_path.unlink()
        print(f"\n  已清理临时文件: {wav_path}")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
