import asyncio
import gemini
from config import *
import bot
import openai

bot_interfaces = {}
chatgpt_contents = {}
async def handler_init(interfaces):
    global bot_interfaces
    bot_interfaces = interfaces
    
async def handler_release():
    pass
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
            print(f"self_id: {message['self_id']}, bot_qq: {bot.bot_qq}")

            if message["message"][0]["type"] == "at":
                print(f"self_id: {message['self_id']}, bot_qq: {bot.bot_qq}")  # 从bot模块访问最新的bot_qq
                if message['self_id'] == bot.bot_qq:
                    #获取当前群聊上下文
                    print("enter ai mode")
                    if group_id in chatgpt_contents:
                        chat_history = chatgpt_contents[group_id]
                    else:
                        chat_history = []
                    
                    #用户新消息加入历史对话
                    chat_history.append({"role": "user", "content": message_content})
                    #调用ChatGPT API
                    gpt_response = await call_chatgpt_api(chat_history)
                    #将ChatGPT的回复加入历史
                    chat_history.append({"role": "assistant", "content": gpt_response})
                    #保存更新后的对话历史
                    chatgpt_contents[group_id] = chat_history
                    #将回复发送
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))

            # return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](message_content)) 
            return None
            
        async def call_chatgpt_api(chat_history):

            openai.api_key = OPENAI_API_KEY
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    message=chat_history
                )
                print(response)
                return response["choices"][0]["message"]["content"]
            
            except Exception as e:
                error_message = f"Error calling ChatGPT API: {str(e)}"
                print(error_message)  # 打印日志，可以替换为实际的日志记录方式
                return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息
        
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