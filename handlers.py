import asyncio
import gemini
import drawing
from config import *
import bot
import os
from openai import OpenAI
from groq import Groq
import roles
from models import *
from api import *


# class User:
#     def __init__(self, user_id, is_super_user, bot_qq):
#         self.user_id = user_id
#         self.is_super_user = is_super_user
#         self.chat_history = [
#             {
#                 "role": "system",
#                 "content": roles.get_Murasame_goshujin_role(user_id,bot_qq) if is_super_user else roles.get_Murasame_customs_role(user_id,bot_qq)
#             }
#         ]

#     def get_user_id(self):
#         return self.user_id
    
#     def get_is_super_user(self):
#         return self.is_super_user
    
#     def get_chat_history(self):
#         return self.chat_history

#     def add_message(self, role, content):
#         self.chat_history.append({"role": role, "content": content})

#     def get_chat_history(self):
#         return self.chat_history
    
#     async def handle_message(self, message_content):
#         self.add_message("user", message_content)
#         gpt_response = await call_groq_api(self.chat_history)
#         self.add_message("assistant", gpt_response)
#         return gpt_response
    
# class Group:
#     def __init__(self, group_id, bot_qq):
#         self.group_id = group_id
#         self.users = {}
#         self.chat_history = []
#         self.bot_qq = bot_qq
    
#     def add_message(self, role, message_content, user_id = None):
#         message_content = "by " + str(user_id) + ": " + message_content if user_id else message_content
#         self.chat_history.append({"role": role, "content": message_content})

#     def get_chat_history(self):
#         return self.chat_history
    
#     async def handle_message(self, user_id, message_content):
#         if user_id in bot.super_users:
#             system_role = roles.get_Murasame_goshujin_role(user_id, self.bot_qq)
#         else:
#             system_role = roles.get_Murasame_customs_role(user_id, self.bot_qq)
            
#         #self.add_message("system", system_role)

#         self.add_message("user", message_content, user_id)

#         tmp_chat_history = self.chat_history.copy()
#         tmp_chat_history.insert(0, {"role": "system", "content": system_role})
#         gpt_response = await call_groq_api(tmp_chat_history)

#         self.add_message("assistant", gpt_response)

#         return gpt_response
 
async def handler_init(interfaces):
    global bot_interfaces
    bot_interfaces = interfaces
    
async def handler_release():
    pass

# async def call_groq_api(chat_history):
#      try:
#         client = Groq(
#             api_key=GROQ_API_KEY,
#         )
        
#         response = client.chat.completions.create(
#             messages=chat_history,
#             model="llama-3.2-90b-text-preview",#llama-3.2-11b-text-preview llama-3.2-11b-vision-preview llama-3.2-90b-text-preview gemma2-9b-it llama-3.1.70b-versatile llama-3.2-90b-text-preview
#             temperature=1,
#             top_p=1,
#             stream=True,
#             stop=None,
#         )

#         full_response = ""
#         for chunk in response:
#             if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
#                 full_response += chunk.choices[0].delta.content
        
#         return full_response
     
#      except Exception as e:
#          error_message = f"Error calling Groq API: {str(e)}"
#          print(error_message)  # 打印日志
#          return "抱歉，我暂时无法处理你的请求。"
     
# async def call_chatgpt_api(chat_history):

#             OpenAI(api_key = OPENAI_API_KEY)
#             print(OPENAI_API_KEY)
#             try:
#                 client = OpenAI(
#                      organization="org-jwlTKLr5o8qaeGU1OL0xgt5a",
#                      project="proj_LKwx8mUG90NATGpm7Ub5TB9H"
#                 )

#                 response = client.chat.completions.create(
#                      model="gpt-3.5-turbo", 
#                      messages=chat_history,
#                     temperature=0.7,
#                 )
#                 print(response)
#                 return response["choices"][0]["message"]["content"]
            
#             except Exception as e:
#                 error_message = f"Error calling ChatGPT API: {str(e)}"
#                 print(error_message)  # 打印日志
#                 return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息

