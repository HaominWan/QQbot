import asyncio
import glob
import html
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import jmcomic
from PIL import Image

_PLUGIN_DIR = Path(__file__).resolve().parent
_BOT_DIR = _PLUGIN_DIR.parent
_TMP_DIR = _BOT_DIR / "tmp"
_RECOMMEND_MARKERS = ("今日推荐", "今日推薦", "今天推荐", "今天推薦", "本日推荐", "本日推薦", "推荐", "推薦")


def _natural_key(path):
    parts = re.split(r"(\d+)", os.path.normpath(path).replace(os.sep, "/"))
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def _create_option():
    option_path = _PLUGIN_DIR / "option.yml"
    os.environ["JM_DIR"] = str(_BOT_DIR)
    return jmcomic.create_option_by_file(str(option_path))


async def get_pdf(code):
    temp_dir = _TMP_DIR / str(code)
    pdf_name = temp_dir / f"{code}.pdf"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Downloading JM album {code}...")

    option = _create_option()

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, jmcomic.download_album, code, option)
    except Exception as exc:
        print(f"[ERROR] Download failed: {exc}")
        import traceback

        traceback.print_exc()
        return 0

    image_files = sorted(
        glob.glob(str(temp_dir / "**" / "*.jpg"), recursive=True)
        + glob.glob(str(temp_dir / "**" / "*.png"), recursive=True),
        key=_natural_key,
    )

    if not image_files:
        print(f"[ERROR] No downloaded images found under {temp_dir}")
        return 0

    print(f"[INFO] Found {len(image_files)} images, building PDF...")

    images = []
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)
        except Exception as exc:
            print(f"[WARN] Skipping {img_path}: {exc}")

    if not images:
        print("[ERROR] No valid images available for PDF generation")
        return 0

    images[0].save(str(pdf_name), save_all=True, append_images=images[1:])
    for img in images:
        img.close()

    print(f"[SUCCESS] PDF generated: {pdf_name}")
    return str(pdf_name)


class _AlbumLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.albums: list[dict[str, str]] = []
        self._active_album: dict[str, str] | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() != "a":
            return

        attr_map = {key.lower(): value or "" for key, value in attrs}
        href = attr_map.get("href", "")
        match = re.search(r"/album/(\d+)", href)
        if match is None:
            return

        self._active_album = {
            "id": match.group(1),
            "title": attr_map.get("title") or attr_map.get("data-original-title") or "",
        }
        self._active_text = []

    def handle_data(self, data: str):
        if self._active_album is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str):
        if tag.lower() != "a" or self._active_album is None:
            return

        text_title = _clean_title(" ".join(self._active_text))
        attr_title = _clean_title(self._active_album.get("title", ""))
        album_id = self._active_album["id"]
        self.albums.append({"id": album_id, "title": attr_title or text_title})
        self._active_album = None
        self._active_text = []


def _clean_title(title: str) -> str:
    title = html.unescape(title or "")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"^(JM)?\d+\s*[-_:：]?\s*", "", title, flags=re.I)
    return title


def _response_to_html(response: Any) -> str:
    if isinstance(response, str):
        return response

    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text

    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore")

    html_text = getattr(response, "html", None)
    if isinstance(html_text, str):
        return html_text

    return str(response)


def _new_html_client(option):
    if hasattr(option, "new_jm_client"):
        for kwargs in ({"impl": "html"}, {}):
            try:
                return option.new_jm_client(**kwargs)
            except TypeError:
                continue

    if hasattr(jmcomic, "JmHtmlClient"):
        return jmcomic.JmHtmlClient(option)

    raise RuntimeError("当前 jmcomic 版本不支持 HTML 客户端")


def _fetch_home_html_sync() -> str:
    client = _new_html_client(_create_option())

    for path in ("/", "", "/?page=1"):
        try:
            if hasattr(client, "get_jm_html"):
                return _response_to_html(client.get_jm_html(path))
            if hasattr(client, "get_html"):
                return _response_to_html(client.get_html(path))
        except Exception as exc:
            print(f"[JM] Failed to fetch home page {path!r}: {exc}")

    raise RuntimeError("无法获取 JM 首页")


def _recommend_section(page_html: str) -> str:
    for marker in _RECOMMEND_MARKERS:
        index = page_html.find(marker)
        if index >= 0:
            return page_html[index:index + 60000]
    return page_html


def _parse_album_links(page_html: str, limit: int) -> list[dict[str, str]]:
    parser = _AlbumLinkParser()
    parser.feed(_recommend_section(page_html))

    seen: set[str] = set()
    recommendations: list[dict[str, str]] = []
    for album in parser.albums:
        album_id = album.get("id", "")
        if not album_id or album_id in seen:
            continue
        seen.add(album_id)
        recommendations.append(album)
        if len(recommendations) >= limit:
            break
    return recommendations


async def get_daily_recommendations(limit: int = 10) -> list[dict[str, str]]:
    limit = max(1, min(int(limit), 20))
    try:
        page_html = await asyncio.to_thread(_fetch_home_html_sync)
        return _parse_album_links(page_html, limit)
    except Exception as exc:
        print(f"[JM] Recommend failed: {exc}")
        return []
