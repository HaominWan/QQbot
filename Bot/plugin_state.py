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
    """管理群聊自主回复模式的启用/禁用状态，支持持久化存储。

    自主回复模式（Agent Autonomous Mode）允许Bot在以下场景无需@或命令前缀即可自动回复：
    - JM推荐相关的高置信度意图（如"今天推荐本子"）
    - 求助问题的高置信度意图（如"有人知道怎么..."）
    - 其他工具需求的明确表达（如"画一张猫"）

    每个群的模式状态独立保存在JSON文件中，默认为关闭状态。
    """

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _group_key(group_id: int | str) -> str:
        return str(group_id).strip()

    def _load(self) -> list[str]:
        """从持久化存储（JSON文件）加载启用群组列表。

        返回格式：按群组ID排序的字符串列表

        容错处理：
        - 如果文件不存在，返回空列表
        - 如果文件读取失败，返回空列表并输出错误日志
        - 如果JSON格式无效，返回空列表
        - 如果groups字段不是列表，返回空列表
        - 清理无效的群组ID（空字符串等）

        Returns:
            排序后的启用群组ID列表
        """
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
        """将启用群组列表持久化到JSON文件。

        过程：
        1. 创建数据目录（如果不存在）
        2. 生成临时文件用于原子性写入（避免文件损坏）
        3. 将数据以JSON格式写入临时文件，使用缩进和中文可读性
        4. 原子性替换原文件（确保即使中途断电也不会损坏原文件）

        Args:
            groups: 已排序的群组ID列表
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"groups": sorted(groups)}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def is_enabled(self, group_id: int | str) -> bool:
        """检查指定群组的自主回复模式是否已启用。

        Args:
            group_id: 群组ID

        Returns:
            True if 该群已启用自主回复模式, False otherwise

        实现细节：从JSON文件加载最新的启用列表，然后检查该group_id是否在列表中
        """
        return self._group_key(group_id) in self._load()

    def enable(self, group_id: int | str) -> bool:
        """在指定群组启用自主回复模式。

        Args:
            group_id: 群组ID

        Returns:
            True if 状态发生了变化（从禁用→启用）, False if 已经是启用状态

        操作流程：
        1. 从持久化存储加载当前启用列表
        2. 检查该群组是否已经在列表中
        3. 如果不在列表中，将其添加到列表
        4. 保存更新后的列表回持久化存储
        """
        group_key = self._group_key(group_id)
        groups = set(self._load())
        if not group_key or group_key in groups:
            return False

        groups.add(group_key)
        self._save(sorted(groups))
        return True

    def disable(self, group_id: int | str) -> bool:
        """在指定群组禁用自主回复模式。

        Args:
            group_id: 群组ID

        Returns:
            True if 状态发生了变化（从启用→禁用）, False if 已经是禁用状态

        操作流程：
        1. 从持久化存储加载当前启用列表
        2. 检查该群组是否在列表中
        3. 如果在列表中，将其移除
        4. 如果移除后列表为空，则删除该群组的记录
        5. 保存更新后的列表回持久化存储
        """
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
