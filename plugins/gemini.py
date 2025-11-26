import google.generativeai as gai
from IPython.display import Markdown
from IPython.display import Image
import PIL.Image as pi
import io
import textwrap
import aiohttp
import asyncio
import os
import time

from config import *
from aiohttp import ClientTimeout

gai.configure(api_key=GEMINI_API_KEY)

def to_markdown(text):
  text = text.replace('•', '  *')
  return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

async def url_to_image(url):
    try:
        print(f"[Gemini]Fetching image from URL: {url}")
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image = await response.read()
                    print(f"[Gemini]Image fetched successfully, size: {len(image)} bytes")
                    return image
                else:
                    print(f"[Gemini]HTTP Error: {response.status}")
                    return None
    except asyncio.TimeoutError:
        print("[Gemini]Timeout while fetching image")
        return None
    except Exception as e:
        print(f"[Gemini]Error fetching image: {e}")
        return None

async def image_to_text(image):
    if image is None:
        return "Error: Unable to fetch image"
    
    try:
        print("[Gemini]Generating text from image...")
        model = gai.GenerativeModel('gemini-1.5-flash')
        
        # 添加超时控制
        response = await asyncio.wait_for(
            model.generate_content_async([
                "请用中文描述这张图片的内容，包括图片中的文字、物品、人物、场景等。",
                pi.open(io.BytesIO(image))
            ]),
            timeout=30.0
        )
        
        print(f"[Gemini]Generated text: {response.text[:100]}...")
        return response.text
        
    except asyncio.TimeoutError:
        print("[Gemini]Timeout while generating text from image")
        return "抱歉，图片处理超时，请稍后再试。"
    except Exception as e:
        print(f"[Gemini]Error processing image: {e}")
        return f"抱歉，图片处理出现错误：{str(e)}"
if __name__ == "__main__":
    pass