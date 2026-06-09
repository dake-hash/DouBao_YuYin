# 豆包桌宠 — 语音输入工具

> 🎤 按住右Ctrl 说话，松手输出文字 — 使用豆包免费 ASR 服务。

## 功能

- **语音转文字**：长按右Ctrl 录音 → 松手自动识别 → 文本注入当前窗口
- **桌面宠物**：透明置顶的可爱桌宠，动画状态反馈
- **系统托盘**：最小化到托盘，右键菜单操作
- **安全无杀软风险**：使用 pynput 系统级键盘监听，不注册任何高危钩子

## 开发环境

- Python 3.10+
- Windows 10/11 64-bit

## 快速开始

### 第一步：获取项目

**方式一：下载压缩包（推荐新手）**
1. 点击页面右上角绿色 `Code` 按钮
2. 选择 `Download ZIP`
3. 解压到任意目录（如 `D:\DouBao_YuYin`）

**方式二：Git 克隆**(电脑上需要有git)
```bash
git clone https://github.com/dake-hash/DouBao_YuYin.git
```

### 第二步：启动项目

进入项目文件夹，根据你的情况双击对应脚本：

| 脚本 | 适用场景 |
|------|------|
| `start_venv.bat` | 唯一启动脚本。依赖会安装到项目独立虚拟环境，不影响系统 Python 环境。首次运行会自动安装依赖并清理约 230MB 无用文件，之后每次启动直接跳过。 |

**首次运行**会自动完成所有环境配置（含依赖安装和 PySide6 瘦身），需要等待几分钟。之后每次启动直接跳过安装步骤，秒级启动。

**前提条件：**
- 需要联网（安装依赖 + 豆包 ASR 服务）
- 需要有麦克风
- 需要有豆包账号（[doubao.com](https://www.doubao.com) 免费注册）

## 项目结构

```
├── src/
│   ├── main.py              # 入口
│   ├── app.py               # 应用生命周期
│   ├── tray.py              # 系统托盘
│   ├── settings.py          # 配置管理
│   ├── paths.py             # 路径常量
│   ├── pet_window.py        # 桌宠窗口
│   ├── pet_animation.py     # 动画管理
│   ├── pet_menu.py          # 右键菜单
│   ├── auth_webview.py      # 豆包登录
│   ├── audio_capture.py     # 麦克风采集
│   ├── audio_buffer.py      # 环形缓冲区
│   ├── doubao_ws.py         # WebSocket 客户端
│   ├── doubao_protocol.py   # 豆包协议编解码
│   ├── webview_asr_bridge.py # WebView JS 桥接 ASR
│   ├── hotkey.py            # 全局热键 右Ctrl
│   ├── text_output.py       # 文本注入
│   └── status_indicator.py  # 状态浮窗
├── assets/                  # 资源文件
├── cleanup_pyside6.py       # PySide6 瘦身脚本（首次运行自动执行）
├── requirements.txt
├── PROJECT_SPEC.md          # 完整需求规格
└── README.md
```

## 开发进度

| 阶段 | 内容 | 状态 |
|:---:|------|:---:|
| P0 | 项目骨架搭建 | ✅ 完成 |
| P1 | 桌宠 UI | ✅ 完成 |
| P2 | 开关状态管理 | ✅ 完成 |
| P3 | 豆包凭证提取 | ✅ 完成 |
| P4 | 麦克风采集 | ✅ 完成 |
| P5 | WebSocket 直连豆包 ASR | ✅ 完成 |
| P6 | 全局热键 右Ctrl | ✅ 完成 |
| P7 | 文本输出到活动窗口 | ✅ 完成 |
| P8 | 全流程串联 + 状态反馈 | 待开发 |
| P9 | 打包分发 | 待开发 |

## License

MIT
