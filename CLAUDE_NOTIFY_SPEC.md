# Claude 语音助手 — 开发规格文档

> **分支**: `feature/claude-notify`（基于 `main` 分支新开，不影响主分支）
> **目标平台**: Windows 10/11
> **核心思路**: 通过 Claude Code Hook 机制，在 Claude 进入等待状态时播放本地 WAV 音频提醒用户

---

## 设计原则

- 项目目录以外，只允许修改 `~/.claude/settings.json`
- 音频文件、播放脚本全部存放在项目目录内，与桌宠 GIF 资源同等地位
- 零新增外部依赖，仅使用 Python 标准库
- 项目目录不可移动（Hook 命令写入绝对路径）

---

## 功能概述

### 触发场景

| 场景 | Claude Code Hook 事件 | 音频文件 |
|------|----------------------|---------|
| Claude 完成任务，等待用户指令 | `Stop` | `task_done.wav` |
| Claude 主动提问，等待用户回复 | `Notification` | `need_input.wav` |

### 托盘菜单

- 在右键托盘菜单顶层新增「Claude 语音助手」开关项
- 开关状态持久化到项目 `settings.json`，重启桌宠后保持上次状态
- 默认关闭

### 开启逻辑

1. 用户点击「Claude 语音助手」
2. 检测 `~/.claude/settings.json` 中是否已写入 Hook 配置
3. 若**未配置** → 弹出配置窗口，提供两个按钮：「一键配置」和「手动配置说明」
4. 若**已配置** → 直接开启，菜单项显示选中状态

### 一键配置执行内容

- 读取项目当前绝对路径
- 将 Hook 命令（指向项目内 `notify.py` 的绝对路径）写入 `~/.claude/settings.json`
- 若 `settings.json` 已存在其他配置，合并写入，不覆盖原有内容

### 关闭逻辑

- 再次点击菜单项即关闭
- 关闭后 `~/.claude/settings.json` 中的 Hook 配置保留，不删除
- 下次开启时无需重新配置

### 多窗口行为

无需特殊处理。`winsound.PlaySound` 为阻塞调用，多个 Claude Code 窗口同时触发时顺序播放，不会混叠。

---

## 项目文件清单

### 新增文件

```
项目目录/
├── assets/
│   └── claude_notify/
│       ├── task_done.wav          # 任务完成提示音（默认文案："任务已完成，等待您的指令"）
│       └── need_input.wav         # 等待回复提示音（默认文案："Claude 需要您的回复"）
└── src/
    └── claude_notify/
        ├── __init__.py
        ├── notify.py              # Hook 调用的播放脚本（由 Hook 直接执行）
        ├── hook_manager.py        # 读写 ~/.claude/settings.json 的 Hook 配置
        └── installer.py           # 一键配置逻辑：写入 Hook 到 settings.json
```

### 修改文件

```
src/
├── tray.py        # 新增「Claude 语音助手」菜单项及开关逻辑
├── pet_menu.py    # 新增配置弹窗（一键配置 / 手动配置说明）
└── settings.py    # 新增 claude_notify_enabled 字段
```

---

## 各模块规格

### `notify.py`

被 Claude Code Hook 直接调用，接收事件参数，播放对应 WAV 文件。

```
调用方式：python <项目绝对路径>/src/claude_notify/notify.py <event>
参数：
  stop          → 播放 task_done.wav
  notification  → 播放 need_input.wav
```

逻辑：
- 根据 `sys.argv[1]` 确定事件类型
- 用 `pathlib` 推算出 `assets/claude_notify/` 的绝对路径
- 调用 `winsound.PlaySound()` 播放对应 WAV 文件
- 文件不存在时静默退出，不报错

### `hook_manager.py`

负责读写 `~/.claude/settings.json`。

方法：
- `is_configured() -> bool` — 检测 Hook 配置是否已写入
- `write_hooks(project_root: Path)` — 将两个 Hook 写入 settings.json（合并，不覆盖原有内容）
- `get_manual_config_text(project_root: Path) -> str` — 返回供用户手动填写的 JSON 片段

### `installer.py`

被桌宠「一键配置」按钮调用。

方法：
- `install(project_root: Path) -> bool` — 调用 `hook_manager.write_hooks()`，返回是否成功

### `settings.py` 新增字段

```json
{
  "claude_notify_enabled": false
}
```

### `tray.py` 改动

- 在托盘右键菜单顶层插入「Claude 语音助手」`QAction`，设置 `setCheckable(True)`
- 读取 `settings.claude_notify_enabled` 初始化选中状态
- 点击时调用开关逻辑

### `pet_menu.py` 改动

新增 `ClaudeNotifyConfigDialog(QDialog)`：
- 提示文案：「您尚未配置 Claude Code Hook，语音助手无法工作。请选择配置方式：」
- 按钮一：「一键配置」→ 调用 `installer.install()`，成功后提示重启 Claude Code
- 按钮二：「手动配置说明」→ 展示 JSON 片段和操作步骤

---

## 技术规格

| 项目 | 说明 |
|------|------|
| 平台 | Windows 10/11 |
| Python 版本 | 3.10+ |
| 新增外部依赖 | 零 |
| 音频播放 | `winsound.PlaySound`（Python 标准库） |
| 配置读写 | `json` + `pathlib`（Python 标准库） |
| 参数解析 | `sys`（Python 标准库） |

---

## 资源规格

| 文件 | 默认文案 | 格式 | 预估大小 |
|------|---------|------|---------|
| `task_done.wav` | 任务已完成，等待您的指令 | WAV | 300~500 KB |
| `need_input.wav` | Claude 需要您的回复 | WAV | 200~350 KB |

用户可直接用自备 WAV 文件覆盖 `assets/claude_notify/` 内的同名文件，替换后立即生效，无需重启任何程序。

---

## 资源与内存占用

| 项目 | 估算 |
|------|------|
| 新增磁盘占用（代码） | < 10 KB |
| 新增磁盘占用（音频） | 500 KB ~ 900 KB |
| 桌宠常驻内存增量 | 1 MB ~ 3 MB |
| Hook 触发时瞬时内存 | 10 MB ~ 20 MB（播放完毕即释放） |

---

## 验收标准

- [ ] 右键托盘菜单顶层出现「Claude 语音助手」开关项
- [ ] 首次点击开启 → 弹出配置窗口
- [ ] 点击「一键配置」→ `~/.claude/settings.json` 写入两个 Hook，不破坏原有内容
- [ ] 点击「手动配置说明」→ 展示正确的 JSON 片段
- [ ] 已配置状态下点击开启 → 直接生效，不弹窗
- [ ] 再次点击菜单项 → 关闭功能，settings.json Hook 保留
- [ ] 开关状态重启桌宠后保持
- [ ] Claude Code 完成任务时播放 `task_done.wav`
- [ ] Claude Code 等待回复时播放 `need_input.wav`
- [ ] 音频文件被替换后，下次触发立即播放新文件
- [ ] 多个 Claude Code 窗口同时触发时，音频顺序播放，不混叠

---

## 不在范围内

- macOS / Linux 支持
- 在线 TTS / 动态语音内容
- 与 Claude Code 进程直接通信
- 桌面弹窗通知
- 卸载时自动清理 `settings.json` 中的 Hook 配置
