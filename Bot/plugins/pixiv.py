import asyncio
import base64
import math
import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from config import (
    PIXIV_ALLOW_AI,
    PIXIV_ALLOW_R18,
    PIXIV_DEFAULT_COUNT,
    PIXIV_MAX_COUNT,
    PIXIV_MIN_BOOKMARKS,
    PIXIV_REFRESH_TOKEN,
    PIXIV_SAMPLE_POOL,
    PROXY_URL,
)

_USER_AGENT = (
    "PixivAndroidApp/5.0.234 "
    "(Android 11; Pixel 5)"
)
_IMAGE_HEADERS = {
    "Referer": "https://www.pixiv.net/",
    "User-Agent": _USER_AGENT,
}
_RECENT_BY_QUERY: dict[str, deque[int]] = defaultdict(lambda: deque(maxlen=40))
_RANDOM = random.SystemRandom()


@dataclass(frozen=True)
class PixivQuery:
    raw: str
    keyword: str
    count: int
    exact_id: int | None = None


def _text_seg(text: str) -> dict:
    return {"type": "text", "data": {"text": text}}


def _image_seg(file: str) -> dict:
    return {"type": "image", "data": {"file": file, "type": "show"}}


def _client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "timeout": httpx.Timeout(30.0, connect=10.0),
        "headers": _IMAGE_HEADERS,
    }
    if PROXY_URL:
        kwargs["proxy"] = PROXY_URL
    return kwargs


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "items"):
        return dict(value.items())
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _parse_query(message: str) -> PixivQuery:
    raw = message.strip()
    count = PIXIV_DEFAULT_COUNT

    def replace_count(match: re.Match[str]) -> str:
        nonlocal count
        count = int(match.group(1))
        return " "

    keyword = re.sub(r"(?:--count|-n)\s+(\d+)", replace_count, raw, flags=re.I).strip()
    keyword = re.sub(r"\s+", " ", keyword)
    count = max(1, min(count, PIXIV_MAX_COUNT))

    id_match = re.search(r"(?:pid|id|illust_id)?[:：#]?\s*(\d{5,12})$", keyword, flags=re.I)
    exact_id = int(id_match.group(1)) if id_match and keyword == id_match.group(0).strip() else None
    return PixivQuery(raw=raw, keyword=keyword, count=count, exact_id=exact_id)


def _require_pixiv_client():
    if not PIXIV_REFRESH_TOKEN:
        raise RuntimeError("未配置 Pixiv refresh_token")

    try:
        from pixivpy3 import AppPixivAPI
    except ImportError as exc:
        raise RuntimeError("缺少 pixivpy3 依赖，请先执行 pip install -r Bot/requirements.txt") from exc

    api = AppPixivAPI()
    if PROXY_URL:
        api.requests_kwargs.update({"proxies": {"http": PROXY_URL, "https": PROXY_URL}})
    api.set_accept_language("zh-cn")
    api.auth(refresh_token=PIXIV_REFRESH_TOKEN)
    return api


def _to_illusts(payload: Any) -> list[dict[str, Any]]:
    data = _json_dict(payload)
    return [_json_dict(item) for item in _json_list(data.get("illusts"))]


