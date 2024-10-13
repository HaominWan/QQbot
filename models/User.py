import roles
from api import *

class User:
    def __init__(self, user_id, is_super_user, bot_qq):
        self.user_id = user_id
        self.is_super_user = is_super_user
        self.chat_history = [
            {
                "role": "system",
                "content": roles.get_Murasame_goshujin_role(user_id,bot_qq) if is_super_user else roles.get_Murasame_customs_role(user_id,bot_qq)
            }
        ]

    def get_user_id(self):
        return self.user_id
    
    def get_is_super_user(self):
        return self.is_super_user
    
    def get_chat_history(self):
        return self.chat_history

    def add_message(self, role, content):
        self.chat_history.append({"role": role, "content": content})

    def get_chat_history(self):
        return self.chat_history
    
    async def handle_message(self, message_content):
        self.add_message("user", message_content)
        gpt_response = await call_groq_api(self.chat_history)
        self.add_message("assistant", gpt_response)
        return gpt_response