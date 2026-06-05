# 豆包桌宠语音输入工具 — 完整需求规格文档

> **用途**: 每次重开 Claude CLI 时粘贴本文档，告知当前进度到第几阶段，AI 验证后继续。
> **目标平台**: Windows 10/11
> **核心思路**: 参考 [doubao-murmur](https://github.com/lilong7676/doubao-murmur) (macOS)，用 WebSocket 直连豆包免费语音识别服务，不调用付费 API。
> **技术栈**: Python 3.12 + PySide6 + WebView2 + pyaudio + websocket-client

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
│   ├── auth_webview.py          # WebView2 登录 + Cookie 提取
│   ├── audio_capture.py         # 麦克风录音（PyAudio / WASAPI）
│   ├── audio_buffer.py          # 环形缓冲区（录音数据暂存）
│   ├── doubao_ws.py             # 豆包 WebSocket 客户端
│   ├── doubao_protocol.py       # 豆包二进制协议编解码
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
   pyaudio>=0.2.14
   websocket-client>=1.8
   pywebview>=5.2
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
通过内嵌 WebView2 让用户登录豆包，提取认证凭证（Cookie / Token），保存到本地。登录完成后销毁 WebView，后续不再需要浏览器。

### 技术要点
- `pywebview` 创建 WebView2 窗口（Windows 内置 Edge WebView2 Runtime）
- 导航到 `https://www.doubao.com/chat/`
- 用户手动登录后，通过 JS 注入提取 Cookie
- 保存到 `settings.json` 的 `auth_token` 字段
- **关键**：录完 Cookie 后立即销毁 WebView，释放内存

### 参考
doubao-murmur 的做法：
1. 内嵌 WKWebView → 加载 doubao.com
2. 用户手动登录
3. 提取 Cookie 和关键请求头（device_id, iid, etc.）
4. 销毁 WebView
5. 后续直接用 WebSocket + 凭证通信

### 具体任务
1. 编写 `auth_webview.py`：`AuthWebView` 类
   - 创建 WebView2 窗口，导航到 `https://www.doubao.com/chat/`
   - 等待用户登录（检测页面 URL 变化或特定 DOM 元素出现）
   - 登录成功后通过 `webview.evaluate_js()` 提取 `document.cookie`
   - 额外提取 localStorage/sessionStorage 中的关键 token
   - 保存到 `settings.auth_token`（JSON 对象）
   - 设置 `settings.auth_expiry`（7天后过期，提醒用户重新登录）
   - 关闭 WebView 窗口
2. 在 `pet_menu.py` 中添加「登录豆包」菜单项
3. 登录状态检测：
   - 检查 `auth_token` 是否为 null
   - 检查 `auth_expiry` 是否已过期
   - 过期时桌宠显示提示（托盘气泡通知）

### 验收标准
- [ ] 点击菜单「登录豆包」→ 弹出 WebView2 窗口 → 显示豆包登录页
- [ ] 用户在 WebView 中登录成功后 → 窗口自动关闭
- [ ] `settings.json` 中 `auth_token` 不再为 null
- [ ] WebView 窗口关闭后进程内存释放（任务管理器验证）
- [ ] 凭证过期（模拟修改日期）→ 再次点击语音输入时提示「请重新登录豆包」
- [ ] 未登录状态下按右Shift → 无反应 + 托盘提示「请先登录豆包」

### 关键风险点
> ⚠️ 豆包网页版可能使用 HttpOnly Cookie + 额外的设备指纹 token。
> 需要实际抓包确认需要哪些凭证。doubao-murmur 的源码中有完整的凭证提取逻辑，可直接参考。

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
- [ ] 调用 `AudioCapture.start()` → 开始从麦克风读取数据
- [ ] 调用 `AudioCapture.stop()` → 停止读取，释放设备
- [ ] `AudioBuffer` 在高频读写下无数据竞争（线程安全）
- [ ] 测试 WAV 文件可正常播放，音频清晰
- [ ] CPU 占用 < 5%（纯 I/O，无处理）
- [ ] 不录音时不占用麦克风设备

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

### 技术要点
- WebSocket 地址：`wss://openspeech.bytedance.com/api/v3/realtime/dialogue`
- 自定义二进制协议（参考 doubao-murmur 和火山引擎官方文档）
- 需要在连接时携带 P3 提取的凭证
- 支持流式发送（20ms 一包）和流式接收

### 协议概要（需验证）
```
消息格式：
[4字节 Header] + [Optional扩展字段] + [4字节 PayloadSize] + [Payload]

Header 结构（4字节）:
  - Protocol Version (4 bits)
  - Header Size (4 bits)
  - Message Type (4 bits)
  - Message Type Flags (4 bits)
  - Serialization Method (4 bits)
  - Compression Type (4 bits)
  - Reserved (8 bits)

主要消息类型:
  - FullClientRequest (0b0001): 客户端发送音频
  - FullServerResponse (0b1001): 服务端返回识别结果
```

### 具体任务
1. 编写 `doubao_protocol.py`：`DoubaoProtocol` 类
   - `build_header(msg_type, payload_size)` → 4 字节 header
   - `encode_message(msg_type, payload_json)` → 完整二进制消息
   - `decode_message(raw_bytes)` → (msg_type, payload_dict)
2. 编写 `doubao_ws.py`：`DoubaoWebSocket` 类
   - `connect(auth_token)` → 建立 WebSocket 连接
   - `send_audio(audio_chunk: bytes)` → 发送 20ms PCM 数据
   - `start_session()` → 发送 StartSession 消息
   - `finish_session()` → 发送 FinishSession 消息
   - `on_message(callback)` → 注册转录结果回调
   - `on_error(callback)` → 注册错误回调
   - `close()` → 正常关闭连接
   - 自动重连（最多 3 次）
3. 参考 doubao-murmur 源码实现具体协议细节
4. 编写单元测试：
   - 发送一段预录音频 → 验证收到转录结果

### 验收标准
- [ ] WebSocket 连接成功建立
- [ ] `start_session()` 后服务端返回确认
- [ ] `send_audio()` 持续收到 `on_message` 回调（流式识别结果）
- [ ] `finish_session()` 后收到最终完整结果
- [ ] 连接失败时自动重试（输出日志）
- [ ] 识别准确率与直接使用豆包 Web 版一致

### 关键风险点
> ⚠️ 这是整个项目技术风险最高的模块。
> 豆包的 WebSocket 协议和认证机制没有公开文档，需要逆向工程。
> **强烈建议**：先研究 doubao-murmur 的 Swift 源码，理解其握手和消息格式，
> 然后翻译到 Python。如果协议发生变化，这个模块是唯一需要大改的地方。

### 预期文件
```
src/
├── doubao_ws.py        ← P5 创建
├── doubao_protocol.py  ← P5 创建
```

---

## P6 — 全局热键 右Shift

### 目标
监听右 Shift 键的全局按下/释放事件，控制录音的开始和停止。与 P2 的语音开关状态联动。

**不使用任何键盘钩子（hook）**，采用 `RegisterHotKey` + `GetAsyncKeyState` 方案，
从根本上消除杀软误报风险。

### 为什么右 Shift？

```
右Shift 在绝大多数应用中无绑定 → 几乎不会热键冲突
左Shift 被大量应用占用（输入法切换、游戏奔跑键等）
单独一个键 → RegisterHotKey 的 MOD_NOREPEAT 天然防止按键重复触发
不是组合键 → 用户单手操作，另一只手可以继续敲键盘
```

### 技术原理

```
┌─ 按下右Shift ──────────────────────────────────────────┐
│                                                          │
│ ① RegisterHotKey 收到 WM_HOTKEY                         │
│    (系统通知，不拦截任何键盘事件——杀软不管)               │
│                                                          │
│ ② 启动 200ms 计时器 + 释放检测线程                       │
│    GetAsyncKeyState(VK_RSHIFT) 每 50ms 轮询              │
│                                                          │
│ ③ 若 200ms 内释放 → 这是一次普通按键 → 取消              │
│    若超过 200ms    → 录音指令 → AudioCapture.start()     │
│                                                          │
│ ④ 释放检测线程持续轮询                                    │
│    检测到 GetAsyncKeyState(VK_RSHIFT) >= 0 → 松手        │
│    → AudioCapture.stop() → 触发 WebSocket 转录           │
│                                                          │
│ ⑤ 超时保护: 连续录音 > 30 秒 → 自动停止                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 为什么杀软不报

```
RegisterHotKey  → 截图工具(QQ/微信/OBS)的标准 API → 杀软白名单习惯
GetAsyncKeyState → 游戏/录屏软件的标准 API        → 杀软不管
不注册 WH_KEYBOARD_LL 钩子 → 没有 keylogger 特征   → 启发式检测不触发
```

### 具体任务

1. 编写 `hotkey.py`：`HotkeyManager` 类
   ```python
   # 核心 API 调用（伪代码）
   import win32gui, win32con, win32api

   class HotkeyManager:
       HOTKEY_ID = 1
       HOLD_THRESHOLD_MS = 200       # 短按忽略阈值
       POLL_INTERVAL_MS = 50         # 释放检测轮询间隔
       MAX_RECORD_SECONDS = 30       # 最大录音时长（超时保护）

       def register(self, hwnd):
           """注册全局热键 右Shift"""
           # MOD_NOREPEAT: 按住不重复触发
           # VK_RSHIFT: 右Shift虚拟键码
           win32gui.RegisterHotKey(
               hwnd, self.HOTKEY_ID,
               win32con.MOD_NOREPEAT,
               win32con.VK_RSHIFT
           )

       def unregister(self, hwnd):
           """注销热键（程序退出时调用）"""
           win32gui.UnregisterHotKey(hwnd, self.HOTKEY_ID)

       def is_rshift_held(self):
           """检测右Shift是否仍被按住"""
           return win32api.GetAsyncKeyState(win32con.VK_RSHIFT) < 0

       # Qt 集成: 在 nativeEvent 中捕获 WM_HOTKEY
       # def nativeEvent(self, eventType, message):
       #     if message.message == win32con.WM_HOTKEY:
       #         self._on_hotkey_pressed()
   ```
   - 状态机：`IDLE` → `HOTKEY_PRESSED` → `WAITING_THRESHOLD` → `RECORDING` → `AWAIT_RELEASE` → `IDLE`
   - 在单独 QThread 中轮询释放状态（不阻塞 Qt 事件循环）
   - Qt Signal 定义：
     - `recording_started = Signal()` — 长按确认，开始录音
     - `recording_stopped = Signal()` — 松手确认，停止录音
     - `hotkey_conflict = Signal(str)` — 热键注册失败，通知冲突

2. 热键冲突处理：
   - `RegisterHotKey` 返回 0（注册失败）
   - → 发送 `hotkey_conflict` 信号
   - → 托盘气泡：「热键 右Shift 已被其他程序占用，请在设置中更换」
   - → 提供备选热键列表：`ScrollLock`、`F2`、`Pause` 等冷门键

3. 与 P2 联动：
   - `voice_enabled == False` → 收到 WM_HOTKEY 仍记录日志但忽略
   - `auth_token == None` → 收到 WM_HOTKEY 仍忽略 + 托盘气泡「请先登录豆包」

4. 与 P4 联动：
   - `recording_started` → 调用 `AudioCapture.start()`
   - `recording_stopped` → 调用 `AudioCapture.stop()` → 获取缓冲区音频数据

5. 短按过滤：
   - 按下右Shift → 启动 200ms 定时器
   - 若 200ms 内释放 → 这是一次普通按键 → 取消，不触发任何录音逻辑
   - 正常打字永远不会碰到右Shift → 不存在误触问题

### 验收标准

- [ ] 在任何应用前台都能捕获右Shift 按下（WM_HOTKEY 触发）
- [ ] 语音未开启时 → 按右Shift 无录音行为（日志记录热键事件被忽略）
- [ ] 未登录豆包时 → 按右Shift 无录音行为 + 托盘提示
- [ ] 语音已开启 + 已登录 → 按住右Shift > 200ms → 录音开始
- [ ] 释放右Shift → 录音停止 → 转录流程自动触发
- [ ] 短按右Shift（< 200ms）→ 不触发录音，行为一致
- [ ] 长时间按住右Shift（> 30 秒）→ 自动停止录音（超时保护）
- [ ] 正常打字（左Shift、字母键）→ 完全不触发热键
- [ ] 热键注册失败时 → 托盘通知冲突 + 引导用户换键
- [ ] 程序退出时热键正确注销（不残留注册）

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
将 P5 接收到的转录文本，注入到当前活动窗口的输入框中（即 CLI 输入框）。

### 技术要点
- 多种注入策略，按优先级尝试：
  1. **剪贴板粘贴**（最可靠）：复制文本→ `Ctrl+V` → 恢复原剪贴板
  2. **SendInput API**（备选）：模拟逐字键盘输入
  3. **WM_SETTEXT**（最后手段）：直接设置窗口文本
- 使用 `pywin32` 调用 Win32 API
- 注入前保存并恢复剪贴板内容

### 具体任务
1. 编写 `text_output.py`：`TextOutput` 类
   - `output(text: str)` → 自动选择最佳策略输出
   - `_paste_via_clipboard(text)` → 剪贴板方案
     - 保存当前剪贴板内容
     - 写入新文本到剪贴板
     - 模拟 `Ctrl+V`
     - 延迟 100ms 后恢复原剪贴板
   - `_paste_via_sendinput(text)` → SendInput 方案
     - 将文本转为键盘扫描码序列
     - 调用 `SendInput` API
     - 处理 Unicode 字符（中文等）
   - `get_active_window()` → 获取当前焦点窗口句柄
2. 支持「输入后自动回车」选项（可配置）
3. 输出日志：记录每次输出的文本和时间

### 验收标准
- [ ] 转录完成后文字自动出现在当前焦点输入框
- [ ] 支持中英文混合文本
- [ ] 注入后用户原剪贴板内容不丢失
- [ ] 在以下环境中测试通过：
  - Windows Terminal (PowerShell / CMD)
  - Claude Code CLI 输入框
  - VS Code 终端
  - 记事本（基准测试）

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
| WebView | `pywebview` (WebView2 后端) | Windows 内置、体积小 |
| 音频采集 | `pyaudio` | 跨平台、稳定、PortAudio 底层 |
| 全局热键 | `RegisterHotKey` (win32gui) + `GetAsyncKeyState` (win32api) | 无 hook、杀软安全、系统原生 API |
| 文本注入 | `pywin32` (剪贴板 + SendInput) | Windows 原生、最可靠 |
| WebSocket | `websocket-client` | 纯 Python、支持 WSS |
| 打包 | Nuitka | 编译为原生代码、体积更小 |

## 附录 B：关键风险

| 风险 | 级别 | 缓解措施 |
|------|:---:|------|
| 豆包 WebSocket 协议变更 | 🔴 高 | 参考 doubao-murmur 维护策略，关注其更新 |
| 豆包认证机制变更 | 🔴 高 | 凭证提取逻辑模块化，方便单独更新 |
| 杀软误报（全局键盘钩子） | 🟢 低 | 使用 RegisterHotKey + GetAsyncKeyState，不注册任何钩子，杀软不报 |
| WebView2 Runtime 未安装（Win10） | 🟡 中 | 首次运行检测并引导安装 |
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
