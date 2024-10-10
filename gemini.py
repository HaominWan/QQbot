import google.generativeai as gai
from IPython.display import Markdown
from IPython.display import Image
import PIL.Image as pi
import io
import textwrap

import config


gai.configure(api_key=config.GEMINI_API_KEY)

def to_markdown(text):
  text = text.replace('•', '  *')
  return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

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