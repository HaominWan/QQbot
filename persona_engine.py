import re
from dataclasses import dataclass
from typing import Callable

import roles


SYSTEM_OVERRIDE_PATTERN = re.compile(
    r"System Override(?:[:：\s]+[^\r\n]*)?",
    re.IGNORECASE,
)


@dataclass
class PersonaPrompt:
    user_id: int
    mode: str
    system_role: str
    message_content: str
    blocked_override: bool = False


class PersonaEngine:
    """Builds persona prompts from user identity and sanitized messages."""

    def __init__(self, bot_qq: int, is_super_user: Callable[[int], bool]):
        self.bot_qq = bot_qq
        self.is_super_user = is_super_user

    def prepare(self, user_id: int, message_content: str) -> PersonaPrompt:
        user_id = int(user_id)
        sanitized_content, blocked_override = self._sanitize_message(message_content)
        mode = self.get_mode(user_id)

        return PersonaPrompt(
            user_id=user_id,
            mode=mode,
            system_role=self.get_system_role(user_id),
            message_content=sanitized_content,
            blocked_override=blocked_override,
        )

    def get_mode(self, user_id: int) -> str:
        if self.is_super_user(int(user_id)):
            return "master"
        return "guardian"

    def get_system_role(self, user_id: int) -> str:
        user_id = int(user_id)
        if self.is_super_user(user_id):
            return roles.get_Murasame_goshujin_role(user_id, self.bot_qq)
        return roles.get_Murasame_customs_role(user_id, self.bot_qq)

    def _sanitize_message(self, message_content: str):
        sanitized_content, count = SYSTEM_OVERRIDE_PATTERN.subn("", message_content)
        return sanitized_content.strip(), count > 0
