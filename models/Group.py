from typing import Optional
from api import *


class Group:
    def __init__(self, group_id, bot_qq, memory=None, window_size: int = 30):
        self.group_id = group_id
        self.users = {}
        self.chat_history = []
        self.bot_qq = bot_qq
        self.memory = memory
        self._window_size = window_size

    def add_message(self, role, message_content, user_id=None):
        message_content = "by " + str(user_id) + ": " + message_content if user_id else message_content
        self.chat_history.append({"role": role, "content": message_content})
        if len(self.chat_history) > self._window_size:
            self.chat_history = self.chat_history[-self._window_size:]

    def get_chat_history(self):
        return self.chat_history

    async def handle_message(self, user_id, message_content, system_role, store_user=True):
        if self.memory and store_user:
            self.memory.store(self.group_id, user_id, message_content, "user")

        self.add_message("user", message_content, user_id)

        augmented_system = system_role
        if self.memory:
            relevant = self.memory.search(self.group_id, message_content)
            if relevant:
                augmented_system += (
                    "\n\n[来自长期记忆的相关历史对话，供参考]\n"
                    + relevant
                    + "\n[历史记忆结束]"
                )

        tmp_chat_history = self.chat_history.copy()
        tmp_chat_history.insert(0, {"role": "system", "content": augmented_system})
        gpt_response = await call_llm_api(tmp_chat_history)

        if self.memory:
            self.memory.store(self.group_id, None, gpt_response, "assistant")
        self.add_message("assistant", gpt_response)

        return gpt_response
