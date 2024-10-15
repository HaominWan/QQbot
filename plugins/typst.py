import sys
import os
import asyncio
import time
import typst
import chardet
import base64

def render(typst_text:str)->str:
    typst_text = "#set page(width: auto, height: auto, margin: (x: 10pt, y: 10pt))\n" + f"#par[{typst_text}]\n"
    if sys.platform == "win32" or sys.platform == "win64":
        temp_file = 'D:/QQbot/Bot/tmp/' + str(time.time()) + '.typ'
        try:
            if not os.path.exists('D:/QQbot/Bot/tmp'):
                os.makedirs('D:/QQbot/Bot/tmp/')
            with open(temp_file, 'w', encoding= 'utf-8') as f:
                f.write(typst_text)
        except Exception as e:
            os.remove(temp_file)
            print("[Typst Renderer] Error:", e)
            raise e
        
        try:
            img = typst.compile(temp_file, format='png')
            os.remove(temp_file)
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            print("[Typst Renderer] Error:", e)
            raise e
        return img
    elif sys.platform == "linux":
        temp_file = '/dev/shm/typst_tmp_' + str(time.time()) + '.typ'
        try:
            if not os.path.exists('/dev/shm'):
                os.makedirs('/dev/shm')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(typst_text)
        except Exception as e:
            os.remove(temp_file)
            print("[Typst Renderer] Error:", e)
            raise e
        
        try:
            img = typst.compile(temp_file, format='png')
            os.remove(temp_file)
        except Exception as e:
            os.remove(temp_file)
            print("[Typst Renderer] Error:", e)
            raise e
        return img
    else:
        raise Exception("[Typst Renderer] Unsupported platform")

async def render_async(typst_text: str) -> str:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, render, typst_text)
    if isinstance(result, list):
        result = ''.join(result)
    return result

async def handle_typst_message(message_content):
    typst_data = message_content[5:].strip() if message_content.startswith(".typ ") else message_content[7:].strip()
    detected_encoding = chardet.detect(typst_data.encode())['encoding']
    if detected_encoding != 'utf-8':
        typst_data = typst_data.encode(detected_encoding).decode('utf-8')
    image_data = await render_async(typst_data)
    image_base64 = base64.b64encode(image_data.encode('utf-8')).decode('utf-8')
    image_cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"

    return image_cq_code

__all__ = ['render', 'render_async']