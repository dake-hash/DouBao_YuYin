# 豆包桌宠 — 语音输入工具

> 🎤 按住右Shift 说话，松手输出文字 — 使用豆包免费 ASR 服务。

## 功能

- **语音转文字**：长按右Shift 录音 → 松手自动识别 → 文本注入当前窗口
- **桌面宠物**：透明置顶的可爱桌宠，动画状态反馈
- **系统托盘**：最小化到托盘，右键菜单操作
- **安全无杀软风险**：使用 RegisterHotKey 系统原生 API，不注册任何键盘钩子

## 开发环境

- Python 3.12+
- Windows 10/11 64-bit

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/dake-hash/DouBao_YuYin.git
cd DouBao_YuYin

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python src/main.py
```

## 项目结构

```
├── src/
│   ├── main.py              # 入口
│   ├── app.py               # 应用生命周期
│   ├── tray.py              # 系统托盘
│   ├── settings.py          # 配置管理
│   ├── pet_window.py        # 桌宠窗口 (P1)
│   ├── pet_animation.py     # 动画管理 (P1)
│   ├── pet_menu.py          # 右键菜单 (P2)
│   ├── auth_webview.py      # 豆包登录 (P3)
│   ├── audio_capture.py     # 麦克风采集 (P4)
│   ├── audio_buffer.py      # 环形缓冲区 (P4)
│   ├── doubao_ws.py         # WebSocket 客户端 (P5)
│   ├── doubao_protocol.py   # 豆包协议编解码 (P5)
│   ├── hotkey.py            # 全局热键 (P6)
│   ├── text_output.py       # 文本注入 (P7)
│   ├── status_indicator.py  # 状态浮窗 (P8)
│   └── utils.py             # 通用工具
├── assets/                  # 资源文件
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
| P4 | 麦克风采集 | 待开发 |
| P5 | WebSocket 直连豆包 ASR | 待开发 |
| P6 | 全局热键 右Shift | 待开发 |
| P7 | 文本输出到活动窗口 | 待开发 |
| P8 | 全流程串联 + 状态反馈 | 待开发 |
| P9 | 打包分发 | 待开发 |

## License

MIT
