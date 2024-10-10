from aiocqhttp import CQHttp, Event
from gpt import get_gpt_response
from drawing import generate_image

user_states = {}

async def handle_help(event):
    return ".help: 查看帮助\n.draw: 画图\n@Murasame: 对话\n .draw: 生成图像"

async def handle_reset(event, user_id):
    user_states.pop(user_id, None)
    return "已重置"

async def handle_gpt(event, message):
    user_id = event.user_id
    prompt = message.repalce("@Murasame", "").strip()

    personality = user_states.get(user_id, {}).get("default", None)
    response = await get_gpt_response(prompt, personality)
    return response

async def handle_draw(event, message):
    description = message.replace(".draw", "").strip() 
    image_url = await generate_image(description)
    return f"绘画完成：{image_url}"