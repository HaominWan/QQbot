import asyncio
import json
import websockets 
import base64
import aiohttp
import time
import traceback
import os
import importlib

from plugins import *

Host = "127.0.0.1"
Port = "8080"
websocket_url = f"ws://{Host}:{Port}"

bot_qq = 0

super_users = [1000000002]

echo_counter = 0
echo_dict = {}
running_tasks = []

proxy = "http://127.0.0.1:7890"

crash_signal = False


def test_if_super_user(user_id):
    return user_id in super_users

async def get_message_by_id(ws:websockets.WebSocketClientProtocol, message_id):
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    json_data = {
        "action": "get_msg",
        "params": {
            "message_id": message_id
        },
        "echo": self_echo
    }
    await ws.send(json.dumps(json_data))

    while self_echo not in echo_dict and not crash_signal:
        await asyncio.sleep(0.1)
    response = echo_dict[self_echo]
    del echo_dict[self_echo]
    print("[Lagrange Core]Response:",response)
    if "data" in response:
        return response["data"]
    return None

async def get_stranger_info(ws:websockets.WebSocketClientProtocol, user_id):
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    json_data = {
        "action": "get_stranger_info",
        "params": {
            "user_id": user_id
        },
        "echo": self_echo
    }
    await ws.send(json.dumps(json_data))

    while self_echo not in echo_dict and not crash_signal:
        await asyncio.sleep(0.1)
    response = echo_dict[self_echo]
    del echo_dict[self_echo]
    print("[Lagrange Core]Response:",response)
    if "data" in response:
        return response["data"]
    return None

async def send_group_message(ws:websockets.WebSocketClientProtocol, group_id, message, auto_escape=False):
# async def send_group_message(ws_url: str, group_id: str, message, auto_escape: bool =False):
    print("[Lagrange Core]Sending message:", message)
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    json_data = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": message,
            "auto_escape": auto_escape
        },
        "echo": self_echo
    }
    
    # await ws.send(json.dumps(json_data))

    # while self_echo not in echo_dict and not crash_signal:
    #     await asyncio.sleep(0.1)

    # response = echo_dict.get(self_echo)
    # if response:
    #     del echo_dict[self_echo]
    #     print ("[Lagrange Core]Response:",response)
    #     if "status" in response:
    #         if response["status"] == "ok":
    #             print("[Lagrange Core]Message sent successfully")
    #         else:
    #             print("[Lagrange Core]Failed to send message")
    #     if response is None:
    #         return None
    #     if "data" in response and response["data"] != None and "message_id" in response["data"]:
    #         return response["data"]["message_id"]
    # else:
    #     print("[Lagrange Core]No response received or crash signal triggered")
    # return None

    async with aiohttp.ClientSession() as session:
        await ws.send(json.dumps(json_data))
        while self_echo not in echo_dict and not crash_signal:
            await asyncio.sleep(0.1)
        response = echo_dict.get(self_echo)
        if response:
            del echo_dict[self_echo]
            print("[Lagrange Core]Response:", response)
            if "status" in response:
                if response["status"] == "ok":
                    print("[Lagrange Core]Message sent successfully")
                else:
                    print("[Lagrange Core]Failed to send message")
            if response is None:
                return None
            if "data" in response and response["data"] is not None and "message_id" in response["data"]:
                return response["data"]["message_id"]
        else:
            print("[Lagrange Core]No response received or crash signal triggered")
        return None

async def send_private_message(ws:websockets.WebSocketClientProtocol, user_id, message, auto_escape=False):
    print("[Lagrange Core]Sending message:", message)
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    json_data = {
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": message,
            "auto_escape": auto_escape
        },
        "echo": self_echo
    }
    await ws.send(json.dumps(json_data))
    while self_echo not in echo_dict and not crash_signal:
        await asyncio.sleep(0.1)
    response = echo_dict.get(self_echo)
    if response:
        del echo_dict[self_echo]
        print ("[Lagrange Core]Response:",response)
        if "status" in response:
            if response["status"] == "ok":
                print("[Lagrange Core]Message sent successfully")
            else:
                print("[Lagrange Core]Failed to send message")
        if response == None:
            return None
        if "data" in response and response["data"] != None and "message_id" in response["data"]:
            return response["data"]["message_id"]
    else:
        print("[Lagrange Core]No response received or crash signal triggered")
    return None

async def withdraw_group_message(ws:websockets.WebSocketClientProtocol, message_id):
    if message_id == None:
        return None
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    json_data = {
        "action": "delete_msg",
        "params": {
            "message_id": message_id
        },
        "echo": self_echo
    }
    await ws.send(json.dumps(json_data))

    while self_echo not in echo_dict and not crash_signal:
        await asyncio.sleep(0.1)
    response = echo_dict[self_echo]
    del echo_dict[self_echo]
    print("[Lagrange Core]Response:",response)
    if "status" in response:
        if response["status"] == "ok":
            print("[Lagrange Core]Message withdrawn successfully")
        else:
            print("[Lagrange Core]Failed to withdraw message")
    return None

#把消息转化为CQ码
async def encode_message_to_CQ(message):
    encoded_message = ""
    for x in message:
        if x["type"] == "text":
            encoded_message += x["data"]["text"]
        else:
            encoded_message += f"[CQ:{x['type']},"
            for key, value in x["data"].items():
                if key != "type":
                    encoded_message += f"{key}={value},"
            encoded_message = encoded_message[:-1] + "]"
    return encoded_message

