import base64
import io

import httpx
from PIL import Image

from config import HF_TOKEN, PROXY_URL

_HF_API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"


async def handle_drawing_message(prompt: str) -> str:
    """Generate image from prompt via HuggingFace FLUX.1-schnell model."""
    if not prompt:
        return "[请提供绘图提示词，例如：.draw a cute cat]"
    if not HF_TOKEN:
        return "[未配置 HuggingFace Token (hf_token)，无法使用 AI 绘图]"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        client_kwargs: dict = {"timeout": 120.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(
                _HF_API_URL,
                headers=headers,
                json={"inputs": prompt},
            )
            if resp.status_code == 503:
                return "[绘图模型加载中，请稍后再试（通常需要 20 秒）]"
            resp.raise_for_status()
            image_bytes = resp.content

        img = Image.open(io.BytesIO(image_bytes))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"[CQ:image,file=base64://{b64}]"
    except Exception as exc:
        print(f"[Drawing] HuggingFace API error: {exc}")
        return f"[绘图失败: {exc}]"
