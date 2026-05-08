from google import genai
from google.genai import types
import PIL.Image as pi
import io
import aiohttp
import asyncio
import os
import tempfile

from config import *
from aiohttp import ClientTimeout

_client = genai.Client(api_key=GEMINI_API_KEY)
_MODEL = "gemini-2.0-flash"


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
        # Convert to JPEG bytes via PIL for a consistent format
        img = pi.open(io.BytesIO(image))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        response = await asyncio.wait_for(
            _client.aio.models.generate_content(
                model=_MODEL,
                contents=[
                    "请用中文描述这张图片的内容，包括图片中的文字、物品、人物、场景等。",
                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                ],
            ),
            timeout=30.0,
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
    temp_video_path = None
    try:
        print(f"[Gemini] Fetching video from URL: {video_url}")

        async with aiohttp.ClientSession(timeout=ClientTimeout(total=60)) as session:
            async with session.get(video_url) as response:
                if response.status != 200:
                    return "[视频下载失败]"
                video_data = await response.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_data)
            temp_video_path = tmp.name

        print("[Gemini] Uploading video to Gemini...")
        video_file = await _client.aio.files.upload(file=temp_video_path)

        while video_file.state.name == "PROCESSING":
            print("[Gemini] Waiting for video processing...")
            await asyncio.sleep(2)
            video_file = await _client.aio.files.get(name=video_file.name)

        if video_file.state.name == "FAILED":
            return "[视频处理失败]"

        print("[Gemini] Generating text from video...")
        response = await _client.aio.models.generate_content(
            model=_MODEL,
            contents=[
                video_file,
                "请详细描述这个视频的内容，包括发生的事件、人物动作、声音（如果有）等。",
            ],
        )

        print(f"[Gemini] Generated video description: {response.text[:100]}...")
        return f" [视频内容: {response.text}] "

    except Exception as e:
        print(f"[Gemini] Error processing video: {e}")
        return f" [视频分析错误: {str(e)}] "
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)


if __name__ == "__main__":
    pass
