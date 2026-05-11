import json
import os
from pathlib import Path
from typing import Any


class GroupPluginBanStore:
    """Persists per-group plugin disable switches."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _normalize_plugin(plugin_name: str) -> str:
        return plugin_name.strip().lstrip(".").lower()

    @staticmethod
    def _group_key(group_id: int | str) -> str:
        return str(group_id)

    def _load(self) -> dict[str, list[str]]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data: Any = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[PluginState] Failed to read {self.path}: {exc}")
            return {}

        if not isinstance(data, dict):
            return {}

        normalized: dict[str, list[str]] = {}
        for group_id, plugins in data.items():
            if not isinstance(plugins, list):
                continue
            clean_plugins = sorted(
                {
                    self._normalize_plugin(str(plugin))
                    for plugin in plugins
                    if str(plugin).strip()
                }
            )
            if clean_plugins:
                normalized[str(group_id)] = clean_plugins
        return normalized

    def _save(self, data: dict[str, list[str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def is_banned(self, group_id: int | str, plugin_name: str) -> bool:
        data = self._load()
        return self._normalize_plugin(plugin_name) in data.get(self._group_key(group_id), [])

    def ban(self, group_id: int | str, plugin_name: str) -> bool:
        data = self._load()
        group_key = self._group_key(group_id)
        plugin_key = self._normalize_plugin(plugin_name)
        plugins = set(data.get(group_key, []))
        if plugin_key in plugins:
            return False

        plugins.add(plugin_key)
        data[group_key] = sorted(plugins)
        self._save(data)
        return True

    def unban(self, group_id: int | str, plugin_name: str) -> bool:
        data = self._load()
        group_key = self._group_key(group_id)
        plugin_key = self._normalize_plugin(plugin_name)
        plugins = set(data.get(group_key, []))
        if plugin_key not in plugins:
            return False

        plugins.remove(plugin_key)
        if plugins:
            data[group_key] = sorted(plugins)
        else:
            data.pop(group_key, None)
        self._save(data)
        return True