async def encode_message_to_CQ_without_At_self_and_Image(message):
    encoded_message = ""
    for x in message:
        if x["type"] == "text":
            encoded_message += x["data"]["text"]
        else:
            if x["type"] == "at" and x["data"]["qq"] == str(bot_qq):
                continue
            if x["type"] == "image":
                if "base64" in x["data"]:
                    img = x["data"]["base64"]
                    # decode
                    img = base64.b64decode(img)
                    tag = await gemini.image_to_text(img)
                    encoded_message += f" <Image:prompt=\"{tag}\"> "
                elif "url" in x["data"]:
                    url = x["data"]["url"]
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            img = await response.read()
                    tag = await gemini.image_to_text(img)
                    encoded_message += f" <Image:prompt=\"{tag}\"> "
                continue
            encoded_message += f"[CQ:{x['type']},"
            for key, value in x["data"].items():
                if key != "type":
                    encoded_message += f"{key}={value},"
            encoded_message = encoded_message[:-1] + "]"
    return encoded_message
async def decode_CQ_to_message(message):
    decoded_message = []
    i = 0
    while i < len(message):
        if message[i] == "[":
            j = i + 1
            while j < len(message) and message[j] != "]":
                j += 1
            if j < len(message):
                cq_message = message[i + 1:j]
                cq_message = cq_message.split(",")
                cq_type = cq_message[0]
                cq_data = {}
                for x in cq_message[1:]:
                    try:
                        key, value = x.split("=", 1)
                    except:
                        key = x
                        value = ""
                    cq_data[key] = value
                # remove "CQ:" prefix
                if cq_type.startswith("CQ:"):
                    cq_type = cq_type[3:]
                decoded_message.append({"type": cq_type, "data": cq_data})
                i = j + 1
            else:
                decoded_message.append({"type": "text", "data": {"text": str(message[i:])}})
                break
        else:
            j = i + 1
            while j < len(message) and message[j] != "[":
                j += 1
            decoded_message.append({"type": "text", "data": {"text": str(message[i:j])}})
            i = j
    return decoded_message

interfaces = None

def set_interfaces():
    global interfaces
    interfaces= {
        "get_message_by_id": get_message_by_id,
        "send_group_message": send_group_message,
        "send_private_message": send_private_message,
        "withdraw_group_message": withdraw_group_message,
        "get_stranger_info": get_stranger_info,
        "encode_message_to_CQ": encode_message_to_CQ,
        "encode_message_to_CQ_without_At_self_and_Image": encode_message_to_CQ_without_At_self_and_Image,
        "decode_CQ_to_message": decode_CQ_to_message,
        "test_if_super_user": test_if_super_user,
        "bot_qq": bot_qq,
        
    }


handlers = None
async def hot_reload(handler_file):
    set_interfaces()
    global handlers
    if hasattr(handler_file, "handler_release"): await handlers.handler_release()
    try:
        handlers = importlib.reload(handler_file)
    except:
        handlers = importlib.import_module(handler_file)
    if handlers == None: return
    if hasattr(handlers, "handler_init"): await handlers.handler_init(interfaces)
    return handlers
        
async def release_handlers():
    global handlers
    if handlers == None: return
    if hasattr(handlers, "handler_release"): await handlers.handler_release()
    handlers = None

server_close_signal = False
task_info = []
async def serve():
    async def serve_forever(ws):
        loop = asyncio.get_event_loop()
        global handlers
        unexcepted_error_happened = False
        retry = 0
        while not server_close_signal:
            try:
                if unexcepted_error_happened:
                    unexcepted_error_happened = False
                    global context_managers
                    # 向所有已操作的群聊发送错误信息
                    for group_id in context_managers.keys():
                        loop.create_task(send_group_message(ws, group_id, "Bot前端发生严重错误，所有任务已取消，如有需要请重新发送消息"))
                response = await ws.recv()
                
                response = json.loads(response)
                #print("[Lagrange Core]Received message: ", response)
                if "status" in response and "echo" in response:
                    global echo_dict
                    echo_dict[response["echo"]] = response
                    retry = 0
                    continue
                
                task = loop.create_task(handlers.execute_function(ws, response))
                task_info = {"task": task, "start_time": time.time(),"param":response,"ws":ws}
                running_tasks.append(task_info)
                def remove_task(task):
                    for idx in range(len(running_tasks)):
                        if running_tasks[idx]["task"] == task:
                            running_tasks.pop(idx)
                            break
                task.add_done_callback(remove_task)
                #await execute_function(websocket, response)
                retry = 0
            except Exception as e:
                traceback.print_exc()
                print("[Lagrange Core]Failed to process message: ", str(e))
                await asyncio.sleep(5)
                retry += 1
                if retry > 5:
                    raise RuntimeError("[Lagrange Core]ERROR, reconnecting")
                continue
        
    async with websockets.connect(websocket_url) as ws:
        # Get bot info (to get bot QQ)
        msg = {
            "type": "ping"
        }
        await ws.send(json.dumps(msg))
        response = await ws.recv()
        bot_info = json.loads(response)
        if "self_id" in bot_info:
            global bot_qq
            bot_qq = bot_info["self_id"]
            print("[Lagrange Core]Bot QQ:", bot_qq)
            print("[Lagrange Core]Connected to server")

        else:
            print("[Lagrange Core]Failed to connect to server")
            return
        
        await hot_reload("handlers")
        await serve_forever(ws)
       
bot_workpath = os.path.join(os.path.dirname(__file__), "bot_workpath")

async def server():
    print("[Lagrange Core]Starting server")
    #await hot_reload("handlers")
    while not server_close_signal:
        try:
            await serve()
        except Exception as e:
            print("[Lagrange Core]", traceback.format_exc())
            print("[Lagrange Core]Error:", e)
            await asyncio.sleep(5)
            print("[Lagrange Core]Reconnecting...")
            
if __name__ == "__main__":
    asyncio.run(server())
        
        