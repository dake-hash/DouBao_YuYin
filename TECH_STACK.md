# 技术栈清单 — 豆包桌宠语音输入工具

## 运行时

| 组件 | 选型 | 版本 | 用途 |
|------|------|------|------|
| 语言 | Python | 3.12 | 主力开发语言 |
| 打包 | Nuitka | latest | 编译为原生 Windows exe，减小体积 |

## GUI 层

| 组件 | 选型 | 用途 | 备注 |
|------|------|------|------|
| 框架 | PySide6 | 桌面宠物窗口、系统托盘、菜单 | Qt for Python 官方绑定 |
| 动画 | QMovie (GIF) / QLottieWidget | 桌宠待机/聆听/思考动画 | 初期用 GIF 占位，后期切 Lottie |
| WebView | pywebview (WebView2) | 登录豆包时内嵌浏览器 | Windows 10/11 内置 Edge WebView2 Runtime |

## 音频层

| 组件 | 选型 | 用途 | 备注 |
|------|------|------|------|
| 采集 | PyAudio | 麦克风录音 | 基于 PortAudio，跨平台 |
| 格式 | PCM Int16, 16000Hz, 单声道 | 与豆包 WebSocket 协议对齐 | 20ms 一帧 (640 bytes) |
| 缓冲 | 自研环形缓冲区 (deque + Lock) | 边录边传 | 线程安全 |

## 网络层

| 组件 | 选型 | 用途 | 备注 |
|------|------|------|------|
| WebSocket | websocket-client | 直连豆包 ASR 服务 | wss://openspeech.bytedance.com |
| 协议 | 自研编解码 | 豆包自定义二进制协议 | 参考 doubao-murmur 实现 |
| HTTP | requests | 下载资源文件等 | 轻量级 HTTP 客户端 |

## 系统交互层

| 组件 | 选型 | 用途 | 备注 |
|------|------|------|------|
| 全局热键 | RegisterHotKey (win32gui) + GetAsyncKeyState (win32api) | 监听右Shift 长按 | 系统原生 API，无 hook，杀软安全 |
| 文本注入 | pywin32 | 剪贴板操作 / SendInput 模拟输入 | Win32 API Python 封装 |
| 窗口管理 | pywin32 (win32gui) | 获取活动窗口句柄 | 注入文本前确认目标窗口 |

## 数据持久化

| 组件 | 选型 | 用途 |
|------|------|------|
| 配置 | JSON (settings.json) | 开关状态、热键、登录凭证 |
| 凭证安全 | DPAPI (CryptProtectData) | 加密存储豆包 Cookie（可选，后期优化） |

## 开发工具

| 工具 | 用途 |
|------|------|
| Git | 版本控制 |
| GitHub | 代码托管 + Release 分发 |
| venv / uv | Python 虚拟环境管理 |

## 依赖清单 (requirements.txt)

```
PySide6>=6.6
pyaudio>=0.2.14
websocket-client>=1.8
pywebview>=5.2
pywin32>=306
Pillow>=10.0
requests>=2.31
```

## 系统要求（最终用户）

| 要求 | 最低配置 |
|------|------|
| 操作系统 | Windows 10 64-bit 或 Windows 11 |
| 运行时 | Edge WebView2 Runtime（Win11 内置，Win10 首次引导安装） |
| 内存 | 4GB+ |
| 硬盘 | 200MB 可用空间 |
| 网络 | 需要联网（豆包 ASR 服务为云端） |
| 音频 | 麦克风设备 |
