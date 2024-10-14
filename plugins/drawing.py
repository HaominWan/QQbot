import requests
import aiohttp
import json
import traceback
import asyncio

from config import *
from api import *

async def build_StableDiffusion_info(data:str):
    ret = {}
    Plain = True
    Backlash = False
    Type = "prompt"
    data_str = ""
    default_str=""
    for char in data:
        if(char == "\"" and not Backlash and Plain):
            Type="prompt"
            if(data_str==""):
                Plain = not Plain
                continue
            Backlash = False
            default_str += data_str
            Plain = not Plain
            data_str = ""
            continue
        if(char == "\"" and not Backlash and not Plain):
            Backlash = False
            try:
                ret.update({Type:float(data_str)})                
            except ValueError:
                ret.update({Type:data_str})
            Plain = not Plain
            data_str=""
            continue
        if(char == "\\" and not Backlash):
            Backlash = True
            continue
        if(char == "\\" and Backlash):
            data_str += "\\"
            Backlash = False
            continue
        if(char=="\"" and Backlash):
            data_str += "\""
            Backlash = False
            continue
        if(char==":" and not Plain):
            Type = data_str
            data_str = ""
            continue
        data_str += char
    default_str+=data_str
    ret.update({"prompt":default_str})
    return ret

async def generate(raw_message, auth:str = PRODIA_API_KEY, url_=False, XL = False)->bytes:

    tmp = "sdxl" if XL else "sd"
    url = f"https://api.prodia.com/v1/{tmp}/generate"

    headers = {
        "accept": "application/json",
        "X-Prodia-Key": auth,


        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://deepinfra.com',
        'Referer': 'https://deepinfra.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'X-Deepinfra-Source': 'web-embed',
        'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    headers2={
        "X-Prodia-Key": auth,
        "accept": "application/json"
    }

    data = await build_StableDiffusion_info(raw_message)
    if("prompt" not in data):
        data["prompt"]="girl,HD,UHD,64K,4K,8K Wallpaper,masterpiece,best quality:2,beautiful face"
    else:
        data["prompt"]+=",HD,UHD,64K,4K,masterpiece,best quality:2,highres,high detailed,high quality:2,high resolution:2,high definition:2,beautiful"
    if("negative_prompt" not in data):
        data["negative_prompt"]="FastNegativeV2,easynegative,nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, artist name,badly drawn,worst quality:2,normal quality:2,malformed:2,blurry:2,low quality:2,low resolution:2,low definition,ugly,watermark,blurry,malformed:2,dutch angle:2,black,gray,malformed hand:2,strange eye,error light,bad hand,bad body,malformed leg:2,censor, bar censor, mosaic censor, black skin, monochrome, white borders, multiple views,dutch angle,malformed leg:2"
    if("width" not in data):
        data["width"]=1280 if XL else 1024
    if("height" not in data):
        data["height"]=748 if XL else 640
    if("model" not in data):
        data["model"]="meinamix_meinaV11.safetensors [b56ce717]" if not XL else "animagineXLV3_v30.safetensors [75f2f05b]"
    if("steps" not in data):
        data["steps"]=30
    if("style_preset" not in data):
        data["style_preset"] = "enhance"
    if("sampler" not in data):
        data["sampler"] = "Euler a"
    try:
        response = []
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response_:
                response = await response_.text()
        #response = requests.post(url, headers=headers, json=data)
        try:
            output_json=json.loads(str(response))
        except json.JSONDecodeError:
            print("[Prodia]Invalid JSON response:",response)
            raise Exception("Invalid JSON response")
        if("status" not in output_json or "job" not in output_json):
            raise Exception("No output in response,check auth key")
        url = f"https://api.prodia.com/v1/job/{output_json['job']}"
        counter=0
        while("imageUrl" not in output_json):
            print("[Prodia]Waiting for response...")
            await asyncio.sleep(5)
            counter+=1
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers2) as response_:
                    response = await response_.text()
            #response = requests.get(url, headers=headers2)
            output_json=json.loads(str(response))
            if(counter>20):
                raise Exception("Timeout")
        if("imageUrl" not in output_json):
            raise Exception("No output in response,check auth key")
        output_url=output_json["imageUrl"]
        if(url_):
            return output_url
        data_ = bytearray()
        async with aiohttp.ClientSession() as session:
            async with session.get(output_url) as response_:
                data_ += await response_.content.read()
        return data_
    except Exception as e:
        traceback.print_exc()

        return None

