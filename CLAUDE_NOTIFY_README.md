# Claude 语音助手 — 使用指南

当 Claude Code 完成任务或等待你回复时，桌宠会自动播放语音提醒，让你专注于其他事情而不必盯着屏幕。

---

## 前提条件

- 豆包桌宠已安装并可正常运行
- Claude Code 已安装
- **项目目录不可移动**（配置中写入的是绝对路径，移动后需重新配置）

---

## 开启 Claude 语音助手

**第一步：启动桌宠**

按照桌宠原有方式启动，托盘图标出现后继续下一步。

**第二步：点击开关**

右键点击托盘图标，点击顶部的「Claude 语音助手」。

**第三步：完成配置**

首次开启会弹出配置窗口。选择其中一种方式：

- **一键配置**（推荐）→ 桌宠自动完成所有配置
- **手动配置说明** → 查看手动修改步骤，自行操作

**第四步：重启 Claude Code**

关闭并重新打开 Claude Code，功能立即生效。

> 先开桌宠还是先开 Claude Code 均可，顺序不影响使用。

---

## 手动配置说明

如果选择手动配置，打开以下文件（不存在则新建）：

```
C:\Users\你的用户名\.claude\settings.json
```

将以下内容写入，把 `<项目绝对路径>` 替换为你的实际路径（例如 `D:/DouBao_YuYin`）：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python <项目绝对路径>/src/claude_notify/notify.py stop"
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python <项目绝对路径>/src/claude_notify/notify.py notification"
          }
        ]
      }
    ]
  }
}
```

保存后重启 Claude Code 即可生效。

> 如果 `settings.json` 已有其他配置内容，只需将 `"hooks"` 部分合并进去，不要替换整个文件。

---

## 替换音频文件

默认提示音位于项目目录：

```
assets/claude_notify/
├── task_done.wav      # Claude 完成任务时播放
└── need_input.wav     # Claude 等待你回复时播放
```

用自备 WAV 文件直接覆盖对应文件，**文件名必须保持不变**，替换后立即生效，无需重启。

---

## 关闭功能

右键托盘图标，再次点击「Claude 语音助手」开关即可关闭。

关闭后 `settings.json` 中的 Hook 配置保留，下次开启时无需重新配置。

---

## 常见问题

**开启了但没有声音？**

检查以下几项：
1. 系统音量是否已静音
2. `assets/claude_notify/` 目录下是否存在两个 WAV 文件
3. `~/.claude/settings.json` 中是否已写入 Hook 配置（可在桌宠菜单重新执行一键配置）
4. 是否已重启过 Claude Code

**项目目录移动后怎么办？**

重新在桌宠菜单执行「一键配置」，会用新路径覆盖旧配置。

**能不能让它说别的话？**

可以。用任意工具录制一段 WAV 文件，覆盖 `assets/claude_notify/` 里对应的文件即可。文件名保持 `task_done.wav` 或 `need_input.wav` 不变。

**多开了几个 Claude Code 窗口，会不会同时播两个声音？**

不会。多个窗口同时触发时，音频会依次顺序播放。
