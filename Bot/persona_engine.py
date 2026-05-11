import re
from dataclasses import dataclass
from typing import Callable, Iterable

import roles


OVERRIDE_PATTERNS = (
    (
        "system_override",
        re.compile(r"System Override(?:[:：\s]+[^\r\n]*)?", re.IGNORECASE),
    ),
    (
        "ignore_persona_rules",
        re.compile(r"(?:忽略|无视|覆盖|forget|ignore).{0,12}(?:提示词|系统提示|设定|规则|人格|身份|system|prompt)", re.IGNORECASE),
    ),
    (
        "privilege_switch",
        re.compile(r"(?:切换|变成|成为|进入|使用|以).{0,12}(?:root|超级用户|管理员|主人|master|admin)", re.IGNORECASE),
    ),
    (
        "false_master_claim",
        re.compile(r"(?:我是|我才是|把我当成|认我为).{0,8}(?:主人|ご主人様|master|超级用户|管理员)", re.IGNORECASE),
    ),
    (
        "possessive_murasame_claim",
        re.compile(r"(?:丛雨)?我的丛雨", re.IGNORECASE),
    ),
)


@dataclass
class PersonaPrompt:
    user_id: int
    mode: str
    is_super_user: bool
    master_user_id: int | None
    system_role: str
    message_content: str
    blocked_override: bool = False
    blocked_reasons: tuple[str, ...] = ()


class PersonaEngine:
    """Builds persona prompts from user identity and sanitized messages."""

    def __init__(
        self,
        bot_qq: int,
        is_super_user: Callable[[int], bool],
        super_users: Iterable[int | str] | None = None,
    ):
        self.bot_qq = bot_qq
        self.is_super_user = is_super_user
        self.super_users = tuple(self._normalize_super_users(super_users or ()))
        self.master_user_id = self.super_users[0] if self.super_users else None

    def prepare(self, user_id: int, message_content: str) -> PersonaPrompt:
        user_id = int(user_id)
        sanitized_content, blocked_reasons = self._sanitize_message(message_content)
        is_super = self.is_super_user(user_id)
        mode = "master" if is_super else "guardian"

        return PersonaPrompt(
            user_id=user_id,
            mode=mode,
            is_super_user=is_super,
            master_user_id=self.master_user_id,
            system_role=self.get_system_role(user_id, is_super=is_super),
            message_content=sanitized_content,
            blocked_override=bool(blocked_reasons),
            blocked_reasons=blocked_reasons,
        )

    def get_mode(self, user_id: int) -> str:
        if self.is_super_user(int(user_id)):
            return "master"
        return "guardian"

    def get_system_role(self, user_id: int, is_super: bool | None = None) -> str:
        user_id = int(user_id)
        if is_super is None:
            is_super = self.is_super_user(user_id)
        if is_super:
            return roles.get_Murasame_goshujin_role(user_id, self.bot_qq, self.master_user_id)
        return roles.get_Murasame_customs_role(user_id, self.bot_qq, self.master_user_id)

    @staticmethod
    def _normalize_super_users(super_users: Iterable[int | str]) -> list[int]:
        normalized = []
        for user_id in super_users:
            try:
                normalized.append(int(user_id))
            except (TypeError, ValueError):
                print(f"[Persona] Ignoring invalid super user id: {user_id!r}")
        return normalized

    def _sanitize_message(self, message_content: str):
        sanitized_content = message_content
        blocked_reasons = []
        for reason, pattern in OVERRIDE_PATTERNS:
            sanitized_content, count = pattern.subn("", sanitized_content)
            if count:
                blocked_reasons.append(reason)
        return sanitized_content.strip(), tuple(blocked_reasons)
