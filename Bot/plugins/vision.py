import aiohttp
import httpx
from aiohttp import ClientTimeout

from config import HF_TOKEN, PROXY_URL

_HF_API_URL = "https://router.huggingface.co/hf-inference/models/Salesforce/blip-image-captioning-large"


def _guess_mime(url: str) -> str:
    low = url.lower()
    if ".gif" in low:
        return "image/gif"
    if ".png" in low:
        return "image/png"
    if ".webp" in low:
        return "image/webp"
    return "image/jpeg"


async def fetch_image(url: str) -> bytes | None:
    """Download image bytes from URL (QQ CDN is domestic, no proxy needed)."""
    try:
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=15)) as sess:
            async with sess.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                print(f"[Vision] HTTP {resp.status} fetching image")
    except Exception as exc:
        print(f"[Vision] Failed to fetch image: {exc}")
    return None


async def describe_image(image_bytes: bytes, url: str = "") -> str:
    """Describe image content via HuggingFace BLIP captioning model."""
    if not HF_TOKEN:
        return "[未配置 HuggingFace Token (hf_token)，无法识别图片]"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/octet-stream",
    }

    try:
        client_kwargs: dict = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(_HF_API_URL, headers=headers, content=image_bytes)
            if resp.status_code == 503:
                return "[图片识别模型加载中，请稍后再试]"
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                caption = data[0].get("generated_text", "")
            else:
                caption = str(data)
            return f"[图片内容：{caption}]"
    except Exception as exc:
        print(f"[Vision] HuggingFace API error: {exc}")
        return f"[图片识别失败: {exc}]"


__all__ = ["fetch_image", "describe_image"]
