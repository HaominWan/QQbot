import requests
import roles
from groq import Groq
from config import *
from api import *

def generate(raw_message):

    prompt = call_groq_api(raw_message)

    url = "https://api.prodia.com/v1/sd/generate"

    payload = {
        "model": "v1-5-pruned-emaonly.safetensors [d7049739]",
        "prompt": prompt,
        "negative_prompt": "Bad quality",
        "style_preset": "anime",
        "steps": 20,
        "cfg_scale": 7,
        "seed": -1,
        "upscale": True,
        "sampler": "DPM++ 2M Karras",
        "width": 512,
        "height": 512
    }

    response = requests.post(url, json = payload, headers=headers)
    return response.json()

