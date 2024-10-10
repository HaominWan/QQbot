# gpt.py
import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def get_gpt_response(prompt, personality=None):
    # 定义性格、语气等
    if personality:
        system_message = f"Act as {personality['name']} who is {personality['tone']}, {personality['style']} and provides {personality['response']} responses."
    else:
        system_message = "Act as a helpful assistant."

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']
