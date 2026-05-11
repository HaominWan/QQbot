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

    def _format_memory_context(self, relevant: str) -> str:
        if MEMORY_CONTEXT_MAX_CHARS > 0 and len(relevant) > MEMORY_CONTEXT_MAX_CHARS:
            relevant = relevant[:MEMORY_CONTEXT_MAX_CHARS].rstrip() + "\n...[truncated]"
        return (
            "\n\n[来自长期记忆的相关历史对话，仅供参考]\n"
            + relevant
            + "\n[历史记忆结束]"
        )

    async def handle_message(self, user_id, message_content, system_role, store_user=True):
        if self.memory and store_user:
            self.memory.store(self.group_id, user_id, message_content, "user")

        self.add_message("user", message_content, user_id)

        augmented_system = system_role
        tmp_chat_history = self.chat_history.copy()
        if self.memory:
            relevant = self.memory.search(self.group_id, message_content)
            if relevant:
                memory_context = self._format_memory_context(relevant)
                if MEMORY_CONTEXT_PLACEMENT == "system":
                    augmented_system += memory_context
                elif tmp_chat_history:
                    current_message = tmp_chat_history[-1].copy()
                    current_message["content"] = current_message["content"] + memory_context
                    tmp_chat_history[-1] = current_message

        tmp_chat_history.insert(0, {"role": "system", "content": augmented_system})
        gpt_response = await call_llm_api(tmp_chat_history)

        if self.memory:
            self.memory.store(self.group_id, None, gpt_response, "assistant")
        self.add_message("assistant", gpt_response)

        return gpt_response
