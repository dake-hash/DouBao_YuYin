"""
settings.py — 设置管理（JSON 持久化）

P0: 提供 Settings 类，读写项目根目录的 settings.json 文件。
"""

import json
from pathlib import Path
from typing import Any, Optional


class Settings:
    """应用设置管理，读写 JSON 配置文件。

    默认配置:
        voice_enabled: False  — 语音识别是否开启
        hotkey: "rshift"      — 全局热键
        first_run: True       — 是否首次运行
        auth_token: None      — 豆包登录凭证
        auth_expiry: None     — 凭证过期时间
    """

    DEFAULT_SETTINGS: dict[str, Any] = {
        "voice_enabled": False,
        "hotkey": "rshift",
        "first_run": True,
        "auth_token": None,
        "auth_expiry": None,
    }

    def __init__(self, filepath: Optional[str] = None) -> None:
        if filepath is None:
            # 默认保存在项目根目录
            filepath = Path(__file__).parent.parent / "settings.json"
        self._filepath = Path(filepath)
        self._data: dict[str, Any] = dict(self.DEFAULT_SETTINGS)
        self.load()

    # ------------------------------------------------------------------
    # 文件 I/O
    # ------------------------------------------------------------------

    def load(self) -> None:
        """从 JSON 文件载入设置，文件不存在或损坏时使用默认值。"""
        try:
            if self._filepath.exists():
                with open(self._filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                for key in self.DEFAULT_SETTINGS:
                    if key in data:
                        self._data[key] = data[key]
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[Settings] 加载配置失败，使用默认值: {exc}")

    def save(self) -> None:
        """保存当前设置到 JSON 文件。"""
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self._filepath, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[Settings] 保存配置失败: {exc}")

    # ------------------------------------------------------------------
    # 属性访问器（修改后自动保存）
    # ------------------------------------------------------------------

    @property
    def voice_enabled(self) -> bool:
        return self._data["voice_enabled"]

    @voice_enabled.setter
    def voice_enabled(self, value: bool) -> None:
        self._data["voice_enabled"] = value
        self.save()

    @property
    def hotkey(self) -> str:
        return self._data["hotkey"]

    @hotkey.setter
    def hotkey(self, value: str) -> None:
        self._data["hotkey"] = value
        self.save()

    @property
    def first_run(self) -> bool:
        return self._data["first_run"]

    @first_run.setter
    def first_run(self, value: bool) -> None:
        self._data["first_run"] = value
        self.save()

    @property
    def auth_token(self) -> Optional[Any]:
        return self._data["auth_token"]

    @auth_token.setter
    def auth_token(self, value: Optional[Any]) -> None:
        self._data["auth_token"] = value
        self.save()

    @property
    def auth_expiry(self) -> Optional[str]:
        return self._data["auth_expiry"]

    @auth_expiry.setter
    def auth_expiry(self, value: Optional[str]) -> None:
        self._data["auth_expiry"] = value
        self.save()

    # ------------------------------------------------------------------
    # 通用访问
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()