def _dedupe_illusts(illusts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for illust in illusts:
        illust_id = int(illust.get("id") or 0)
        if not illust_id or illust_id in seen:
            continue
        seen.add(illust_id)
        unique.append(illust)
    return unique


def _fetch_detail_sync(illust_id: int) -> list[dict[str, Any]]:
    api = _require_pixiv_client()
    payload = _json_dict(api.illust_detail(illust_id))
    illust = _json_dict(payload.get("illust"))
    return [illust] if illust else []


def _fetch_search_sync(keyword: str, pages: int = 4) -> list[dict[str, Any]]:
    api = _require_pixiv_client()
    illusts: list[dict[str, Any]] = []

    for target in ("partial_match_for_tags", "title_and_caption"):
        payload = api.search_illust(keyword, search_target=target, sort="date_desc")
        for _ in range(max(1, pages // 2)):
            illusts.extend(_to_illusts(payload))
            next_url = _json_dict(payload).get("next_url")
            if not next_url:
                break
            payload = api.search_illust(**api.parse_qs(next_url))

    user_payload = _json_dict(api.search_user(keyword))
    for preview in _json_list(user_payload.get("user_previews"))[:3]:
        preview = _json_dict(preview)
        illusts.extend(_json_dict(item) for item in _json_list(preview.get("illusts")))

        user = _json_dict(preview.get("user"))
        user_id = user.get("id")
        if not user_id:
            continue
        try:
            illusts.extend(_to_illusts(api.user_illusts(user_id)))
        except Exception as exc:
            print(f"[Pixiv] Failed to fetch user illusts for {user_id}: {exc}")

    return _dedupe_illusts(illusts)


def _fetch_ranking_sync(pages: int = 3) -> list[dict[str, Any]]:
    api = _require_pixiv_client()
    illusts: list[dict[str, Any]] = []
    payload = api.illust_ranking("day")
    for _ in range(pages):
        illusts.extend(_to_illusts(payload))
        next_url = _json_dict(payload).get("next_url")
        if not next_url:
            break
        payload = api.illust_ranking(**api.parse_qs(next_url))
    return _dedupe_illusts(illusts)


def _tag_names(illust: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for tag in _json_list(illust.get("tags")):
        tag = _json_dict(tag)
        name = str(tag.get("name") or "").strip()
        translated_raw = tag.get("translated_name")
        translated = ""
        if isinstance(translated_raw, str):
            translated = translated_raw.strip()
        elif translated_raw:
            translated = str(_json_dict(translated_raw).get("name") or "").strip()
        if name:
            names.append(name)
        if translated:
            names.append(translated)
    return names


def _passes_safety_filters(illust: dict[str, Any]) -> bool:
    if not illust or illust.get("visible") is False:
        return False
    if illust.get("type") == "ugoira":
        return False
    if not PIXIV_ALLOW_R18 and int(illust.get("x_restrict") or 0) > 0:
        return False
    if not PIXIV_ALLOW_AI and int(illust.get("illust_ai_type") or 0) == 2:
        return False
    return True


def _quality_score(illust: dict[str, Any]) -> float:
    bookmarks = int(illust.get("total_bookmarks") or 0)
    views = int(illust.get("total_view") or 0)
    width = int(illust.get("width") or 0)
    height = int(illust.get("height") or 0)
    page_count = int(illust.get("page_count") or 1)

    pixel_score = min((width * height) / 1_800_000, 2.5)
    bookmark_score = math.log10(bookmarks + 1) * 2.2
    view_score = math.log10(views + 1) * 0.35
    page_bonus = min(page_count - 1, 4) * 0.18
    return bookmark_score + view_score + pixel_score + page_bonus


def _select_illusts(illusts: list[dict[str, Any]], query_key: str, count: int) -> list[dict[str, Any]]:
    candidates = [item for item in illusts if _passes_safety_filters(item)]
    high_bookmark = [
        item for item in candidates
        if int(item.get("total_bookmarks") or 0) >= PIXIV_MIN_BOOKMARKS
    ]
    if high_bookmark:
        candidates = high_bookmark
    if not candidates:
        return []

    pool = sorted(candidates, key=_quality_score, reverse=True)[:PIXIV_SAMPLE_POOL]
    recent = _RECENT_BY_QUERY[query_key]
    chosen: list[dict[str, Any]] = []

    while pool and len(chosen) < count:
        fresh_pool = [item for item in pool if int(item.get("id") or 0) not in recent]
        sample_pool = fresh_pool or pool
        weights = [max(_quality_score(item), 0.1) ** 1.8 for item in sample_pool]
        item = _RANDOM.choices(sample_pool, weights=weights, k=1)[0]
        illust_id = int(item.get("id") or 0)
        chosen.append(item)
        recent.append(illust_id)
        pool = [candidate for candidate in pool if int(candidate.get("id") or 0) != illust_id]

    return chosen


def _image_url(illust: dict[str, Any]) -> str:
    meta_single = _json_dict(illust.get("meta_single_page"))
    original = meta_single.get("original_image_url")
    if original:
        return str(original)

    meta_pages = _json_list(illust.get("meta_pages"))
    if meta_pages:
        urls = _json_dict(_json_dict(meta_pages[0]).get("image_urls"))
        return str(urls.get("original") or urls.get("large") or "")

    urls = _json_dict(illust.get("image_urls"))
    return str(urls.get("large") or urls.get("medium") or urls.get("square_medium") or "")


async def _download_image_as_base64(image_url: str) -> str:
    async with httpx.AsyncClient(**_client_kwargs()) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()

    b64 = base64.b64encode(resp.content).decode("utf-8")
    return f"base64://{b64}"


async def _format_illust(illust: dict[str, Any]) -> list[dict[str, Any]]:
    illust_id = int(illust.get("id") or 0)
    title = str(illust.get("title") or "Untitled")
    user = _json_dict(illust.get("user"))
    author = str(user.get("name") or "unknown")
    bookmarks = int(illust.get("total_bookmarks") or 0)
    width = int(illust.get("width") or 0)
    height = int(illust.get("height") or 0)
    page_count = int(illust.get("page_count") or 1)
    tags = " / ".join(_tag_names(illust)[:6])
    page_url = f"https://www.pixiv.net/artworks/{illust_id}"

    lines = [
        f"{title}",
        f"作者：{author}",
        f"PID：{illust_id} | 收藏：{bookmarks} | 尺寸：{width}x{height} | 页数：{page_count}",
    ]
    if tags:
        lines.append(f"Tags：{tags}")
    lines.append(page_url)

    segments = [_text_seg("\n".join(lines))]
    url = _image_url(illust)
    if not url:
        segments.append(_text_seg("\n[没有可发送的图片地址]"))
        return segments

    try:
        segments.append(_image_seg(await _download_image_as_base64(url)))
    except Exception as exc:
        print(f"[Pixiv] Failed to download image {illust_id}: {exc}")
        segments.append(_text_seg(f"\n[图片下载失败，可打开链接查看：{page_url}]"))
    return segments


async def _build_response(illusts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not illusts:
        return [_text_seg("没有找到符合条件的 Pixiv 图片。可以试试换 tag，或降低 pixiv_settings.min_bookmarks。")]

    segments: list[dict[str, Any]] = []
    for index, illust in enumerate(illusts):
        if index > 0:
            segments.append(_text_seg("\n\n----------------\n\n"))
        segments.extend(await _format_illust(illust))
    return segments


async def handle_pixiv_message(message: str) -> list[dict[str, Any]]:
    query = _parse_query(message)
    if not query.keyword:
        return [_text_seg("请输入 PID、作者/作品名或 tag，例如：.pixiv 初音ミク -n 2")]

    parts = query.keyword.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else ""
    if subcommand in {"recommend", "rec", "daily", "ranking"}:
        return await handle_recommend_message(parts[1] if len(parts) > 1 else "")

    try:
        if query.exact_id is not None:
            fetched = await asyncio.to_thread(_fetch_detail_sync, query.exact_id)
            selected = _select_illusts(fetched, f"pid:{query.exact_id}", query.count)
        else:
            fetched = await asyncio.to_thread(_fetch_search_sync, query.keyword)
            selected = _select_illusts(fetched, query.keyword.lower(), query.count)
        return await _build_response(selected)
    except Exception as exc:
        print(f"[Pixiv] Query failed: {exc}")
        return [_text_seg(f"[Pixiv] 查询失败：{exc}")]


async def handle_recommend_message(message: str = "") -> list[dict[str, Any]]:
    query = _parse_query(message)
    count = query.count

    try:
        fetched = await asyncio.to_thread(_fetch_ranking_sync)
        selected = _select_illusts(fetched, "recommend:day", count)
        return await _build_response(selected)
    except Exception as exc:
        print(f"[Pixiv] Recommend failed: {exc}")
        return [_text_seg(f"[Pixiv] 每日推荐获取失败：{exc}")]
