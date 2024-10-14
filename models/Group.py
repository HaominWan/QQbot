import bot
import roles
from api import *

class Group:
    def __init__(self, group_id, bot_qq):
        self.group_id = group_id
        self.users = {}
        self.chat_history = []
        self.bot_qq = bot_qq
    
    def add_message(self, role, message_content, user_id = None):
        message_content = "by " + str(user_id) + ": " + message_content if user_id else message_content
        self.chat_history.append({"role": role, "content": message_content})

    def get_chat_history(self):
        return self.chat_history
    
    async def handle_message(self, user_id, message_content):
        if user_id in bot.super_users:
            system_role = roles.get_Murasame_goshujin_role(user_id, self.bot_qq)
        else:
            system_role = roles.get_Murasame_customs_role(user_id, self.bot_qq)
            
        #self.add_message("system", system_role)

        self.add_message("user", message_content, user_id)

        tmp_chat_history = self.chat_history.copy()
        tmp_chat_history.insert(0, {"role": "system", "content": system_role})
        gpt_response = await call_groq_api(tmp_chat_history)

        self.add_message("assistant", gpt_response)

        return gpt_response