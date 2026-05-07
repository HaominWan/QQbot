from typing import Callable, Dict

import roles
from models import Group, User


class SessionManager:
    """Owns conversation session lifecycle for private and group chats."""

    def __init__(self, bot_qq: int, is_super_user: Callable[[int], bool]):
        self.bot_qq = bot_qq
        self.is_super_user = is_super_user
        self.private_sessions: Dict[int, User] = {}
        self.group_sessions: Dict[int, Group] = {}

    def get_private_session(self, user_id: int) -> User:
        user_id = int(user_id)
        if user_id not in self.private_sessions:
            is_super = self.is_super_user(user_id)
            self.private_sessions[user_id] = User(user_id, is_super, self.bot_qq)
        return self.private_sessions[user_id]

    def get_group_session(self, group_id: int) -> Group:
        group_id = int(group_id)
        if group_id not in self.group_sessions:
            self.group_sessions[group_id] = Group(group_id, self.bot_qq)
        return self.group_sessions[group_id]

    def reset_private_session(self, user_id: int) -> bool:
        user_id = int(user_id)
        session = self.private_sessions.get(user_id)
        if session is None:
            return False

        session.chat_history = [
            {
                "role": "system",
                "content": self._default_private_role(user_id),
            }
        ]
        return True

    def reset_group_session(self, group_id: int) -> bool:
        group_id = int(group_id)
        session = self.get_group_session(group_id)
        session.chat_history = []
        return True

    def _default_private_role(self, user_id: int) -> str:
        if self.is_super_user(user_id):
            return roles.get_Murasame_goshujin_role(user_id, self.bot_qq)
        return roles.get_Murasame_customs_role(user_id, self.bot_qq)
