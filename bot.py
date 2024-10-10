from aiocqhttp import CQHttp, Event
from handlers import handle_help, handle_gpt, handle_draw, handle_reset

bot = CQHttp()

@bot.on_message
async def handle_message(event: Event):
    message =  event.message
    user_id = event.user_id
    
    if message.startswith(".help"):
        response = await handle_help(event)
        await bot.send(event, response)

    elif message.startwith(".reset"):
        response = await handle_reset(event, user_id)
        await bot.send(event, response)

    elif message.startswith("@murasame "):
        response = await handle_gpt(event, message)
        await bot.send(event, response)

    elif message.startswith(".draw"):
        response = await handle_draw(event, message)
        await bot.send(event, response)

if __name__ == "__main__":
    bot.run(host = "127.0.0.1", port = 8080)