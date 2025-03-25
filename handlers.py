import asyncio
import bot
import os
import roles
import base64
import chardet
import requests

from groq import Groq
from openai import OpenAI
from models import *
from api import *
from config import *
from plugins import *
 
async def handle_image_message(message_url, message_content):
    message_content += ' </image>prompt: '
    for part in message_url:
        image_prompt = await gemini.image_to_text(await gemini.url_to_image(part))
        message_content += image_prompt
        message_content += " | "

async def handler_init(interfaces):
    global bot_interfaces
    bot_interfaces = interfaces
    
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
            
            if message_content.startswith(".help"):
                help_message = '''========================
.help           插件信息
.reset          重置对话
.draw           AI绘图
.typ/.typst     Typst渲染
.md/.markdown   Markdown渲染
.YGO            查询卡片信息
.P5             预告信
========================'''
                await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](help_message))

            elif message_content.startswith(".reset"):
                group = Group(group_id, bot_interfaces["bot_qq"])
                if bot_interfaces["test_if_super_user"](user_id):
                    try:
                        group.chat_history = []
                        reset_message = "重置成功"
                        await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](reset_message))
                    except:
                        reset_message = "重置失败"
                        await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](reset_message))
                else:
                    reset_message = "抱歉，您没有权限重置对话"
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](reset_message))

            elif message_content.startswith(".draw"):
                image_cq_code = await drawing.handle_drawing_message(message_content)
                if image_cq_code == None:
                    image_cq_code = "抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"
                try:
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"))
                    
            elif message_content.startswith(".typ") or message_content.startswith(".typst"):
                image_cq_code = await typst_renderer.handle_typst_message(message_content)
                try:
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供Typst渲染服务，请尝试使用其他指令。"))

            elif message_content.startswith(".md") or message_content.startswith('.markdown'):
                image_cq_code = await markdown.handle_markdown_message(message_content)
                try: 
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_group_message"](ws, group_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供Markdown渲染服务，请尝试使用其他指令。"))  

            elif message_content.startswith(".YGO"):
                card_info = await YGO_find_card.get_card_info(message_content[5:])
                try:
                    await bot_interfaces["send_group_message"](ws, group_id, card_info)
                except:
                    await bot_interfaces["send_group_message"](ws, group_id, "抱歉，未找到相关卡片信息。")
                    
            elif message_content.startswith(".P5") or message_content.startswith(".p5"):
                card_image = await P5_card.get_card(message_content[4:])
                try:
                    await bot_interfaces["send_group_message"](ws, group_id, card_image)
                except:
                    await bot_interfaces["send_group_message"](ws, group_id, "怪盗团有点繁忙")

            elif message_content.startswith(".jm") or message_content.startswith(".JM"):
                jm_pdf = await jm2pdf.get_pdf(message_content[4:])
                if jm_pdf == 0:
                    await bot_interfaces["send_group_message"](ws, group_id, "抱歉，未找到相关本子信息。")
                else:
                    try:
                        await bot_interfaces["upload_group_file"](group_id, jm_pdf, {message_content[4:] + ".pdf"}, "jm")
                        await bot_interfaces["send_group_message"](ws, group_id, "少🦌点哟。")
                        
                    except:
                        await bot_interfaces["send_group_message"](ws, group_id, "抱歉，查询功能暂时无法提供服务，请尝试使用其他指令。")
                    finally:
                        os.remove(jm_pdf)
                        os.rmdir(f"Bot/tmp/{message_content[4:]}")

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

            if message_content.startswith(".help"):
                help_message = '''========================
.help           插件信息
.reset          重置对话
.draw           AI绘图
.typ/.typst     Typst渲染
.md/.markdown   Markdown渲染
.YGO            查询卡片信息
.P5             预告信
========================'''
                await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](help_message))
                
            elif message_content.startswith(".reset"):
                user = User(user_id, bot_interfaces["test_if_super_user"](user_id), bot_interfaces["bot_qq"])
                try:
                    user.chat_history = []
                    reset_message = "重置成功"
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](reset_message))
                except:
                    reset_message = "重置失败"
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](reset_message))
                pass
            elif message_content.startswith(".draw"):
                image_cq_code = await drawing.handle_drawing_message(message_content)
                try:
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"))
                    
            elif message_content.startswith(".typ") or message_content.startswith(".typst"):
                image_cq_code = await typst_renderer.handle_typst_message(message_content)               
                try:
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供Typst渲染服务，请尝试使用其他指令。"))
            elif message_content.startswith(".md") or message_content.startswith('.markdown'):
                image_cq_code = await markdown.handle_markdown_message(message_content)
                try: 
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"](image_cq_code))
                except:
                    await bot_interfaces["send_private_message"](ws, user_id, await bot_interfaces["decode_CQ_to_message"]("抱歉，目前无法为您提供Markdown渲染服务，请尝试使用其他指令。"))
            elif message_content.startswith(".YGO"):
                card_info = await YGO_find_card.get_card_info(message_content[5:])
                try:
                    await bot_interfaces["send_private_message"](ws, user_id, card_info)
                except:
                    await bot_interfaces["send_private_message"](ws, user_id, "抱歉，未找到相关卡片信息。")  
            elif message_content.startswith(".P5"):
                card_image = await P5_card.get_card(message_content[4:])
                try:
                    await bot_interfaces["send_private_message"](ws, user_id, card_image)
                except:
                    await bot_interfaces["send_private_message"](ws, user_id, "怪盗团有点繁忙")

            elif message_content.startswith(".jm") or message_content.startswith(".JM"):
                jm_pdf = await jm2pdf.get_pdf(message_content[4:])
                if jm_pdf == 0:
                    await bot_interfaces["send_private_message"](ws, user_id, "抱歉，未找到相关本子信息。")
                else:
                    try:
                        await bot_interfaces["upload_private_file"](user_id, jm_pdf, {message_content[4:] + ".pdf"})
                        await bot_interfaces["send_private_message"](ws, user_id, "少🦌点哟。")
                    except:
                        await bot_interfaces["send_private_message"](ws, user_id, "抱歉，查询功能暂时无法提供服务，请尝试使用其他指令。")
                    finally:
                        os.remove(jm_pdf)
                        os.rmdir(f"Bot/tmp/{message_content[4:]}")

            else:
                if len(message_image_url) != 0:
                    await handle_image_message(message_image_url, message_content)
                user = User(user_id, user_id in bot.super_users, bot_interfaces["bot_qq"])
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