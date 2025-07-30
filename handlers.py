import asyncio
import bot
import os
import roles
import base64
import chardet
import requests

from openai import OpenAI
from models import *
from api import *
from config import *
from plugins import *
from command_handlers import CommandHandler, CommandType, MessageType
 
async def handle_image_message(message_url, message_content):
    message_content += ' </image>prompt: '
    for part in message_url:
        image_prompt = await gemini.image_to_text(await gemini.url_to_image(part))
        message_content += image_prompt
        message_content += " | "

async def handler_init(interfaces):
    global bot_interfaces, command_handler
    bot_interfaces = interfaces
    command_handler = CommandHandler(interfaces)
    
async def handler_release():
    pass


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
            message_image_url = []
            for part in message['message']:
                if part['type'] == 'image':
                    message_image_url.append(part['data']['file'])

            message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
            print(message_content)
            print(message["message"][0]["type"] == 'at')
            
            # 使用命令处理器处理命令
            command_type = command_handler.get_command_type(message_content)
            if command_type:
                await command_handler.handle_command(
                    ws, MessageType.GROUP, command_type, message_content,
                    group_id=group_id, user_id=user_id, message_id=message_id
                )
                return

            elif message["message"][0]["type"] == "reply" and message["message"][2]["type"] == "at":
                if str(bot_interfaces["bot_qq"]) == message["message"][2]["data"]["qq"]:
                    print("enter ai mode")

                    reply_message = await bot_interfaces["get_message_by_id"](ws, message["message"][0]["data"]["id"])
                    reply_message_content = await bot_interfaces["encode_message_to_CQ"](reply_message['message'])
                    print(reply_message_content)

                    message_content = reply_message_content + message_content

                    if len(message_image_url) != 0:
                        await handle_image_message(message_image_url, message_content)
                    group = Group(group_id, bot_interfaces["bot_qq"])
                    gpt_response = await group.handle_message(user_id, message_content)
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
            elif message["message"][0]["type"] == "at":
                print(str(message['self_id']) == message["message"][0]["data"]["qq"])
                if str(bot_interfaces["bot_qq"]) == message["message"][0]["data"]["qq"]:
                    print("enter ai mode")

                    if len(message_image_url) != 0:
                        await handle_image_message(message_image_url, message_content)
                    group = Group(group_id, bot_interfaces["bot_qq"])
                    gpt_response = await group.handle_message(user_id, message_content)
                    return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
 
            return None
        if message["message_type"] == "private":
            user_id = message['user_id']
            message_id = message['message_id']
            message_image_url = []
            for part in message['message']:
                if part['type'] == 'image':
                    message_image_url.append(part['data']['file'])
            message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
            print(message_content)

            # 使用命令处理器处理命令
            command_type = command_handler.get_command_type(message_content)
            if command_type:
                await command_handler.handle_command(
                    ws, MessageType.PRIVATE, command_type, message_content,
                    user_id=user_id, message_id=message_id
                )
                return

            else:
                if len(message_image_url) != 0:
                    await handle_image_message(message_image_url, message_content)
                user = User(user_id, bot_interfaces["test_if_super_user"](user_id), bot_interfaces["bot_qq"])
                gpt_response = await user.handle_message(message_content)
                return await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))


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