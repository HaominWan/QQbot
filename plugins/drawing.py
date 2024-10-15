import aiohttp
import json
import traceback
import asyncio
import base64
from PIL import Image
from io import BytesIO

from config import *
from api import *
from aiohttp import ClientTimeout

async def save_image_and_convert_to_base64(raw_message):
    try:
        # 调用 generate 方法并设置 url_ = True
        image_url = await generate(raw_message, url_=True)
        
        if not image_url:
            # 下载图片并转换为 base64 编码
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    image_data = await response.read()
                    
                    if not image_data:
                        raise Exception("Failed to download image data")
                    
                    # 验证图像数据是否有效
                    try:
                        Image.open(BytesIO(image_data))
                    except Exception:
                        raise Exception("Invalid image data")
                    
                    base64_encoded_image = base64.b64encode(image_data).decode('utf-8')
        
        # 下载图片并转换为 base64 编码
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                image_data = await response.read()
                base64_encoded_image = base64.b64encode(image_data).decode('utf-8')
        
        return base64_encoded_image
    except Exception as e:
        traceback.print_exc()
        return None

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
        data["model"]="anythingV5_PrtRE.safetensors [893e49b9]" if not XL else "cuteyukimixAdorable_midchapter3.safetensors [04bdffe6]" #cuteyukimixAdorable_midchapter3.safetensors [04bdffe6] pastelMixStylizedAnime_pruned_fp16.safetensors [793a26e8] anythingV5_PrtRE.safetensors [893e49b9]
    if("steps" not in data):
        data["steps"]=30
    if("style_preset" not in data):
        data["style_preset"] = "enhance"
    if("sampler" not in data):
        data["sampler"] = "Euler a"
    
    try:
        response = []
        timeout = ClientTimeout(total=60)  # 设置超时时间为60秒
        max_retries = 3  # 最大重试次数
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=data) as response_:
                        response = await response_.text()
                break  # 如果请求成功，则跳出循环
            except aiohttp.ClientError as e:
                print(f"[Prodia]Request failed with error: {e}. Retrying...")
                if attempt == max_retries - 1:
                    raise e # 如果重试次数达到上限，则抛出异常
                
        try:
            output_json = json.loads(str(response))
        except json.JSONDecodeError:
            print("[Prodia] Invalid JSON response:", response)
            raise Exception("Invalid JSON response")

        if "status" not in output_json or "job" not in output_json:
            raise Exception("No output in response, check auth key")
        
        url = f"https://api.prodia.com/v1/job/{output_json['job']}"
        counter = 0
        while "imageUrl" not in output_json:
            print("[Prodia] Waiting for response...")
            await asyncio.sleep(5)
            counter += 1
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers2) as response_:
                    response = await response_.text()
            output_json = json.loads(str(response))

            if counter > 20:
                raise Exception("Timeout")

        if "imageUrl" not in output_json:
            raise Exception("No output in response, check auth key")
        
        output_url = output_json["imageUrl"]

        if url_:
            return output_url

        data_ = bytearray()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(output_url) as response_:
                data_ += await response_.content.read()
        return data_

    except Exception as e:
        traceback.print_exc()
        return None
    
async def handle_drawing_message(message_content):
    draw_data = message_content[6:].strip()
    image_base64 = await save_image_and_convert_to_base64(draw_data)
    image_cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"
    
    return image_cq_code

