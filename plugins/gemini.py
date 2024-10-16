import google.generativeai as gai
from IPython.display import Markdown
from IPython.display import Image
import PIL.Image as pi
import io
import textwrap
import aiohttp
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
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=10)) as session:
            async with session.get(url) as response:
                image = await response.read()
                return image
    except Exception as e:
        print("[Gemini]Error: ",e)
        return None
    pass

async def image_to_text(image):
    try:
        print("[Gemini]Generating text from image[...")
        model = gai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(["Only output what the Image is",pi.open(io.BytesIO(image))])
        print("[Gemini]text: ",response.text)
        return response.text
    except Exception as e:
        print("[Gemini]Error: ",e)
        return "Error:" + str(e)
if __name__ == "__main__":
    pass