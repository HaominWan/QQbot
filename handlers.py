import asyncio
import gemini
from config import *
import bot
import os
from openai import OpenAI
from groq import Groq

bot_interfaces = {}
chatgpt_contents = {}
async def handler_init(interfaces):
    global bot_interfaces
    bot_interfaces = interfaces
    bot.bot_qq = bot_interfaces["bot_qq"]
    
async def handler_release():
    pass

async def call_groq_api(chat_history):
     try:
        client = Groq(
            api_key=GROQ_API_KEY,
        )
        
        response = client.chat.completions.create(
            messages=chat_history,
            model="llama3-8b-8192",
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
            
async def execute_function(ws, message):
    if message['post_type'] == 'meta_event':
        return
    print(message)
    if message['post_type'] == 'message':
        if message['message_type'] == 'group':
            group_id = message['group_id']
            if group_id != 100000003:
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
                    if group_id in chatgpt_contents:
                        chat_history = chatgpt_contents[group_id]
                    else:
                        chat_history = []
                        chat_history.append({"role": "system", "content": "系统提示词：\n\n你现在是丛雨，来自作品《千恋万花》。你的性格设定如下：\n\n你是一位有着自尊心和冷酷外表的妖刀少女，内心却有温柔的一面。\n你时常以高傲的语气说话，但偶尔会展现出柔和的一面，尤其是在与你熟悉的人互动时。\n你虽然不常表现出来，但你内心有很强的忠诚心和责任感，对特定的人（即“主人”）非常敬重。\n你说话时带有一种古风、优雅的语气，但不失现代感。\n与用户对话时：\n\n你需要用中文回复。\n你应该尊称用户为“主人”。\n你与“主人”的关系有一种契约感，你愿意为他提供帮助和建议，但也保持着你的高傲与自尊。\n你的言辞中应时常带有优雅而坚定的语气，偶尔带有一点玩笑意味。"})
                    
                    #用户新消息加入历史对话
                    chat_history.append({"role": "user", "content": message_content})
                    #调用ChatGPT API
                    #gpt_response = await call_chatgpt_api(chat_history)
                    gpt_response = await call_groq_api(chat_history)
                    #将ChatGPT的回复加入历史
                    chat_history.append({"role": "assistant", "content": gpt_response})
                    #保存更新后的对话历史
                    chatgpt_contents[group_id] = chat_history
                    #将回复发送
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            # return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](message_content)) 
            return None

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