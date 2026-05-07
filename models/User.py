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
    
    async def handle_message(self, message_content, system_role):
        print(f"[Debug] User.handle_message called with system_role length: {len(system_role)}")
        print(f"[Debug] System role preview: {system_role[:200]}...")
        
        self.add_message("user", message_content)
        
        # Create a temporary chat history with the provided system role
        tmp_chat_history = self.chat_history.copy()
        # Find and replace the system message
        for i, msg in enumerate(tmp_chat_history):
            if msg["role"] == "system":
                tmp_chat_history[i] = {"role": "system", "content": system_role}
                break
        else: # If no system message exists, add one
            tmp_chat_history.insert(0, {"role": "system", "content": system_role})

        gpt_response = await call_llm_api(tmp_chat_history)
        self.add_message("assistant", gpt_response)
        return gpt_response
