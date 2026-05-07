import base64
import aiohttp
import httpx
from aiohttp import ClientTimeout

from config import OPENROUTER_API_KEY, PROXY_URL

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_VISION_MODEL = "google/gemini-2.0-flash-exp:free"
_PROMPT = (
    "请用中文简洁描述这张图片，"
    "包括文字内容、人物、场景、物品等关键信息。"
    "如果是表情包或截图请说明。"
)


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
    """Describe image content in Chinese via OpenRouter (Gemini 2.0 Flash)."""
    if not OPENROUTER_API_KEY:
        return "[未配置 OpenRouter API Key，无法识别图片]"

    mime = _guess_mime(url)
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": _VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        client_kwargs: dict = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(_OPENROUTER_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"[Vision] OpenRouter API error: {exc}")
        return f"[图片识别失败: {exc}]"


__all__ = ["fetch_image", "describe_image"]
