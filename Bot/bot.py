import asyncio
import json
import logging
import websockets
import base64
import aiohttp
import time
import traceback
import os
import importlib
import requests
import errno

# TCP port-probe connections (e.g. from wait_port.ps1) trigger a harmless
# "opening handshake failed" warning — suppress it so logs stay clean.
logging.getLogger("websockets.server").setLevel(logging.ERROR)

from plugins import *
from config import HOST, PORT, PROXY_URL, SUPER_USERS

Host = HOST
Port = PORT
websocket_url = f"ws://{Host}:{Port}"

bot_qq = 0

super_users = SUPER_USERS

echo_counter = 0
echo_dict = {}
pending_echoes = set()
running_tasks = []

proxy_url = PROXY_URL

crash_signal = False
startup_notice_sent = False
ONEBOT_RESPONSE_TIMEOUT = 30.0


def _next_echo():
    global echo_counter
    echo_counter += 1
    self_echo = str(echo_counter)
    pending_echoes.add(self_echo)
    return self_echo


async def _wait_for_echo(self_echo, action_name, timeout=ONEBOT_RESPONSE_TIMEOUT):
    deadline = time.monotonic() + timeout
    try:
        while not crash_signal:
            response = echo_dict.pop(self_echo, None)
            if response is not None:
                return response
            if time.monotonic() >= deadline:
                print(f"[NapCat]Timeout waiting for {action_name} response, echo={self_echo}")
                return None
            await asyncio.sleep(0.1)
        return None
    finally:
        pending_echoes.discard(self_echo)
        echo_dict.pop(self_echo, None)


async def _send_onebot_action(ws, action, params, timeout=ONEBOT_RESPONSE_TIMEOUT):
    self_echo = _next_echo()
    try:
        await ws.send(
            json.dumps(
                {
                    "action": action,
                    "params": params,
                    "echo": self_echo,
                }
            )
        )
        response = await _wait_for_echo(self_echo, action, timeout=timeout)
        print("[NapCat]Response:", response)
        return response
    except Exception:
        pending_echoes.discard(self_echo)
        echo_dict.pop(self_echo, None)
        raise


def test_if_super_user(user_id):
    try:
        normalized_user_id = int(user_id)
    except (TypeError, ValueError):
        print(f"[Debug] Invalid super user id value: {user_id!r}")
        return False

    print(f"[Debug] Checking super user status for {normalized_user_id}, super_users list: {super_users}")
    result = normalized_user_id in super_users
    print(f"[Debug] Super user check result: {result}")
    return result

async def get_message_by_id(ws, message_id):
    response = await _send_onebot_action(ws, "get_msg", {"message_id": message_id})
    if response is None:
        return None
    if "data" in response:
        return response["data"]
    return None

async def get_stranger_info(ws, user_id):
    response = await _send_onebot_action(ws, "get_stranger_info", {"user_id": user_id})
    if response is None:
        return None
    if "data" in response:
        return response["data"]
    return None

async def send_group_message(ws, group_id, message, auto_escape=False):
# async def send_group_message(ws_url: str, group_id: str, message, auto_escape: bool =False):
    print("[NapCat]Sending message:", message)
    response = await _send_onebot_action(
        ws,
        "send_group_msg",
        {
            "group_id": group_id,
            "message": message,
            "auto_escape": auto_escape,
        },
    )
    if response:
        if "status" in response:
            if response["status"] == "ok":
                print("[NapCat]Message sent successfully")
            else:
                print("[NapCat]Failed to send message")
        if "data" in response and response["data"] is not None and "message_id" in response["data"]:
            return response["data"]["message_id"]
    else:
        print("[NapCat]No response received or crash signal triggered")
    return None

async def send_private_message(ws, user_id, message, auto_escape=False):
    print("[NapCat]Sending message:", message)
    response = await _send_onebot_action(
        ws,
        "send_private_msg",
        {
            "user_id": user_id,
            "message": message,
            "auto_escape": auto_escape,
        },
    )
    if response:
        if "status" in response:
            if response["status"] == "ok":
                print("[NapCat]Message sent successfully")
            else:
                print("[NapCat]Failed to send message")
        if "data" in response and response["data"] is not None and "message_id" in response["data"]:
            return response["data"]["message_id"]
    else:
        print("[NapCat]No response received or crash signal triggered")
    return None

async def notify_super_users_bot_started(ws):
    global startup_notice_sent
    if startup_notice_sent:
        return
    startup_notice_sent = True

    if not super_users:
        print("[Startup] No super users configured, startup notice skipped.")
        return

    await asyncio.sleep(1)
    message = [{"type": "text", "data": {"text": "Bot已启用"}}]
    for user_id in super_users:
        try:
            await send_private_message(ws, user_id, message)
            print(f"[Startup] Startup notice sent to super user {user_id}.")
        except Exception as exc:
            print(f"[Startup] Failed to send startup notice to {user_id}: {exc}")

