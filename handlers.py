import asyncio
import gemini
from config import *
import bot
import os
from openai import OpenAI
from groq import Groq
import roles

chatgpt_contents_group = {}
chatgpt_contents_private = {}
async def handler_init(interfaces):
    global bot_interfaces
    bot_interfaces = interfaces
    
async def handler_release():
    pass

async def call_groq_api(chat_history):
     try:
        client = Groq(
            api_key=GROQ_API_KEY,
        )
        
        response = client.chat.completions.create(
            messages=chat_history,
            model="llama-3.2-90b-text-preview",#llama-3.2-11b-text-preview llama-3.2-11b-vision-preview llama-3.2-90b-text-preview gemma2-9b-it llama-3.1.70b-versatile llama-3.2-90b-text-preview
            temperature=1,
            top_p=1,
            stream=True,
            stop=None,
        )

        full_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
        
        return full_response
     
     except Exception as e:
         error_message = f"Error calling Groq API: {str(e)}"
         print(error_message)  # 打印日志
         return "抱歉，我暂时无法处理你的请求。"
     
async def call_chatgpt_api(chat_history):

            OpenAI(api_key = OPENAI_API_KEY)
            print(OPENAI_API_KEY)
            try:
                client = OpenAI(
                     organization="org-jwlTKLr5o8qaeGU1OL0xgt5a",
                     project="proj_LKwx8mUG90NATGpm7Ub5TB9H"
                )

                response = client.chat.completions.create(
                     model="gpt-3.5-turbo", 
                     messages=chat_history,
                    temperature=0.7,
                )
                print(response)
                return response["choices"][0]["message"]["content"]
            
            except Exception as e:
                error_message = f"Error calling ChatGPT API: {str(e)}"
                print(error_message)  # 打印日志
                return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息

#启用群的列表
test_group = [100000003, 100000001, 1000000001] #第二团体100000003 *100000001 西工大·赣1000000001
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

            if message["message"][0]["type"] == "at":
                print(str(message['self_id']) == message["message"][0]["data"]["qq"])
                if str(message['self_id']) == message["message"][0]["data"]["qq"]:
                    #获取当前群聊上下文
                    print("enter ai mode")
                    if group_id in chatgpt_contents_group:
                        chat_history = chatgpt_contents_group[group_id]
                    else:
                        chat_history = []
                        if user_id in bot.super_users:
                            system_role = roles.Murasame_goshujin_role
                        else:
                            system_role = roles.Murasame_customs_role
                        chat_history.append(
                                {"role": "system", 
                                "content": system_role
                                }
                            )
                    
                    #用户新消息加入历史对话
                    chat_history.append({"role": "user", "content": message_content})
                    #调用ChatGPT API
                    #gpt_response = await call_chatgpt_api(chat_history)
                    gpt_response = await call_groq_api(chat_history)
                    #将ChatGPT的回复加入历史
                    chat_history.append({"role": "assistant", "content": gpt_response})
                    #保存更新后的对话历史
                    chatgpt_contents_group[group_id] = chat_history
                    #将回复发送
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            # return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](message_content)) 
            return None
        if message["post_type"] == "private":
            user_id = message['user_id']
            message_id = message['message_id']
            message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
            print(message_content)
            
            if user_id in chatgpt_contents_private:
                chat_history = chatgpt_contents_private[user_id]
                chat_history.append({"role": "user", "content": message_content})
                gpt_response = await call_chatgpt_api(chat_history)
                chat_history.append({"role": "assistant", "content": gpt_response})
                return await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            else:
                chat_history = []
                if user_id in bot.super_users:
                    chat_history.append(
                        {"role": "system", 
                        "content": roles.Murasame_goshujin_role
                        }
                    )
                else:
                    chat_history.append(
                        {"role": "system", 
                        "content": roles.Murasame_customs_role
                        }
                    )

#消息格式示例     
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