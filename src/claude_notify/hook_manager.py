"""
hook_manager.py — 读写 ~/.claude/settings.json 的 Hook 配置，以及锁文件管理
"""

import json
from pathlib import Path


_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def _notify_script_path(project_root: Path) -> str:
    script = project_root / "src" / "claude_notify" / "notify.py"
    return str(script).replace("\\", "/")


def lock_file_path(project_root: Path) -> Path:
    """返回锁文件路径（项目内，不在用户目录）。"""
    return project_root / "assets" / "claude_notify" / ".lock"


def acquire_lock(project_root: Path) -> None:
    """桌宠启动且语音助手开启时写入锁文件。"""
    lock_file_path(project_root).touch()


def release_lock(project_root: Path) -> None:
    """桌宠退出时删除锁文件。"""
    lf = lock_file_path(project_root)
    try:
        lf.unlink(missing_ok=True)
    except OSError:
        pass


def is_configured() -> bool:
    """检测 ~/.claude/settings.json 中是否已写入 Hook 配置。"""
    if not _CLAUDE_SETTINGS.exists():
        return False
    try:
        with open(_CLAUDE_SETTINGS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        hooks = data.get("hooks", {})
        return "Stop" in hooks and "PreToolUse" in hooks
    except (json.JSONDecodeError, OSError):
        return False


def write_hooks(project_root: Path) -> None:
    """将 Hook 写入 ~/.claude/settings.json，保留原有内容。"""
    script = _notify_script_path(project_root)

    data: dict = {}
    if _CLAUDE_SETTINGS.exists():
        try:
            with open(_CLAUDE_SETTINGS, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            data = {}

    hooks = data.setdefault("hooks", {})
    hooks["Stop"] = [
        {"hooks": [{"type": "command", "command": f"python {script} stop"}]}
    ]
    hooks["PreToolUse"] = [
        {"hooks": [{"type": "command", "command": f"python {script} notification"}]}
    ]

    _CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    with open(_CLAUDE_SETTINGS, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def get_manual_config_text(project_root: Path) -> str:
    """返回供用户手动填写的 JSON 片段说明。"""
    script = _notify_script_path(project_root)
    snippet = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": f"python {script} stop"}]}
            ],
            "PreToolUse": [
                {"hooks": [{"type": "command", "command": f"python {script} notification"}]}
            ],
        }
    }
    return json.dumps(snippet, indent=2, ensure_ascii=False)