async def upload_group_file(ws, group_id, file, name, folder):
    # url = '/upload_group_file'

    # payload = json.dumps({
    #     "group_id": group_id,
    #     "file": file,
    #     "name": name,
    #     "folder": folder
    # })

    # headers = {
    #     'Content-Type': 'application/json'
    # }

    # response = requests.request("8080", url, headers=headers, data=payload)
    response = await _send_onebot_action(
        ws,
        "upload_group_file",
        {
            "group_id": group_id,
            "file": file,
            "name": name,
            "folder": folder,
        },
    )
    if response and "status" in response:
        if response["status"] == "ok":
            print("[NapCat]File uploaded successfully")
        else:
            print("[NapCat]Failed to upload file")
    return None


async def upload_private_file(ws, user_id, file, name):
    # url = "/upload_private_file"

    # payload = json.dumps({
        # "user_id": user_id,
        # "file": file,
        # "name": name
    # })

    # headers={
        # 'Content-Type': 'application/json',
    # }

    # response = requests.request("8080", url, headers=headers, data=payload)

    response = await _send_onebot_action(
        ws,
        "upload_private_file",
        {
            "user_id": user_id,
            "file": file,
            "name": name,
        },
    )
    if response and "status" in response:
        if response["status"] == "ok":
            print("[NapCat]File uploaded successfully")
        else:
            print("[NapCat]Failed to upload file")
    return None


async def withdraw_group_message(ws, message_id):
    if message_id == None:
        return None
    response = await _send_onebot_action(ws, "delete_msg", {"message_id": message_id})
    if response and "status" in response:
        if response["status"] == "ok":
            print("[NapCat]Message withdrawn successfully")
        else:
            print("[NapCat]Failed to withdraw message")
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
                cq_content = message[i + 1:j]
                if cq_content.startswith("CQ:"):
                    cq_parts = cq_content.split(",")
                    cq_type = cq_parts[0][3:]
                    cq_data = {}
                    for x in cq_parts[1:]:
                        try:
                            key, value = x.split("=", 1)
                        except:
                            key = x
                            value = ""
                        cq_data[key] = value
                    decoded_message.append({"type": cq_type, "data": cq_data})
                else:
                    # Not a CQ code, treat as plain text
                    decoded_message.append({"type": "text", "data": {"text": message[i:j + 1]}})
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
        "super_users": tuple(super_users),
        "bot_qq": bot_qq,
        "proxy_url": proxy_url,
        "upload_group_file": upload_group_file,
        "upload_private_file": upload_private_file,
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
    async def serve_forever(ws, path=None):
        loop = asyncio.get_event_loop()
        global handlers, bot_qq
        unexcepted_error_happened = False
        retry = 0
        print(f"[NapCat]NapCat connected from path: {path}")
        if handlers is None:
            await hot_reload("handlers")
        loop.create_task(notify_super_users_bot_started(ws))
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
                #print("[NapCat]Received message: ", response)
                if "self_id" in response and response["self_id"] != bot_qq:
                    bot_qq = response["self_id"]
                    print("[NapCat]Bot QQ:", bot_qq)
                    await hot_reload("handlers")

                if "status" in response and "echo" in response:
                    global echo_dict
                    response_echo = str(response["echo"])
                    if response_echo in pending_echoes:
                        echo_dict[response_echo] = response
                    else:
                        print(f"[NapCat]Ignoring late or unexpected echo response: {response_echo}")
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
            except websockets.exceptions.ConnectionClosed as e:
                print(f"[NapCat]Connection closed: {e}")
                break
            except Exception as e:
                traceback.print_exc()
                print("[NapCat]Failed to process message: ", str(e))
                await asyncio.sleep(5)
                retry += 1
                if retry > 5:
                    raise RuntimeError("[NapCat]ERROR, reconnecting")
                continue

    print(f"[NapCat]Starting reverse websocket server: {websocket_url}/onebot/v11/ws")
    async with websockets.serve(serve_forever, Host, int(Port)):
        await hot_reload("handlers")
        await asyncio.Future()
       
bot_workpath = os.path.join(os.path.dirname(__file__), "bot_workpath")


def _is_address_in_use(exc):
    if not isinstance(exc, OSError):
        return False
    if getattr(exc, "errno", None) in (errno.EADDRINUSE, 10048):
        return True
    return "address already in use" in str(exc).lower()

async def server():
    print("[NapCat]Starting server")
    #await hot_reload("handlers")
    while not server_close_signal:
        try:
            await serve()
        except Exception as e:
            if _is_address_in_use(e):
                print(f"[NapCat]Port {Host}:{Port} is already in use; another bot is probably running.")
                raise
            print("[NapCat]", traceback.format_exc())
            print("[NapCat]Error:", e)
            await asyncio.sleep(5)
            print("[NapCat]Reconnecting...")
            
if __name__ == "__main__":
    asyncio.run(server())
        
        
