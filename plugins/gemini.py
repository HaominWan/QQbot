import google.generativeai as gai
import PIL.Image as pi
import io
import aiohttp
import asyncio
import os
import time
import tempfile

from config import *
from aiohttp import ClientTimeout

gai.configure(api_key=GEMINI_API_KEY)

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

async def analyze_video(video_url):
    """
    使用 Gemini 分析视频内容
    """
    temp_video_path = None
    try:
        print(f"[Gemini] Fetching video from URL: {video_url}")
        
        # 下载视频
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=60)) as session:
            async with session.get(video_url) as response:
                if response.status != 200:
                    return "[视频下载失败]"
                video_data = await response.read()

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
            temp_video.write(video_data)
            temp_video_path = temp_video.name

        print("[Gemini] Uploading video to Gemini...")
        video_file = gai.upload_file(path=temp_video_path)
        
        # 等待视频处理完成
        while video_file.state.name == "PROCESSING":
            print('[Gemini] Waiting for video processing...')
            await asyncio.sleep(2)
            video_file = gai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            return "[视频处理失败]"

        print("[Gemini] Generating text from video...")
        model = gai.GenerativeModel('gemini-1.5-flash')
        
        response = await model.generate_content_async(
            [video_file, "请详细描述这个视频的内容，包括发生的事件、人物动作、声音（如果有）等。"],
            request_options={"timeout": 600}
        )
        
        print(f"[Gemini] Generated video description: {response.text[:100]}...")
        return f" [视频内容: {response.text}] "

    except Exception as e:
        print(f"[Gemini] Error processing video: {e}")
        return f" [视频分析错误: {str(e)}] "
    finally:
        # 清理临时文件
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)

if __name__ == "__main__":
    pass
