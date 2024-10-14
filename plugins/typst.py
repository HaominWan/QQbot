import typst
import sys
import os
import asyncio
import time

def render(typst_text:str)->str:
    if sys.platform == "win32":
        temp_file = 'tmp/' + str(time.time()) + '.typ'
        try:
            if not os.path.exists('tmp'):
                os.makedirs('tmp')
            with open(temp_file, 'w') as f:
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
    elif sys.platform == "linux":
        temp_file = '/dev/shm/typst_tmp_' + str(time.time()) + '.typ'
        try:
            if not os.path.exists('/dev/shm'):
                os.makedirs('/dev/shm')
            with open(temp_file, 'w') as f:
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