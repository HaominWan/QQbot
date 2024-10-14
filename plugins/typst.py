import sys
import os
import asyncio
import time
import typst

def render(typst_text:str)->str:
    typst_text = "#set page(width: auto, height: auto, margin: (x: 10pt, y: 10pt), page size: auto)\n" + typst_text
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

async def render_async(typst_text:str)->str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, render, typst_text)

__all__ = ['render', 'render_async']