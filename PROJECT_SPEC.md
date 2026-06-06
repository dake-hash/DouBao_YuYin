# 豆包桌宠语音输入工具 — 完整需求规格文档

> **用途**: 每次重开 Claude CLI 时粘贴本文档，告知当前进度到第几阶段，AI 验证后继续。
> **目标平台**: Windows 10/11
> **核心思路**: 参考 [doubao-murmur](https://github.com/lilong7676/doubao-murmur) (macOS)，用 WebSocket 直连豆包免费语音识别服务，不调用付费 API。
> **技术栈**: Python 3.12 + PySide6 + QWebEngineView + pyaudio + websocket-client

---

## 项目进度总览

| 阶段 | 内容 | 核心交付物 | 依赖 |
|:---:|------|-----------|:---:|
| **P0** | 项目骨架搭建 | 可运行的空窗口 + 系统托盘 | — |
| **P1** | 桌宠 UI | 透明桌面宠物 + 点击交互 + Lottie 动画 | P0 |
| **P2** | 开关状态管理 | 语音识别开关 + 状态持久化 + 视觉反馈 | P1 |
| **P3** | 豆包凭证提取 | WebView2 登录 → 提取 Cookie → 本地存储 | P0 |
| **P4** | 麦克风采集 | PCM 16kHz 音频流 + 录音缓冲区 | P0 |
| **P5** | WebSocket 直连豆包 ASR | 连接 → 发送音频 → 接收转录文本 | P3, P4 |
| **P6** | 全局热键 右Shift | 长按录音 / 松手停止 / 无杀软风险 | P5, P2 |
| **P7** | 文本输出到活动窗口 | 剪贴板注入 / SendInput 模拟输入 | P5 |
| **P8** | 全流程串联 + 状态反馈 | 端到端可用 + 录音/识别/输出 视觉提示 | P6, P7 |
| **P9** | 打包分发 | 单 exe 安装包 / 便携版 | P8 |

---

## 项目目录结构（目标态）

```
doubao-pet/
├── src/
│   ├── main.py                  # 入口：启动 App
│   ├── app.py                   # QApplication + 生命周期管理
│   ├── pet_window.py            # 桌宠窗口（透明、置顶、可拖动）
│   ├── pet_animation.py         # 动画管理（Lottie/帧序列）
│   ├── tray.py                  # 系统托盘图标与菜单
│   ├── settings.py              # 设置管理（JSON 持久化）
│   ├── auth_webview.py          # QWebEngineView 登录 + Cookie 提取 + 后台保活
│   ├── audio_capture.py         # 麦克风录音（PyAudio / WASAPI）
│   ├── audio_buffer.py          # 环形缓冲区（录音数据暂存）
│   ├── doubao_ws.py             # 豆包 WebSocket 客户端（Python 直连）
│   ├── doubao_protocol.py       # ASR 参数提取 + URL 构建 + JSON 消息解析
│   ├── webview_asr_bridge.py    # WebView JS 桥接层（主力 ASR 实现，绕过 TLS 指纹检测）
│   ├── _qwebchannel.js          # Qt 官方 QWebChannel JS 库（注入到 WebView）
│   ├── hotkey.py                # 全局热键监听（右Shift 长按，RegisterHotKey 方案）
│   ├── text_output.py           # 文本注入（剪贴板/SendInput）
│   ├── status_indicator.py      # 状态浮窗（录音中/识别中/完成）
│   ├── pet_menu.py              # 桌宠右键/点击菜单
│   └── utils.py                 # 通用工具函数
├── assets/
│   ├── pet_idle.json            # 桌宠待机动画（Lottie）
│   ├── pet_listening.json       # 桌宠"聆听中"动画
│   ├── pet_thinking.json        # 桌宠"识别中"动画
│   ├── icon.ico                 # 应用图标
│   └── tray_icon.png            # 托盘图标
├── requirements.txt
├── PROJECT_SPEC.md              # 本文档
└── README.md
```

---

## P0 — 项目骨架搭建

### 目标
创建一个能启动、显示空白窗口、出现在系统托盘的 Python 应用。

### 技术要点
- `PySide6` 作为 GUI 框架
- `QSystemTrayIcon` 系统托盘
- 主窗口隐藏（桌宠不是常规窗口）

### 具体任务
1. 初始化项目目录结构 `src/` `assets/`
2. 创建 `requirements.txt`：
   ```
   PySide6>=6.6
   PySide6-WebEngine>=6.6
   pyaudio>=0.2.14
   websocket-client>=1.8
   pywin32>=306
   Pillow>=10.0
   requests>=2.31
   ```
3. 编写 `main.py`：创建 QApplication，初始化托盘，进入事件循环
4. 编写 `app.py`：应用生命周期管理类 `DoubaoPetApp`
5. 编写 `tray.py`：系统托盘图标，右键菜单包含「退出」
6. 编写 `settings.py`：`Settings` 类，读写 JSON 配置文件，默认值：
   ```json
   {
     "voice_enabled": false,
     "hotkey": "rshift",
     "first_run": true,
     "auth_token": null,
     "auth_expiry": null
   }
   ```

### 验收标准
- [x] 运行 `python src/main.py` 不报错
- [x] 系统托盘出现图标
- [x] 右键托盘图标 → 点击「退出」→ 程序正常退出
- [x] 项目根目录生成 `settings.json` 文件

### 预期文件
```
doubao-pet/
├── src/
│   ├── main.py          ← P0 创建
│   ├── app.py           ← P0 创建
│   ├── tray.py          ← P0 创建
│   └── settings.py      ← P0 创建
├── assets/
│   └── tray_icon.png    ← P0 需要（可以先用纯色占位图）
├── requirements.txt     ← P0 创建
└── README.md            ← P0 创建
```

---

## P1 — 桌宠 UI

### 目标
创建一个透明、置顶、可拖动的桌面宠物窗口，带有待机动画。

### 技术要点
- `Qt.WindowStaysOnTopHint` 保持置顶
- `Qt.FramelessWindowHint` + `WA_TranslucentBackground` 实现透明无边框
- 窗口大小约 200×200 像素（可配置）
- 使用 QLabel + QMovie 播放 GIF，或用 QLottieWidget 播放 Lottie

### 具体任务
1. 编写 `pet_window.py`：`PetWindow(QWidget)`
   - 无边框、透明背景、始终置顶
   - 初始位置：屏幕右下角（计算屏幕几何）
   - 支持鼠标拖动：重写 `mousePressEvent` / `mouseMoveEvent`
   - 支持鼠标点击：重写 `mouseReleaseEvent`（区分拖动和点击）
2. 编写 `pet_animation.py`：`PetAnimation` 类
   - 管理动画状态切换（idle / listening / thinking）
   - 初期用 QMovie + GIF 占位，后期可替换为 Lottie
3. 在 `app.py` 中创建 `PetWindow` 实例
4. 生成占位动画资源（或从免费素材下载一个简单的 GIF）

### 验收标准
- [x] 启动后桌面右下角出现动画角色
- [x] 窗口没有边框、背景透明（只看到角色本身）
- [x] 角色始终在其他窗口上方
- [x] 可以用鼠标拖动角色到屏幕任意位置
- [x] 点击角色有反应（打印日志即可，P2 再做菜单）
- [x] 关闭程序时窗口正常销毁

### 预期文件
```
src/
├── pet_window.py      ← P1 创建
├── pet_animation.py   ← P1 创建
assets/
├── pet_idle.gif       ← P1 添加（占位动画）
```

---

## P2 — 开关状态管理

### 目标
点击桌宠弹出选项：「是否开启语音识别功能」。开启后保存状态，提供视觉反馈。

### 技术要点
- QMenu 或自定义弹出气泡作为点击菜单
- `Settings` 类读写 `voice_enabled` 字段
- 开启/关闭时桌宠切换不同动画或显示角标

### 具体任务
1. 编写 `pet_menu.py`：`PetMenu` 类
   - 点击桌宠时弹出菜单（QMenu 或自定义 Popup）
   - 菜单包含：
     - 「开启语音识别」/「关闭语音识别」（根据当前状态切换文字）
     - 「设置」
     - 「关于」
     - 「退出」
2. 语音识别开关逻辑：
   - 点击「开启」→ `settings.voice_enabled = True` → 保存 JSON
   - 点击「关闭」→ `settings.voice_enabled = False` → 保存 JSON
3. 视觉反馈：
   - 开启状态：桌宠旁边显示一个小绿点/绿色圆环（QLabel 叠加）
   - 关闭状态：小灰点/灰色圆环
   - 或切换动画（idle_active / idle_inactive）
4. 设置窗口（极简）：
   - 显示热键配置（初期只读，后期可修改）
   - 显示登录状态（初期显示「未登录」，P3 后联动）

### 验收标准
- [x] 点击桌宠弹出菜单
- [x] 点击「开启语音识别」→ settings.json 中 voice_enabled 变为 true
- [x] 再次点击桌宠 → 菜单显示「关闭语音识别」
- [x] 开启后桌宠外观有明显变化（绿点/高亮边框/不同动画）
- [x] 关闭程序重新打开 → 开关状态保持（读取 settings.json）
- [ ] 关闭状态下按右Shift 无反应（日志提示「语音未开启」）

### 预期文件
```
src/
├── pet_menu.py        ← P2 创建
assets/
├── indicator_on.png   ← P2 添加（绿点，16x16）
├── indicator_off.png  ← P2 添加（灰点，16x16）
```

---

## P3 — 豆包凭证提取

### 目标
通过内嵌 QWebEngineView 让用户登录豆包，提取认证凭证（Cookie / Token），保存到本地。登录完成后 WebView **不销毁**，移至后台隐藏窗口，供 P5 桥接层复用。

### 技术要点
- `PySide6.QtWebEngineWidgets.QWebEngineView` 内嵌浏览器（Chromium）
- 使用具名持久化 Profile `QWebEngineProfile("doubao-pet")`，Cookie 持久化到磁盘
- 导航到 `https://www.doubao.com/chat/`
- 登录状态检测：JS 轮询 `document.cookie` + localStorage，检测登录 UI 消失
- 凭证提取：两路并行
  - JS 端：`document.cookie` + `localStorage` + `sessionStorage`（可见内容）
  - CookieStore：`QWebEngineProfile.cookieStore().loadAllCookies()`（含 HttpOnly）
- **关键**：ByteDance SSO 登录 Cookie（`sessionid`、`uid_tt`、`sid_tt`）由 `passport.bytedance.com` 域设置，是跨域 Cookie，`document.cookie` 在 doubao.com 页面无法读取。这些 Cookie 只存在于 WebView 的内存 session 中，不写入磁盘。因此登录后必须保留 WebView 实例。
- 登录完成后 WebView 移至隐藏后台窗口（`keep_alive=True`），不调用 `setUrl` 刷新（刷新会丢失内存中的跨域 session）

### 具体任务
1. 编写 `auth_webview.py`：`AuthWebView(QDialog)` 类
   - 创建 `QWebEngineView`，绑定具名持久 Profile
   - 定时轮询 JS 检测登录状态
   - 登录完成后提取凭证，保存到 `settings.auth_token`（JSON 对象）
   - 设置 `settings.auth_expiry`（7天后过期）
   - `keep_alive=True`：移至隐藏后台窗口保留 session
   - `keep_alive=False`：销毁 WebView 释放内存
   - `get_bridge()` → 返回绑定在此 WebView 上的 `WebViewASRBridge`（P5 使用）
2. 在 `pet_menu.py` 中添加「登录豆包」菜单项
3. 登录状态检测：
   - 检查 `auth_token` 是否为 null
   - 检查 `auth_expiry` 是否已过期
   - 过期时桌宠显示提示（托盘气泡通知）

### 验收标准
- [x] 点击菜单「登录豆包」→ 弹出 QWebEngineView 窗口 → 显示豆包登录页
- [x] 用户在 WebView 中登录成功后 → 窗口自动关闭（移至后台）
- [x] `settings.json` 中 `auth_token` 不再为 null
- [x] WebView 窗口对用户不可见（隐藏到后台），进程内存正常
- [x] 凭证过期（模拟修改日期）→ 再次点击语音输入时提示「请重新登录豆包」
- [ ] 未登录状态下按右Shift → 无反应 + 托盘提示「请先登录豆包」

### 预期文件
```
src/
├── auth_webview.py    ← P3 创建
```

---

## P4 — 麦克风采集

### 目标
从系统麦克风采集 PCM 16kHz 16bit 单声道音频流，写入环形缓冲区。

### 技术要点
- `pyaudio` 或 `sounddevice` 访问音频设备
- 音频格式：**PCM Int16, 16000Hz, 单声道**（与豆包 WebSocket 协议匹配）
- 环形缓冲区 `audio_buffer.py`：支持边写边读
- 采集是可暂停的（不开语音时不占资源）

### 具体任务
1. 编写 `audio_buffer.py`：`AudioBuffer` 类
   - 线程安全的环形缓冲区（`collections.deque` + `threading.Lock`）
   - 方法：`write(chunk: bytes)` / `read(n_bytes: int) -> bytes` / `clear()`
   - 属性：`available_bytes` / `is_empty`
2. 编写 `audio_capture.py`：`AudioCapture` 类
   - 初始化 PyAudio，打开输入流
   - 配置：`format=paInt16, channels=1, rate=16000, frames_per_buffer=3200`
     - 3200 samples = 200ms per chunk（与豆包官方推荐的 20ms 有一定差异，需对齐）
   - `start()` → 开始采集，数据写入 AudioBuffer
   - `stop()` → 停止采集，清空缓冲区
   - 在独立线程中运行音频回调
3. 编写测试脚本验证：
   - 采集 3 秒音频 → 写入 WAV 文件 → 播放检查

### 验收标准
- [x] 调用 `AudioCapture.start()` → 开始从麦克风读取数据
- [x] 调用 `AudioCapture.stop()` → 停止读取，释放设备
- [x] `AudioBuffer` 在高频读写下无数据竞争（线程安全）
- [x] 测试 WAV 文件可正常播放，音频清晰
- [x] CPU 占用 < 5%（纯 I/O，无处理）
- [x] 不录音时不占用麦克风设备

### 预期文件
```
src/
├── audio_capture.py   ← P4 创建
├── audio_buffer.py    ← P4 创建
```

---

## P5 — WebSocket 直连豆包 ASR

### 目标
建立到豆包流式语音识别服务的 WebSocket 连接，发送 PCM 音频，接收实时转录结果。

### 技术要点（✅ 已通过实测验证）
- WebSocket 地址：**`wss://ws-samantha.doubao.com/samantha/audio/asr`**
- **协议极其简单** — 无二进制帧头 / 无握手消息：
  - **上行**：裸 PCM Int16 LE 音频，直接作为 WebSocket binary frame 发送
  - **下行**：纯 JSON 文本帧，event 类型只有 "result"（识别结果）和 "finish"（完成）
  - **认证**：依赖 WebView 内的 Chromium 网络栈自动携带 session Cookie（不在 Python 层手动拼 Cookie header）
- **架构选型：WebView JS 桥接**（不是 Python 直连）
  - 豆包服务端部署了 CDN/WAF（ArgusSecurityPlugin），会对 TLS 指纹做检测
  - Python `websocket-client` 直连被拦截（连接被重置）
  - 解决方案：通过 P3 保留的 QWebEngineView，在 Chromium 内部用 JS 发起 WebSocket
  - Chromium 的 TLS 指纹与真实浏览器一致，不被拦截
- 通信机制：`QWebChannel`（Python ↔ JS 双向）
  - Python → JS：emit Signal（connectASR / audioData / finishSending / closeASR）
  - JS → Python：调用 Slot（onOpen / onResult / onFinish / onError / onAuthError / onChannelReady）
- 预加载音频机制：`connect()` 时将音频 base64 编码传给 JS，在 `ws.onopen` 时立刻冲刷，避免服务端因无音频超时关闭

### 具体任务
1. 编写 `doubao_protocol.py`：`ASRParams` + URL 构建 + JSON 消息解析
   - `ASRParams.from_auth_token(auth_token)` → 从 P3 凭证中提取 cookies, device_id, web_id
   - `build_wss_url(params)` → 构建完整 WSS URL（含所有 query 参数）
   - `parse_message(raw_text)` → 解析服务端 JSON 响应 → `ServerMessage`
2. 编写 `doubao_ws.py`：`DoubaoWebSocket` 类（Python 直连版，用于非 CDN 拦截环境或测试）
3. 编写 `webview_asr_bridge.py`：`WebViewASRBridge` 类（主力实现）
   - `connect(params, preload_audio)` → 通过 QWebChannel 向 JS 发送连接指令
   - `send_audio(data: bytes)` → base64 编码后 emit audioData 信号
   - `finish_sending()` → emit finishSending 信号，JS 端冲刷后关闭 WS
   - `close()` → emit closeASR 信号
   - 回调：`on_open` / `on_result` / `on_finish` / `on_error` / `on_auth_error`
4. 在 JS 注入脚本（`_ASR_BRIDGE_JS`）中实现：
   - `initChannel()` → 初始化 QWebChannel，握手完成后通知 Python
   - `connectASR(url, cookieHeader, preloadedB64)` → 建立 WS，预加载音频写入缓冲
   - `ws.onopen` → 立刻冲刷预加载音频缓冲，再通知 Python `onOpen`
   - `ws.onmessage` → 解析 JSON，路由到 `onResult` / `onFinish` / `onAuthError`
   - `finishSending()` → 冲刷缓冲，发空帧 EOF，300ms 后关闭 WS

### 验收标准
- [x] `doubao_protocol.py` — URL 构建 + 参数提取 + 消息解析
- [x] `doubao_ws.py` — Python 直连 WebSocket 客户端
- [x] `webview_asr_bridge.py` — WebView JS 桥接层
- [x] WebSocket 连接成功建立（通过 WebView Chromium 网络栈）
- [x] `send_audio()` 持续收到 `on_result` 回调（流式识别结果）
- [x] 识别准确率与直接使用豆包 Web 版一致（实测："现在开始进行录音测试"）
- [ ] 连接失败时自动重试（输出日志）

### 预期文件
```
src/
├── doubao_ws.py           ← P5 创建 ✅
├── doubao_protocol.py     ← P5 创建 ✅
├── webview_asr_bridge.py  ← P5 创建 ✅（主力实现）
├── _qwebchannel.js        ← P5 创建 ✅（Qt 官方 QWebChannel JS 库）
```

---

## P6 — 全局热键 右Ctrl

### 目标
监听右 Ctrl 键的全局按下/释放事件，控制录音的开始和停止。与 P2 的语音开关状态联动。

使用 `pynput` 库监听全局键盘事件，在独立线程中运行，通过 Qt Signal 跨线程通知主线程。

### 为什么右 Ctrl？

```
右Shift 被排除的原因：
  - 长按 8 秒触发 Windows 粘滞键提示，打断录音
  - 部分输入法（搜狗等）用右Shift切换中英文，产生冲突

右Ctrl 的优势：
  - Windows 没有任何长按右Ctrl的系统行为
  - 短按/长按/连按均不触发任何系统功能
  - 绝大多数应用不绑定单独的右Ctrl
  - 用户单手可操作，另一只手可以继续敲键盘
```

### 技术原理

```
┌─ 按下右Ctrl ──────────────────────────────────────────┐
│                                                         │
│ ① pynput Listener.on_press 收到 Key.ctrl_r             │
│    (独立线程，不阻塞 Qt 事件循环)                        │
│                                                         │
│ ② 启动 200ms 计时线程                                   │
│    等待 _stop_event 或超时                              │
│                                                         │
│ ③ 若 200ms 内松手（on_release 触发 _stop_event）→ 取消  │
│    若超过 200ms → 录音指令 → recording_started Signal   │
│                                                         │
│ ④ 持续等待松手（_stop_event）或 30 秒超时               │
│    → recording_stopped Signal                           │
│                                                         │
│ ⑤ 超时保护: 连续录音 > 30 秒 → 自动停止，数据完整保留   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 具体任务

1. 编写 `hotkey.py`：`HotkeyManager` 类
   - 使用 `pynput.keyboard.Listener` 监听全局键盘事件
   - 状态机：`IDLE` → `WAITING_THRESHOLD` → `RECORDING` → `IDLE`
   - Qt Signal 定义：
     - `recording_started = Signal()` — 长按确认，开始录音
     - `recording_stopped = Signal()` — 松手或超时，停止录音
     - `hotkey_conflict = Signal(str)` — 保留接口兼容，pynput 方案不触发

2. 与 P2 联动：
   - `voice_enabled == False` → 按下右Ctrl 记录日志但忽略
   - `auth_token == None` → 按下右Ctrl 忽略 + 托盘气泡「请先登录豆包」

3. 与 P4 联动：
   - `recording_started` → 调用 `AudioCapture.start()`
   - `recording_stopped` → 调用 `AudioCapture.stop()` → 获取缓冲区音频数据

4. 短按过滤：
   - 按下右Ctrl → 启动 200ms 计时
   - 若 200ms 内松手 → 取消，不触发任何录音逻辑

### 验收标准

- [x] 在任何应用前台都能捕获右Ctrl 按下
- [x] 语音未开启时 → 按右Ctrl 无录音行为（日志「语音未开启，忽略热键」）
- [x] 未登录豆包时 → 按右Ctrl 无录音行为 + 托盘提示「请先登录豆包」
- [x] 语音已开启 + 已登录 → 按住右Ctrl > 200ms → 录音开始
- [x] 释放右Ctrl → 录音停止
- [x] 短按右Ctrl（< 200ms）→ 不触发录音
- [x] 长时间按住右Ctrl（> 30 秒）→ 自动停止，缓冲区数据完整保留
- [x] 正常打字 → 完全不触发热键日志
- [x] 程序退出时热键正确注销

### 预期文件

```
src/
├── hotkey.py          ← P6 创建
```

### 关键优势

| 对比维度 | keyboard 库 (hook) | RegisterHotKey (本方案) |
|----------|:---:|:---:|
| 杀软误报风险 | 🟡 中 | 🟢 极低 |
| 热键冲突检测 | ❌ 无（直接吃掉） | ✅ 注册失败即通知 |
| 正常打字干扰 | 需要过滤组合键 | ✅ 右Shift 打字时永不会按 |
| CPU 占用 | 事件驱动（低） | 50ms 轮询（极低） |
| 代码复杂度 | 低 | 中（需处理 Qt nativeEvent） |
| 用户操作直觉 | 组合键 | 单键长按（更简单） |

---

## P7 — 文本输出到活动窗口

### 目标
将 ASR 转录文本注入到用户当前使用的输入框中。

### 技术要点
- 按下热键前用 `GetForegroundWindow()` 记录目标窗口句柄
- 用 `AttachThreadInput` + `GetFocus` 获取目标窗口内的焦点子控件
- 用 `PostMessage WM_CHAR` 逐字符直接投递到目标控件的消息队列
- 完全不依赖焦点状态，不影响剪贴板内容
- PowerShell 不兼容（使用 DirectComposition 渲染，WM_CHAR 无效）；Claude Code CLI、VS Code 终端、记事本等主流环境均兼容

### 具体任务
1. 编写 `text_output.py`：`TextOutput` 类
   - `_get_focus_child(hwnd)` → 通过 AttachThreadInput 获取焦点子窗口句柄
   - `_post_text(hwnd, text)` → 逐字符 PostMessage WM_CHAR 到目标窗口
   - `_paste_via_sendinput(text)` → SendInput Unicode 备用方案
2. `hotkey.py` 在 `_on_press` 时记录 `GetForegroundWindow()`，松手后直接调用 `_post_text`

### 验收标准
- [x] 转录完成后文字自动出现在目标输入框
- [x] 支持中英文混合文本
- [x] 注入后剪贴板内容不丢失
- [x] Claude Code CLI 输入框测试通过
- [x] VS Code 终端测试通过
- [x] 记事本测试通过
- [ ] PowerShell 暂不支持（已知限制，后续考虑）

### 预期文件
```
src/
├── text_output.py     ← P7 创建
```

---

## P8 — 全流程串联 + 状态反馈

### 目标
把 P0-P7 的所有模块串联起来，实现完整的「登录豆包 → 开启语音 → 按住右Shift 说话 → 文字出现在输入框」流程。同时增加全流程中的视觉状态反馈。

### 技术要点
- 在 `app.py` 中编排所有模块的初始化和生命周期
- 状态指示器：一个半透明浮窗，显示当前状态
- 桌宠动画随状态切换

### 具体任务
1. 编写 `status_indicator.py`：`StatusIndicator` 类
   - 半透明浮窗（位于屏幕中央偏下）
   - 显示状态文本：
     - 「🎤 正在聆听...」（录音中，带动画波形）
     - 「🤔 识别中...」（等待 WebSocket 返回）
     - 「✅ 已输入」（文本成功注入，显示 1 秒后消失）
     - 「❌ 识别失败」（错误提示）
   - 纯 QLabel + QPropertyAnimation 淡入淡出
2. 扩展 `pet_animation.py`：
   - 录音中 → 播放 `pet_listening` 动画（嘴巴张开/耳朵竖起）
   - 识别中 → 播放 `pet_thinking` 动画（思考状）
   - 完成 → 播放一个短庆祝动画 → 恢复 `pet_idle`
3. 在 `app.py` 中实现完整流程编排：
   ```python
   # 伪代码
   def on_hotkey_press():
       if not settings.voice_enabled or not settings.auth_token:
           return
       audio_capture.start()
       doubao_ws.connect()
       doubao_ws.start_session()
       pet_animation.play("listening")
       status.show("正在聆听...")

   def on_hotkey_release():
       audio_capture.stop()
       doubao_ws.finish_session()
       pet_animation.play("thinking")
       status.show("识别中...")

   def on_transcription(text):
       text_output.output(text)
       pet_animation.play("done")
       status.show("已输入", duration=1000)
       pet_animation.play("idle")
   ```
4. 异常处理：
   - 录音设备被占用 → 托盘通知
   - WebSocket 连接失败 → 重试 3 次 → 提示用户检查网络
   - 识别结果为空 → 提示「未识别到语音」
5. 内存管理：
   - 每次录音结束后清空 AudioBuffer
   - 长时间不使用时 WS 连接自动关闭（5 分钟超时）
   - 程序退出时正确释放所有资源

### 验收标准
- [ ] 完整流程可跑通：开机 → 登录豆包 → 开启语音 → 按住右Shift → 说话 → 松手 → 文字出现在 CLI
- [ ] 录音时桌宠切换为「聆听中」动画
- [ ] 松手后桌宠切换为「识别中」动画
- [ ] 文字输出成功后桌宠有完成动画
- [ ] 状态浮窗正确显示各阶段状态
- [ ] 连续使用 10 次无内存泄漏（任务管理器观察）
- [ ] 异常情况有明确提示，不崩溃

### 预期文件
```
src/
├── status_indicator.py  ← P8 创建
assets/
├── pet_listening.json   ← P8 添加
├── pet_thinking.json    ← P8 添加
├── pet_done.json        ← P8 添加
```

---

## P9 — 打包分发

### 目标
将项目打包为 Windows 可执行文件，用户下载即可用，无需安装 Python 环境。

### 技术要点
- **Nuitka**（推荐）：编译为原生 exe，体积小，启动快
- 或 **PyInstaller**（备选）：简单但体积较大
- WebView2 Runtime：检测系统是否已安装（Win11 内置），Win10 提示安装
- 版本号管理 + 自动更新检查

### 具体任务
1. 打包配置：
   - 使用 Nuitka 编译为单个 exe
   - 包含所有 assets 资源文件
   - 排除不必要的 Python 模块以减小体积
2. 安装体验：
   - 首次运行自动创建桌面快捷方式
   - 自动检测 WebView2 Runtime
   - 首次运行引导：欢迎 → 登录豆包 → 设置热键 → 完成
3. 目标体积：
   - 期望 < 80MB（不含 WebView2 Runtime）
4. 编写 README：
   - 功能介绍 + GIF 演示
   - 安装步骤
   - 常见问题（麦克风权限、杀软警告等）
5. GitHub Release 发布：
   - 版本号 tag
   - exe 附件
   - 更新日志

### 验收标准
- [ ] 在干净 Win10 虚拟机中：下载 → 运行 → 功能正常
- [ ] 在干净 Win11 虚拟机中：下载 → 运行 → 功能正常
- [ ] exe 文件 < 100MB
- [ ] 杀软不报毒（或提供说明）
- [ ] README 清晰易懂

---

## 附录 A：关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| GUI 框架 | PySide6 | 成熟、文档多、支持透明窗口 |
| WebView | `PySide6.QtWebEngineWidgets.QWebEngineView` | 与 PySide6 原生集成，无需额外依赖，Chromium 内核 TLS 指纹与真实浏览器一致 |
| WebView Profile | `QWebEngineProfile("doubao-pet")` 具名持久化 | Cookie 持久化到磁盘；登录后保留 WebView 实例以保持跨域 session |
| ASR 连接方式 | `WebViewASRBridge`（WebView JS 桥接） | 豆包服务端 CDN/WAF 对 Python `websocket-client` 做 TLS 指纹检测并拦截；通过 Chromium 内部 JS 发起 WebSocket 可绕过 |
| Python ↔ JS 通信 | `QWebChannel` | Qt 原生双向通信，无需 HTTP server；Signal/Slot 映射直观 |
| 音频采集 | `pyaudio` | 跨平台、稳定、PortAudio 底层 |
| 全局热键 | `RegisterHotKey` (win32gui) + `GetAsyncKeyState` (win32api) | 无 hook、杀软安全、系统原生 API |
| 文本注入 | `pywin32` (剪贴板 + SendInput) | Windows 原生、最可靠 |
| 打包 | Nuitka | 编译为原生代码、体积更小 |

## 附录 B：关键风险

| 风险 | 级别 | 缓解措施 |
|------|:---:|------|
| 豆包 WebSocket 协议变更 | 🔴 高 | 参考 doubao-murmur 维护策略，关注其更新 |
| 豆包认证机制变更 | 🔴 高 | 凭证提取逻辑模块化，方便单独更新 |
| CDN/WAF TLS 指纹检测升级 | 🟡 中 | 已切换为 WebView JS 桥接，Chromium 指纹与真实浏览器一致；若进一步升级可考虑注入更多浏览器特征 |
| 杀软误报（全局键盘钩子） | 🟢 低 | 使用 RegisterHotKey + GetAsyncKeyState，不注册任何钩子，杀软不报 |
| 不同 CLI 终端文本注入兼容性 | 🟡 中 | 提供多种注入策略，用户可选 |
| 中文识别偶尔不准 | 🟢 低 | 豆包 ASR 准确率本身很高 |

## 附录 C：开发环境要求

```
Windows 10/11 64-bit
Python 3.12+
Git
Edge WebView2 Runtime (Win11 内置，Win10 需安装)
麦克风设备
```
