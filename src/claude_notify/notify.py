"""
notify.py — Claude Code Hook 播放脚本

由 Claude Code Hook 直接调用：
    python notify.py stop           → 播放 task_done.wav
    python notify.py notification   → 播放 need_input.wav
"""

import sys
import time
import winsound
from pathlib import Path

_AUDIO_DIR = Path(__file__).parent.parent.parent / "assets" / "claude_notify"

_SOUND_MAP = {
    "stop": _AUDIO_DIR / "task_done.wav",
    "notification": _AUDIO_DIR / "need_input.wav",
}

if __name__ == "__main__":
    event = sys.argv[1].lower() if len(sys.argv) > 1 else "stop"
    wav = _SOUND_MAP.get(event)
    if wav and wav.exists():
        time.sleep(1)
        winsound.PlaySound(str(wav), winsound.SND_FILENAME)
