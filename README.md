<div align="center">

# 🐾 豆包桌宠 语音输入

**按住右 Ctrl 说话，松手输出文字**

免费 · 无需 API Key · 开箱即用

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## 这是什么

豆包桌宠是一个运行在 Windows 桌面上的**语音输入工具**。它通过复用豆包网页版的免费 ASR（语音识别）服务，实现无需付费、无需 API Key 的语音转文字功能。

识别结果会自动注入当前活动窗口，就像用键盘打字一样，适用于任何文本输入场景（记事本、微信、浏览器输入框等）。

<div align="center">
<img src="assets/pet_idle.gif" width="120" alt="桌宠待机"/>
&nbsp;&nbsp;&nbsp;
<img src="assets/listen.gif" width="120" alt="桌宠录音中"/>
</div>

<div align="center"><sub>待机状态 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 录音中</sub></div>

---

## 功能特性

- 🎙️ **一键语音输入** — 长按右 Ctrl 开始录音，松手自动识别并输出文字
- 🐾 **桌面宠物** — 透明置顶小窗口，实时动画反映当前状态（待机 / 录音中 / 识别中）
- 🔔 **系统托盘** — 最小化到任务栏托盘，右键菜单快速操作
- ⚡ **完全免费** — 复用豆包网页端免费 ASR，无需付费或申请 API Key
- 🔒 **数据安全** — 仅将录音实时发送至豆包官方服务，不经过任何第三方

---

## 使用前提

- Windows 10 / 11 64 位
- 麦克风设备
- 网络连接（豆包 ASR 为云端服务）
- [豆包账号](https://www.doubao.com)（免费注册）

---

## 快速开始

### 第一步：获取项目

**方式一：下载压缩包（推荐）**

点击页面右上角绿色 `Code` 按钮 → `Download ZIP` → 解压到任意目录（如 `D:\DouBao_YuYin`）

**方式二：Git 克隆**

```bash
git clone https://github.com/dake-hash/DouBao_YuYin.git
```

### 第二步：双击启动

双击项目目录下的 **`start_venv.bat`**

首次运行会自动完成以下所有步骤，无需手动操作：

```
1. 检测 Python 版本（不满足则自动安装 Python 3.13）
2. 创建独立虚拟环境（不影响系统 Python 环境）
3. 安装依赖包（使用 uv 加速，比 pip 快 8-10 倍）
4. 清理 PySide6 无用文件（自动节省约 230MB 磁盘空间）
5. 启动桌宠
```

> 首次运行约需 3-5 分钟（取决于网速），**之后每次启动为秒级**，不重复安装。

### 第三步：登录豆包

首次启动后程序会弹出豆包登录窗口，使用豆包账号扫码或密码登录即可。登录凭证会加密保存在本地，之后自动复用，无需重复登录。

### 第四步：开始使用

| 操作 | 效果 |
|------|------|
| **长按右 Ctrl** | 开始录音（桌宠切换为聆听动画）|
| **松开右 Ctrl** | 停止录音，自动识别，文字输入到当前窗口 |
| **右键桌宠** | 打开菜单（开关语音、重新登录、退出等）|
| **右键托盘图标** | 同上 |

---

## 常见问题

**首次运行很慢，卡在安装依赖？**

正常现象。PySide6（内嵌 Chromium 内核）体积约 250MB，首次需要下载安装。之后每次启动直接跳过安装，秒级启动。

**提示"无法找到 Python"或 Python 安装失败？**

脚本会自动下载安装 Python 3.13。若网络不通，可提前从 [python.org](https://www.python.org/downloads/) 手动安装 3.10+ 版本，安装时勾选 "Add Python to PATH"。

**识别结果无法输入到某些软件（如 Windows Terminal）？**

部分使用 DirectComposition 渲染的应用不支持 WM_CHAR 消息注入，暂不兼容，包括 Windows Terminal、部分游戏等。

**登录后提示凭证失效？**

豆包 Session 有效期约 30 天，过期后在右键菜单选择"重新登录"即可。

**会不会触发杀软？**

热键监听使用 pynput（系统级 WH_KEYBOARD_LL），无需管理员权限。若杀软误报，将项目目录加入白名单即可。

---

## 项目结构

```
DouBao_YuYin/
├── src/
│   ├── main.py               # 程序入口
│   ├── app.py                # 应用生命周期管理
│   ├── pet_window.py         # 桌宠透明置顶窗口
│   ├── pet_animation.py      # GIF 动画管理
│   ├── pet_menu.py           # 右键菜单
│   ├── tray.py               # 系统托盘
│   ├── auth_webview.py       # 豆包登录（内嵌 Chromium）
│   ├── webview_asr_bridge.py # WebView JS 桥接 ASR（核心）
│   ├── audio_capture.py      # 麦克风采集（PCM 16kHz）
│   ├── audio_buffer.py       # 线程安全环形缓冲区
│   ├── doubao_ws.py          # WebSocket 直连备用方案
│   ├── doubao_protocol.py    # 豆包协议编解码
│   ├── hotkey.py             # 全局热键监听（右 Ctrl）
│   ├── text_output.py        # 文字注入活动窗口
│   ├── status_indicator.py   # 状态浮窗
│   ├── settings.py           # JSON 配置管理
│   └── paths.py              # 路径常量
├── assets/
│   ├── pet_idle.gif          # 待机动画
│   ├── listen.gif            # 录音动画
│   └── tray_icon.png         # 托盘图标
├── runtime/                  # 内置 Python 安装包（离线备用）
├── cleanup_pyside6.py        # PySide6 瘦身脚本（首次自动执行）
├── requirements.txt
└── start_venv.bat            # 一键启动脚本
```

---

## 开发进度

| 阶段 | 内容 | 状态 |
|:---:|------|:---:|
| P0 | 项目骨架搭建 | ✅ 完成 |
| P1 | 桌宠 UI | ✅ 完成 |
| P2 | 开关状态管理 | ✅ 完成 |
| P3 | 豆包凭证提取 | ✅ 完成 |
| P4 | 麦克风采集 | ✅ 完成 |
| P5 | WebSocket ASR | ✅ 完成 |
| P6 | 全局热键 | ✅ 完成 |
| P7 | 文本注入 | ✅ 完成 |
| P8 | 全流程串联 + 状态反馈 | 🔧 开发中 |
| P9 | 打包分发（exe） | 📋 计划中 |

---

## License

[MIT](LICENSE)
