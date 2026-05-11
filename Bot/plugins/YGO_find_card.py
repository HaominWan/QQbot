"""
游戏王查卡模块 —— 使用百鸽 API 查询中文卡片信息。
"""

import base64
from typing import Any

import httpx

from config import PROXY_URL

_API_BASE = "https://ygocdb.com/api/v0"
_IMAGE_BASE = "https://cdn.233.momobako.com/ygoimg/ygopro"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _text_seg(text: str) -> dict:
    return {"type": "text", "data": {"text": text}}


def _image_seg(url: str) -> dict:
    return {"type": "image", "data": {"file": url, "type": "show"}}


def _client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "timeout": httpx.Timeout(12.0, connect=8.0),
        "verify": False,
        "headers": {"User-Agent": _USER_AGENT},
    }
    return kwargs


def _make_client() -> httpx.AsyncClient:
    kwargs = _client_kwargs()
    if not PROXY_URL:
        return httpx.AsyncClient(**kwargs)

    try:
        return httpx.AsyncClient(**kwargs, proxy=PROXY_URL)
    except TypeError:
        return httpx.AsyncClient(**kwargs, proxies=PROXY_URL)


def _normalize_types(types: Any) -> str:
    if isinstance(types, dict):
        types = types.get("types", "")
    if isinstance(types, list):
        return " ".join(str(t).strip() for t in types if str(t).strip())
    if isinstance(types, str):
        return types.strip()
    return ""


def _card_name(card: dict[str, Any]) -> str:
    for key in ("cn_name", "sc_name", "md_name", "nwbbs_n", "en_name", "jp_name"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(card.get("id") or "未知卡片")


def _card_text(card: dict[str, Any]) -> str:
    text = card.get("text")
    if isinstance(text, dict):
        parts = [text.get("pdesc"), text.get("desc")]
        return "\n".join(str(part).strip() for part in parts if str(part).strip())

    text = text or card.get("desc") or card.get("pdesc") or ""
    return str(text).strip()


def _image_url(card: dict[str, Any]) -> str:
    card_id = card.get("id")
    if not card_id:
        return ""
    return f"{_IMAGE_BASE}/{card_id}.webp!half"


async def _download_image_as_base64(client: httpx.AsyncClient, image_url: str) -> str:
    try:
        resp = await client.get(image_url)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[YGO] Failed to download image {image_url}: {exc}")
        return image_url

    b64_data = base64.b64encode(resp.content).decode("utf-8")
    return f"base64://{b64_data}"


async def _search_cards(card_name: str) -> list[dict[str, Any]]:
    async with _make_client() as client:
        resp = await client.get(f"{_API_BASE}/", params={"search": card_name})
        resp.raise_for_status()
        payload = resp.json()

        cards = payload.get("result", [])
        if not isinstance(cards, list):
            return []

        return [card for card in cards if isinstance(card, dict)]


async def _format_cards(card_name: str) -> list:
    cards = await _search_cards(card_name)
    if not cards:
        return [_text_seg(f"未找到「{card_name}」相关卡片。")]

    segments: list = []
    async with _make_client() as client:
        for i, card in enumerate(cards[:5]):
            name = _card_name(card)
            types = _normalize_types(card.get("types") or card.get("text"))
            text = _card_text(card)

            lines = [f"【{name}】 {types}".rstrip()]
            if text:
                lines.append(text[:200] + ("..." if len(text) > 200 else ""))
            else:
                lines.append("暂无效果文本。")

            if i > 0:
                segments.append(_text_seg("\n\n─────────────────\n\n"))
            segments.append(_text_seg("\n".join(lines)))

            image_url = _image_url(card)
            if image_url:
                image_file = await _download_image_as_base64(client, image_url)
                segments.append(_image_seg(image_file))

    return segments


async def get_card_info(card_name: str) -> list:
    """
    Search for up to 5 YGO cards matching card_name.
    Returns a flat OneBot message segment list (text + image per card).
    """
    card_name = card_name.strip()
    if not card_name:
        return [_text_seg("请输入要查询的卡名，例如：.YGO 青眼白龙")]

    try:
        return await _format_cards(card_name)
    except Exception as exc:
        print(f"[YGO] API error: {exc}")
        return [_text_seg(f"[YGO] 查询失败：{exc}")]