# [
#   "3Guofeng3_v34.safetensors [50f420de]",                     R
#   "absolutereality_V16.safetensors [37db0fc3]",               R
#   "absolutereality_v181.safetensors [3d9d4d2b]",              R
#   "amIReal_V41.safetensors [0a8a2e61]",                       R
#   "analog-diffusion-1.0.ckpt [9ca13f02]",                     R
#   "aniverse_v30.safetensors [579e6f85]",                      A
#   "anythingv3_0-pruned.ckpt [2700c435]",                      A
#   "anything-v4.5-pruned.ckpt [65745d25]",                     A
#   "anythingV5_PrtRE.safetensors [893e49b9]",                  A
#   "AOM3A3_orangemixs.safetensors [9600da17]",                 A
#   "blazing_drive_v10g.safetensors [ca1c1eab]",                A
#   "breakdomain_I2428.safetensors [43cc7d2f]",                 A
#   "breakdomain_M2150.safetensors [15f7afca]",                 A
#   "cetusMix_Version35.safetensors [de2f2560]",                A
#   "childrensStories_v13D.safetensors [9dfaabcb]",             C
#   "childrensStories_v1SemiReal.safetensors [a1c56dbb]",       C
#   "childrensStories_v1ToonAnime.safetensors [2ec7b88b]",      C
#   "Counterfeit_v30.safetensors [9e2a8f19]",                   A
#   "cuteyukimixAdorable_midchapter3.safetensors [04bdffe6]",   A(loli)
#   "cyberrealistic_v33.safetensors [82b0d085]",                A(cyber)
#   "dalcefo_v4.safetensors [425952fe]",                        A-R              
#   "deliberate_v2.safetensors [10ec4b29]",                     R      
#   "deliberate_v3.safetensors [afd9d2d4]",                     R
#   "dreamlike-anime-1.0.safetensors [4520e090]",               A
#   "dreamlike-diffusion-1.0.safetensors [5c9fd6e0]",           A
#   "dreamlike-photoreal-2.0.safetensors [fdcf65e7]",           R
#   "dreamshaper_6BakedVae.safetensors [114c8abb]",             A
#   "dreamshaper_7.safetensors [5cf5ae06]",                     R
#   "dreamshaper_8.safetensors [9d40847d]",                     R
#   "edgeOfRealism_eorV20.safetensors [3ed5de15]",              R
#   "EimisAnimeDiffusion_V1.ckpt [4f828a15]",                   A
#   "elldreths-vivid-mix.safetensors [342d9d26]",               R
#   "epicphotogasm_xPlusPlus.safetensors [1a8f6d35]",           R
#   "epicrealism_naturalSinRC1VAE.safetensors [90a4c676]",      R
#   "epicrealism_pureEvolutionV3.safetensors [42c8440c]",       R
#   "ICantBelieveItsNotPhotography_seco.safetensors [4e7a3dfd]", R
#   "indigoFurryMix_v75Hybrid.safetensors [91208cbb]",          F
#   "juggernaut_aftermath.safetensors [5e20c455]",              R
#   "lofi_v4.safetensors [ccc204d6]",                           R
#   "lyriel_v16.safetensors [68fceea2]",                        A-R
#   "majicmixRealistic_v4.safetensors [29d0de58]",              R
#   "mechamix_v10.safetensors [ee685731]",                      M
#   "meinamix_meinaV9.safetensors [2ec66ab0]",                  A
#   "meinamix_meinaV11.safetensors [b56ce717]",                 A
#   "neverendingDream_v122.safetensors [f964ceeb]",             R
#   "openjourney_V4.ckpt [ca2f377f]",                           A-R
#   "pastelMixStylizedAnime_pruned_fp16.safetensors [793a26e8]",    A(Super)
#   "portraitplus_V1.0.safetensors [1400e684]",                 R
#   "protogenx34.safetensors [5896f8d5]",                       R
#   "Realistic_Vision_V1.4-pruned-fp16.safetensors [8d21810b]", R
#   "Realistic_Vision_V2.0.safetensors [79587710]",             R
#   "Realistic_Vision_V4.0.safetensors [29a7afaa]",             R
#   "Realistic_Vision_V5.0.safetensors [614d1063]",             R
#   "Realistic_Vision_V5.1.safetensors [a0f13c83]",             R
#   "redshift_diffusion-V10.safetensors [1400e684]",            R
#   "revAnimated_v122.safetensors [3f4fefd9]",                  A-R
#   "rundiffusionFX25D_v10.safetensors [cd12b0ee]",             A-R
#   "rundiffusionFX_v10.safetensors [cd4e694d]",                R
#   "sdv1_4.ckpt [7460a6fa]",                                   (shit)
#   "v1-5-pruned-emaonly.safetensors [d7049739]",               (shit)
#   "v1-5-inpainting.safetensors [21c7ab71]",                   (shit)
#   "shoninsBeautiful_v10.safetensors [25d8c546]",              R
#   "theallys-mix-ii-churned.safetensors [5d9225a4]",           R(shit)
#   "timeless-1.0.ckpt [7c4971d4]",                             R               
#   "toonyou_beta6.safetensors [980f6b15]"                      A              
# ]