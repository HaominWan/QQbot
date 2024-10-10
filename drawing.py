import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def generate_image(description):
    response = openai.Image.create(prompt = description, n=1, size="1024x1024")
    return response["data"][0]["url"]