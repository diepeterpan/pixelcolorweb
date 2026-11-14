import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "device": {
        "address": None,
        "name": None,
        "auto_connect": True,
        "connected": False
    },
    "matrix": {
        "width": 96,
        "height": 16,
        "brightness": 80,
        "orientation": 0,
        "power": True
    },
    "mode": "text",  # "text", "script", "image", "clock", "schedule"
    "text": {
        "content": "HELLO MATRIX 96x16",
        "color": "#FF007F",
        "bg_color": "#000000",
        "rainbow_mode": 1,
        "animation": 1,  # 0: static, 1: scroll left, etc.
        "speed": 80,
        "font": "UNIFONT",
        "save_slot": 0
    },
    "active_script_id": "default_clock",
    "active_image": None,
    "clock": {
        "style": 1,
        "show_date": True,
        "format_24": True
    },
    "schedule": {
        "enabled": False,
        "slots": []
    },
    "presets": []
}

class ConfigManager:
    def __init__(self, config_path: str = "data/config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            self._config = DEFAULT_CONFIG.copy()
            self.save()
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config = self._deep_update(DEFAULT_CONFIG.copy(), data)
            except Exception as e:
                print(f"[ConfigManager] Error reading {self.config_path}: {e}. Using default.")
                self._config = DEFAULT_CONFIG.copy()
        return self._config

    def _deep_update(self, base: dict, updates: dict) -> dict:
        for k, v in updates.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                base[k] = self._deep_update(base[k], v)
            else:
                base[k] = v
        return base

    def get(self) -> Dict[str, Any]:
        return self._config

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        self._config = self._deep_update(self._config, updates)
        self.save()
        return self._config

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"[ConfigManager] Failed saving config: {e}")

config_manager = ConfigManager()

