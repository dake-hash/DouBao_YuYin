"""
installer.py — 一键配置：将 Hook 写入 ~/.claude/settings.json
"""

from pathlib import Path
from . import hook_manager


def install(project_root: Path) -> bool:
    """将 Hook 配置写入 ~/.claude/settings.json。返回是否成功。"""
    try:
        hook_manager.write_hooks(project_root)
        return True
    except OSError as exc:
        print(f"[ClaudeNotify] 写入 Hook 配置失败: {exc}")
        return False
