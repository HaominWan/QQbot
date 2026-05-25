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


class GroupBotBanStore:
    """Persists groups where the bot should stay silent."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _group_key(group_id: int | str) -> str:
        return str(group_id).strip()

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data: Any = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[PluginState] Failed to read {self.path}: {exc}")
            return []

        if isinstance(data, dict):
            groups = data.get("groups", [])
        else:
            groups = data

        if not isinstance(groups, list):
            return []

        return sorted({self._group_key(group) for group in groups if self._group_key(group)})

    def _save(self, groups: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"groups": sorted(groups)}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def is_banned(self, group_id: int | str) -> bool:
        return self._group_key(group_id) in self._load()

    def ban(self, group_id: int | str) -> bool:
        group_key = self._group_key(group_id)
        groups = set(self._load())
        if not group_key or group_key in groups:
            return False

        groups.add(group_key)
        self._save(sorted(groups))
        return True

    def unban(self, group_id: int | str) -> bool:
        group_key = self._group_key(group_id)
        groups = set(self._load())
        if group_key not in groups:
            return False

        groups.remove(group_key)
        self._save(sorted(groups))
        return True


class GroupAgentModeStore:
    """Persists groups where autonomous group-agent replies are enabled."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _group_key(group_id: int | str) -> str:
        return str(group_id).strip()

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data: Any = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[PluginState] Failed to read {self.path}: {exc}")
            return []

        if isinstance(data, dict):
            groups = data.get("groups", [])
        else:
            groups = data

        if not isinstance(groups, list):
            return []

        return sorted({self._group_key(group) for group in groups if self._group_key(group)})

    def _save(self, groups: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"groups": sorted(groups)}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def is_enabled(self, group_id: int | str) -> bool:
        return self._group_key(group_id) in self._load()

    def enable(self, group_id: int | str) -> bool:
        group_key = self._group_key(group_id)
        groups = set(self._load())
        if not group_key or group_key in groups:
            return False

        groups.add(group_key)
        self._save(sorted(groups))
        return True

    def disable(self, group_id: int | str) -> bool:
        group_key = self._group_key(group_id)
        groups = set(self._load())
        if group_key not in groups:
            return False

        groups.remove(group_key)
        self._save(sorted(groups))
        return True


class UserBanStore:
    """Persists users the bot should ignore globally."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _user_key(user_id: int | str) -> str:
        return str(user_id).strip()

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data: Any = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[PluginState] Failed to read {self.path}: {exc}")
            return []

        if isinstance(data, dict):
            users = data.get("users", [])
        else:
            users = data

        if not isinstance(users, list):
            return []

        return sorted({self._user_key(user) for user in users if self._user_key(user)})

    def _save(self, users: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"users": sorted(users)}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def is_banned(self, user_id: int | str) -> bool:
        return self._user_key(user_id) in self._load()

    def ban(self, user_id: int | str) -> bool:
        user_key = self._user_key(user_id)
        users = set(self._load())
        if not user_key or user_key in users:
            return False

        users.add(user_key)
        self._save(sorted(users))
        return True

    def unban(self, user_id: int | str) -> bool:
        user_key = self._user_key(user_id)
        users = set(self._load())
        if user_key not in users:
            return False

        users.remove(user_key)
        self._save(sorted(users))
        return True