#启用群的列表
test_group = [100000003, 100000001, 1000000001, 100000002] #第二团体100000003 *100000001 西工大·赣1000000001 cs群( computer science 100000002
async def execute_function(ws, message):
    if message['post_type'] == 'meta_event':
        return
    print(message)
    if message['post_type'] == 'message':
        if message['message_type'] == 'group':
            group_id = message['group_id']
            if not (group_id in test_group):
                return
            user_id = message['user_id']
            message_id = message['message_id']
            message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
            print(message_content)
            print(message["message"][0]["type"] == 'at')

            if message["message"][0]["type"] == "reply" and message["message"][2]["type"] == "at":
                if str(bot_interfaces["bot_qq"]) == message["message"][2]["data"]["qq"]:
                    print("enter ai mode")

                    reply_message = await bot_interfaces["get_message_by_id"](ws, message["message"][0]["data"]["id"])
                    reply_message_content = await bot_interfaces["encode_message_to_CQ"](reply_message['message'])
                    print(reply_message_content)

                    message_content = reply_message_content + message_content

                    group = Group(group_id, bot_interfaces["bot_qq"])
                    gpt_response = await group.handle_message(user_id, message_content)
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            elif message["message"][0]["type"] == "at":
                print(str(message['self_id']) == message["message"][0]["data"]["qq"])
                if str(bot_interfaces["bot_qq"]) == message["message"][0]["data"]["qq"]:
                    print("enter ai mode")

                    group = Group(group_id, bot_interfaces["bot_qq"])
                    gpt_response = await group.handle_message(user_id, message_content)
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
                    # if user_id in bot.super_users:
                    #     if str(user_id) in chatgpt_contents_private:
                    #         chat_history = chatgpt_contents_private[str(user_id)]
                    #     else:
                    #         chat_history = []
                    #         chat_history.append(
                    #             {
                    #                 "role": "system", 
                    #                 "content": roles.get_Murasame_goshujin_role(user_id,bot_interfaces["bot_qq"])
                    #             }
                    #         )

                    #     chat_history.append({"role": "user", "content": message_content})
                    #     gpt_response = await call_groq_api(chat_history)
                    #     chat_history.append({"role": "assistant", "content": gpt_response})
                    #     chatgpt_contents_private[str(user_id)] = chat_history
                    #     return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
                        
                    # else:
                    # #获取当前群聊上下文
                    #     if group_id in chatgpt_contents_group:
                    #         chat_history = chatgpt_contents_group[group_id]
                    #     else:
                    #         chat_history = []
                    #         chat_history.append(
                    #                 {"role": "system", 
                    #                 "content": roles.get_Murasame_customs_role(user_id,bot_interfaces["bot_qq"])
                    #                 }
                    #             )
                    
                    #     #用户新消息加入历史对话
                    #     chat_history.append({"role": "user", "content": message_content})
                    #     #调用ChatGPT API
                    #     #gpt_response = await call_chatgpt_api(chat_history)
                    #     gpt_response = await call_groq_api(chat_history)
                    #     #将ChatGPT的回复加入历史
                    #     chat_history.append({"role": "assistant", "content": gpt_response})
                    #     #保存更新后的对话历史
                    #     chatgpt_contents_group[group_id] = chat_history
                    #     #将回复发送
                    #     return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            # return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](message_content)) 
            return None
        if message["message_type"] == "private":
            user_id = message['user_id']
            message_id = message['message_id']
            message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
            print(message_content)

            user = User(user_id, user_id in bot.super_users, bot_interfaces["bot_qq"])
            gpt_response = await user.handle_message(message_content)
            return await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
            
            # if str(user_id) in chatgpt_contents_private:
            #     print("01")
            #     chat_history = chatgpt_contents_private[str(user_id)]
            # else:
            #     print("02")
            #     chat_history = []
            #     if user_id in bot.super_users:
            #         system_role = roles.get_Murasame_goshujin_role(user_id,bot_interfaces["bot_qq"])
            #     else:
            #         system_role = roles.get_Murasame_customs_role(user_id,bot_interfaces["bot_qq"])
            #     chat_history.append(
            #             {"role": "system", 
            #             "content": system_role
            #             }
            #         )
                    
            # chat_history.append({"role": "user", "content": message_content})
            # gpt_response = await call_groq_api(chat_history)
            # chat_history.append({"role": "assistant", "content": gpt_response})
            # chatgpt_contents_private[str(user_id)] = chat_history
            # return await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

#消息格式示例 group    
# {   'message_type': 'group',
#     'sub_type': 'normal',
#     'message_id': 347984696, 
#     'group_id': 100000003, 
#     'user_id': 1000000002, 
#     'anonymous': None, 
#     'message': [{'type': 'at', 'data': {'qq': '2335937889', 'name': '@Murasame'}}, {'type': 'text', 'data': {'text': ' 1'}}], 
#     'raw_message': '[CQ:at,qq=2335937889,name=@Murasame] 1', 
#     'font': 0, 
#     'sender': {'user_id': 1000000002, 'nickname': '元气のNeko', 'card': '', 'sex': 'unknown', 'age': 0, 'area': '', 'level': '23', 'role': 'owner', 'title': ''}, 
#     'time': 1728579896, 
#     'self_id': 2335937889, 
#     'post_type': 'message'
# }

# {   'message_type': 'group', 
#     'sub_type': 'normal', 
#     'message_id': 1905954616, 
#     'group_id': 1000000001, 
#     'user_id': 1000000002, 
#     'anonymous': None, 
#     'message': [{'type': 'reply', 'data': {'id': '1905913175'}}, {'type': 'text', 'data': {'text': ' '}}, {'type': 'at', 'data': {'qq': '2335937889', 'name': '@吾辈丛雨'}}, {'type': 'text', 'data': {'text': ' '}}], 
#     'raw_message': '[CQ:reply,id=1905913175] [CQ:at,qq=2335937889,name=@吾辈丛 雨] ', 
#     'font': 0, 
#     'sender': {'user_id': 1000000002, 'nickname': '元气のNeko', 'card': '24投降喵', 'sex': 'unknown', 'age': 0, 'area': '', 'level': '100', 'role': 'admin', 'title': ''}, 
#     'time': 1728833824, 
#     'self_id': 2335937889, 
#     'post_type': 'message'
# }

# private
# {   'message_type': 'private', 
#     'sub_type': 'friend', 
#     'message_id': 10042167, 
#     'user_id': 1000000002, 
#     'message': [{'type': 'text', 'data': {'text': '你好'}}], 
#     'raw_message': '你好', 
#     'font': 0, 
#     'sender': {'user_id': 1000000002, 'nickname': '元气のNeko', 'sex': 'unknown'}, 
#     'target_id': 2335937889, 
#     'time': 1728646732, 
#     'self_id': 2335937889, 
#     'post_type': 'message'
#  }