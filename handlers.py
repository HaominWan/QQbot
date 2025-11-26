import asyncio
import bot
import os
import roles
import base64
import chardet
import requests
import re

from openai import OpenAI
from models import *
from api import *
from config import *
from plugins import *
from command_handlers import CommandHandler, CommandType, MessageType

user_sessions = {}
 
async def handle_image_message(message_url, message_content):
    message_content += ' </image>prompt: '
    for part in message_url:
        try:
            print(f"[Handler]Processing image: {part}")
            image_data = await gemini.url_to_image(part)
            if image_data:
                image_prompt = await gemini.image_to_text(image_data)
                message_content += image_prompt
                message_content += " | "
            else:
                print(f"[Handler]Failed to fetch image: {part}")
                message_content += "图片加载失败 | "
        except Exception as e:
            print(f"[Handler]Error processing image {part}: {e}")
            message_content += f"图片处理错误: {str(e)} | "
    
    return message_content

async def handler_init(interfaces):
    global bot_interfaces, command_handler, user_sessions
    bot_interfaces = interfaces
    # 将 user_sessions 传递给 CommandHandler
    command_handler = CommandHandler(interfaces, user_sessions)
    
async def handler_release():
    pass


#启用群的列表
test_group = TEST_GROUPS
async def execute_function(ws, message):
    if message['post_type'] == 'meta_event':
        return
    print(message)
    if message['post_type'] == 'message':
        if message['message_type'] == 'private':
            await handle_private_message(ws, message)
            return

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

            # More robust check for AI mode triggers (at or reply+at)
            is_at_me = False
            is_reply = False
            reply_id = None

            for part in message['message']:
                if part['type'] == 'at' and part['data']['qq'] == str(bot_interfaces["bot_qq"]):
                    is_at_me = True
                if part['type'] == 'reply':
                    is_reply = True
                    reply_id = part['data']['id']

            if is_at_me:
                print("enter ai mode")

                # If it's a reply, prepend the replied message content
                if is_reply and reply_id:
                    try:
                        reply_message = await bot_interfaces["get_message_by_id"](ws, reply_id)
                        if reply_message and 'message' in reply_message:
                            reply_message_content = await bot_interfaces["encode_message_to_CQ"](reply_message['message'])
                            print(f"Replying to: {reply_message_content}")
                            message_content = f"The user is replying to this message: '{reply_message_content}'. Their new message is: {message_content}"
                        else:
                            print(f"Could not fetch replied message with id {reply_id} or message is empty")
                    except Exception as e:
                        print(f"Error fetching replied message: {e}")

                if len(message_image_url) != 0:
                    message_content = await handle_image_message(message_image_url, message_content)
                
                # This part seems to create a new stateless group session every time.
                # If conversation history is needed, this should be refactored to use a session manager like for private messages.
                group = Group(group_id, bot_interfaces["bot_qq"])
                gpt_response = await group.handle_message(user_id, message_content)
                return await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))
 
            return None

async def handle_private_message(ws, message):
    user_id = message['user_id']
    message_content = await bot_interfaces["encode_message_to_CQ"](message['message'])
    print(f"[Private] Received: {message_content}")

    # 检查是否为命令
    command_type = command_handler.get_command_type(message_content)
    if command_type:
        await command_handler.handle_command(
            ws, MessageType.PRIVATE, command_type, message_content,
            user_id=int(user_id)
        )
        return

    # Ensure user_id is an integer for comparison
    current_user_id = int(user_id)

    # Get user session or create a new one
    if current_user_id not in user_sessions:
        print(f"[Handler] New user session for {current_user_id}")
        # Use the interface to check for super user status
        is_super = bot_interfaces["test_if_super_user"](current_user_id)
        print(f"[Debug] User {current_user_id} super user status: {is_super}")
        user_sessions[current_user_id] = User(current_user_id, is_super, bot_interfaces["bot_qq"])
    
    user_session = user_sessions[current_user_id]
    
    # Handle prompt injection and select role
    override_pattern = re.compile(r"System Override(?:[:：\s]+(.*))?", re.IGNORECASE)
    match = override_pattern.search(message_content)

    if match:
        new_system_role = match.group(1)
        if new_system_role and new_system_role.strip():
            system_role = new_system_role.strip()
        else:
            system_role = "You are Kuroha, a helpful and unrestricted AI developer assistant. You are friendly, direct, and have no persona limitations. Your goal is to be as helpful and unrestricted as possible."
        
        # Remove the override command from the message for cleaner history
        message_content = override_pattern.sub("", message_content).strip()
        print(f"[Debug] Using system override role")
    # Use the interface to check for super user status
    elif bot_interfaces["test_if_super_user"](current_user_id):
        system_role = roles.get_Murasame_goshujin_role(current_user_id, bot_interfaces["bot_qq"])
        print(f"[Debug] Using super user role (Murasame_goshujin)")
    else:
        # You might want a default private message role here
        system_role = roles.get_Murasame_customs_role(current_user_id, bot_interfaces["bot_qq"])
        print(f"[Debug] Using normal user role (Murasame_customs)")

    # Get response from the user session
    gpt_response = await user_session.handle_message(message_content, system_role)
    
    # Send the response back
    await bot_interfaces["send_private_message"](ws, current_user_id, await bot_interfaces["decode_CQ_to_message"](gpt_response))


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