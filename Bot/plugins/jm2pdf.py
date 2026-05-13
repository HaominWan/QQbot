import asyncio
import glob
import html
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import jmcomic
from PIL import Image

_PLUGIN_DIR = Path(__file__).resolve().parent
_BOT_DIR = _PLUGIN_DIR.parent
_TMP_DIR = _BOT_DIR / "tmp"
_RECOMMEND_MARKERS = (
    r"C\d+\s*(?:(?:&amp;)|(?:&#38;)|(?:&#x26;)|&|＆){1,2}\s*推荐本本",
    r"C\d+\s*(?:(?:&amp;)|(?:&#38;)|(?:&#x26;)|&|＆){1,2}\s*推薦本本",
)
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_IGNORE_TEXTS = {
    "更多",
    "更多...",
    "查看更多",
    "查看全部",
    "詳細",
    "详情",
    "下载",
    "收藏",
}
_CATEGORY_TITLES = {
    "同人",
    "单本",
    "單本",
    "短篇",
    "其他类",
    "其他類",
    "韩漫",
    "韓漫",
    "English Manga",
    "一般向韩漫",
    "一般向韓漫",
}


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


def _clean_title(title: str) -> str:
    title = html.unescape(title or "")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"^(JM)?\d+\s*[-_:：]?\s*", "", title, flags=re.I)
    return title


def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _decode_unicode_escapes(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    return re.sub(r"\\u([0-9a-fA-F]{4})", replace, text)


def _normalize_marker_text(text: str) -> str:
    text = html.unescape(_decode_unicode_escapes(text or ""))
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", "", text)
    return text.casefold()


def _is_c107_recommend_text(text: str) -> bool:
    normalized = _normalize_marker_text(text)
    return re.search(r"c\d+&{1,2}(?:推荐|推薦)本本", normalized) is not None


def _valid_title(title: str, album_id: str = "") -> bool:
    title = _clean_title(title)
    if not title or title in _IGNORE_TEXTS:
        return False
    if album_id and re.fullmatch(rf"(?:JM)?{re.escape(album_id)}", title, flags=re.I):
        return False
    if re.fullmatch(r"(?:JM)?\d+", title, flags=re.I):
        return False
    if len(title) > 220:
        return False
    return True


def _is_real_album_id(album_id: str) -> bool:
    # JM 首页会把分类入口也写成 /album/1 ... /album/7；真实本子编号不会这么短。
    return album_id.isdigit() and int(album_id) >= 10000


def _is_category_entry(album_id: str, title: str) -> bool:
    return not _is_real_album_id(album_id) or _clean_title(title) in _CATEGORY_TITLES


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw_tags = re.split(r"[,，/、\s]+", tags)
    elif isinstance(tags, (list, tuple, set)):
        raw_tags = [str(tag) for tag in tags]
    else:
        raw_tags = [str(tags)]

    result: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        tag = _clean_text(str(tag))
        if not tag or tag in _IGNORE_TEXTS or len(tag) > 40:
            continue
        if tag.lower() in seen:
            continue
        seen.add(tag.lower())
        result.append(tag)
        if len(result) >= 8:
            break
    return result


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


def _fetch_html_from_client(client: Any, path: str) -> str:
    if hasattr(client, "get_jm_html"):
        return _response_to_html(client.get_jm_html(path))
    if hasattr(client, "get_html"):
        return _response_to_html(client.get_html(path))
    raise RuntimeError("当前 jmcomic HTML 客户端不支持页面抓取")


def _fetch_home_html_sync() -> str:
    client = _new_html_client(_create_option())
    for path in ("/", "", "/?page=1"):
        try:
            return _fetch_html_from_client(client, path)
        except Exception as exc:
            print(f"[JM] Failed to fetch home page {path!r}: {exc}")

    raise RuntimeError("无法获取 JM 首页")


def _real_album_count(fragment: str) -> int:
    return sum(
        1
        for album_match in re.finditer(r"/album/(\d+)", fragment, flags=re.I)
        if _is_real_album_id(album_match.group(1))
    )


def _bounded_section(page_html: str, start: int) -> str:
    search_from = min(len(page_html), start + 20)
    next_section = re.search(
        r"(?:</section\b[^>]*>|<section\b[^>]*>|<h[1-6]\b[^>]*>|C\d+\s*(?:(?:&amp;)|&|＆){1,2})",
        page_html[search_from:],
        flags=re.I,
    )
    end = search_from + next_section.start() if next_section else min(len(page_html), start + 100000)
    return page_html[start:end]


def _html_from_element(element: Any) -> str:
    try:
        from lxml import html as lxml_html

        return lxml_html.tostring(element, encoding="unicode", method="html")
    except Exception:
        return ""


def _next_sibling_section(element: Any) -> str:
    fragments = [_html_from_element(element)]
    sibling = element.getnext()
    while sibling is not None:
        tag = str(getattr(sibling, "tag", "")).lower()
        if tag in {"section", *_HEADING_TAGS}:
            break
        fragments.append(_html_from_element(sibling))
        sibling = sibling.getnext()
    return "".join(fragments)


def _classes_of(element: Any) -> set[str]:
    classes = element.get("class", "") if hasattr(element, "get") else ""
    return {class_name.strip().lower() for class_name in str(classes).split() if class_name.strip()}


def _looks_like_heading_container(element: Any) -> bool:
    tag = str(getattr(element, "tag", "")).lower()
    classes = _classes_of(element)
    if tag in _HEADING_TAGS or "talk-title" in classes:
        return True
    return bool(element.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' talk-title ')]"))


def _row_following_heading_section(element: Any) -> str:
    """Homepage recommendation blocks are a heading row followed by an album row."""
    current = element
    depth = 0
    while current is not None and depth < 8:
        tag = str(getattr(current, "tag", "")).lower()
        classes = _classes_of(current)
        if tag == "div" and "row" in classes and _looks_like_heading_container(current):
            fragments = [_html_from_element(current)]
            sibling = current.getnext()
            while sibling is not None and len(fragments) < 5:
                if _looks_like_heading_container(sibling) and _real_album_count("".join(fragments)) > 0:
                    break
                fragments.append(_html_from_element(sibling))
                if _real_album_count("".join(fragments)) > 0:
                    break
                sibling = sibling.getnext()

            fragment = "".join(fragments)
            if _real_album_count(fragment) > 0:
                return fragment
        current = current.getparent()
        depth += 1
    return ""


def _recommend_section_by_dom(page_html: str, *, log_errors: bool = True) -> str:
    try:
        from lxml import html as lxml_html

        root = lxml_html.fromstring(page_html)
    except Exception as exc:
        if log_errors:
            print(f"[JM] Failed to parse home page DOM: {exc}")
        return ""

    candidates: list[tuple[int, str]] = []
    for element in root.iter():
        text = element.text_content()
        if not _is_c107_recommend_text(text):
            continue
        if any(_is_c107_recommend_text(child.text_content()) for child in element.iterdescendants()):
            continue

        tag = str(getattr(element, "tag", "")).lower()
        fragments = [
            (-5, _row_following_heading_section(element)),
            (0, _next_sibling_section(element)),
            (0, _html_from_element(element)),
        ]

        parent = element.getparent()
        depth = 0
        while parent is not None and depth < 3:
            fragments.append((depth + 1, _next_sibling_section(parent)))
            fragments.append((depth + 1, _html_from_element(parent)))
            parent = parent.getparent()
            depth += 1

        for depth, fragment in fragments:
            count = _real_album_count(fragment)
            if count <= 0:
                continue
            score = (
                min(count, 20)
                + (1000 if tag in _HEADING_TAGS else 0)
                - (depth * 100)
                - (len(fragment) // 5000)
            )
            candidates.append((score, fragment))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _recommend_section(page_html: str, *, log_missing: bool = True) -> str:
    page_html = _decode_unicode_escapes(page_html)
    dom_section = _recommend_section_by_dom(page_html, log_errors=log_missing)
    if dom_section:
        return dom_section

    candidates: list[tuple[int, int, str]] = []
    for marker in _RECOMMEND_MARKERS:
        for match in re.finditer(marker, page_html, flags=re.I):
            section = _bounded_section(page_html, match.start())
            real_album_count = _real_album_count(section)
            if real_album_count <= 0:
                continue

            heading_start = max(
                page_html.rfind("<h1", 0, match.start()),
                page_html.rfind("<h2", 0, match.start()),
                page_html.rfind("<h3", 0, match.start()),
                page_html.rfind("<h4", 0, match.start()),
                page_html.rfind("<h5", 0, match.start()),
                page_html.rfind("<h6", 0, match.start()),
            )
            link_start = page_html.rfind("<a", 0, match.start())
            is_heading = heading_start >= 0 and heading_start > link_start and match.start() - heading_start < 300
            score = real_album_count + (1000 if is_heading else 0)
            candidates.append((score, match.start(), section))

    if candidates:
        candidates.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return candidates[0][2]

    if log_missing:
        nearby_titles = re.findall(r">([^<>]*(?:C\d+|推荐|推薦)[^<>]*)<", page_html, flags=re.I)
        preview = " | ".join(_clean_text(title) for title in nearby_titles[:8] if _clean_text(title))
        print(f"[JM] Cxxx recommendation section marker not found. nearby titles: {preview or 'none'}")
    return ""


def _normalize_site_path(href: str) -> str:
    href = html.unescape(_decode_unicode_escapes(href or "")).strip()
    href = re.sub(r"^https?://[^/]+", "", href, flags=re.I)
    href = href.split("#", 1)[0]
    return href or "/"


def _recommend_promote_paths(page_html: str) -> list[str]:
    page_html = _decode_unicode_escapes(page_html)
    paths: list[str] = []
    seen: set[str] = set()
    marker_matches: list[re.Match[str]] = []
    for marker in _RECOMMEND_MARKERS:
        marker_matches.extend(re.finditer(marker, page_html, flags=re.I))

    for marker_match in sorted(marker_matches, key=lambda item: item.start()):
        window_start = max(0, marker_match.start() - 2500)
        window_end = min(len(page_html), marker_match.end() + 5000)
        window = page_html[window_start:window_end]
        for promote_match in re.finditer(r"href\s*=\s*([\"'])([^\"']*/promotes/\d+[^\"']*)\1", window, flags=re.I):
            path = _normalize_site_path(promote_match.group(2))
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def _redact_debug_text(text: str) -> str:
    text = re.sub(
        r"(<input\b[^>]*(?:password|passwd|username|login|email)[^>]*\bvalue\s*=\s*['\"])([^'\"]*)(['\"])",
        r"\1<redacted>\3",
        text,
        flags=re.I | re.S,
    )
    text = re.sub(
        r"(\b(?:password|passwd|token|cookie|authorization|email|username)\b\s*[:=]\s*['\"]?)([^'\"\s<>]+)",
        r"\1<redacted>",
        text,
        flags=re.I,
    )
    return text


def _debug_snippet(page_html: str, center: int, radius: int = 1200) -> str:
    start = max(0, center - radius)
    end = min(len(page_html), center + radius)
    snippet = page_html[start:end]
    snippet = _redact_debug_text(snippet)
    return f"[offset {start}:{end}]\n{snippet}"


def _recommend_marker_matches(page_html: str) -> list[re.Match[str]]:
    page_html = _decode_unicode_escapes(page_html)
    matches: list[re.Match[str]] = []
    for marker in _RECOMMEND_MARKERS:
        matches.extend(re.finditer(marker, page_html, flags=re.I))
    return sorted(matches, key=lambda item: item.start())


def _debug_nearby_matches(page_html: str) -> list[re.Match[str]]:
    page_html = _decode_unicode_escapes(page_html)
    return list(re.finditer(r"C\d+|推荐本本|推薦本本|promotes/\d+", page_html, flags=re.I))


def _album_ids_in_fragment(fragment: str, limit: int = 20) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"/album/(\d+)", fragment, flags=re.I):
        album_id = match.group(1)
        if album_id in seen or not _is_real_album_id(album_id):
            continue
        seen.add(album_id)
        ids.append(album_id)
        if len(ids) >= limit:
            break
    return ids


def _album_anchor_pattern(album_id: str) -> re.Pattern[str]:
    return re.compile(
        rf"<a\b(?=[^>]*href=[\"'][^\"']*/album/{re.escape(album_id)}(?:[/?#\"'][^\"']*)?)[^>]*>.*?</a>",
        flags=re.I | re.S,
    )


def _album_context(section: str, start: int, end: int) -> str:
    previous_album = None
    for previous_album in re.finditer(r"/album/\d+", section[:start], flags=re.I):
        pass
    next_album = re.search(r"/album/\d+", section[end:], flags=re.I)

    context_start = max(0, start - 600)
    if previous_album is not None:
        context_start = max(context_start, previous_album.end())
        last_card_close = max(
            section.rfind("</div>", previous_album.end(), start),
            section.rfind("</li>", previous_album.end(), start),
            section.rfind("</article>", previous_album.end(), start),
        )
        if last_card_close >= 0:
            context_start = max(context_start, last_card_close)

    context_end = min(len(section), end + 3000)
    if next_album is not None:
        context_end = min(context_end, end + next_album.start())
    return section[context_start:context_end]


def _attribute_candidates(fragment: str) -> list[str]:
    candidates: list[str] = []
    for attr in ("title", "alt", "data-title", "data-original-title", "aria-label"):
        pattern = rf"\b{attr}\s*=\s*([\"'])(.*?)\1"
        candidates.extend(match.group(2) for match in re.finditer(pattern, fragment, flags=re.I | re.S))
    return candidates


def _class_text_candidates(fragment: str) -> list[str]:
    candidates: list[str] = []
    pattern = re.compile(
        r"<(?P<tag>[a-z0-9]+)\b[^>]*(?:class|id)\s*=\s*([\"'])[^\"']*(?:title|name|caption|subject)[^\"']*\2[^>]*>(?P<body>.*?)</(?P=tag)>",
        flags=re.I | re.S,
    )
    for match in pattern.finditer(fragment):
        candidates.append(_clean_text(match.group("body")))
    return candidates


def _extract_title(album_id: str, anchor_html: str, context: str) -> str:
    candidates: list[str] = []
    candidates.extend(_attribute_candidates(anchor_html))
    candidates.append(_clean_text(anchor_html))
    candidates.extend(_attribute_candidates(context))
    candidates.extend(_class_text_candidates(context))

    for candidate in candidates:
        title = _clean_title(candidate)
        if _valid_title(title, album_id):
            return title
    return ""


def _extract_tags(context: str, title: str, album_id: str) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"<a\b[^>]*href\s*=\s*([\"'])[^\"']*(?:search|tag|tags|category|keyword|search_query)[^\"']*\1[^>]*>(.*?)</a>",
        r"<(?P<tag>[a-z0-9]+)\b[^>]*class\s*=\s*([\"'])[^\"']*(?:tag|tags|category|label)[^\"']*\2[^>]*>(?P<body>.*?)</(?P=tag)>",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, context, flags=re.I | re.S):
            body = match.group("body") if "body" in match.groupdict() else match.group(2)
            candidates.append(_clean_text(body))

    tags: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for tag in _normalize_tags(candidate):
            if tag == title or tag == album_id or tag in _IGNORE_TEXTS:
                continue
            if re.fullmatch(r"(?:JM)?\d+", tag, flags=re.I):
                continue
            tag_key = tag.lower()
            if tag_key in seen:
                continue
            seen.add(tag_key)
            tags.append(tag)
            if len(tags) >= 8:
                return tags
    return tags


def _parse_album_links(
    page_html: str,
    limit: int,
    *,
    allow_full_page: bool = False,
    log_missing: bool = True,
) -> list[dict[str, Any]]:
    section = _recommend_section(page_html, log_missing=log_missing and not allow_full_page)
    if not section and allow_full_page:
        section = _decode_unicode_escapes(page_html)
    seen: set[str] = set()
    recommendations: list[dict[str, Any]] = []
    for match in re.finditer(r"/album/(\d+)", section, flags=re.I):
        album_id = match.group(1)
        if album_id in seen:
            continue
        anchor_match = _album_anchor_pattern(album_id).search(
            section,
            max(0, match.start() - 1000),
            min(len(section), match.end() + 3000),
        )
        anchor_html = anchor_match.group(0) if anchor_match else ""
        context = _album_context(section, match.start(), match.end())
        title = _extract_title(album_id, anchor_html, context)
        if _is_category_entry(album_id, title):
            seen.add(album_id)
            continue

        seen.add(album_id)
        recommendations.append(
            {
                "id": album_id,
                "title": title,
                "tags": _extract_tags(context, title, album_id),
            }
        )
        if len(recommendations) >= limit:
            break
    return recommendations


def _detail_get(detail: Any, key: str, default: Any = None) -> Any:
    if isinstance(detail, dict):
        return detail.get(key, default)
    return getattr(detail, key, default)


def _fetch_album_detail(client: Any, album_id: str) -> Any:
    for method_name in ("get_album_detail", "album_detail", "get_album"):
        method = getattr(client, method_name, None)
        if method is None:
            continue
        return method(album_id)
    raise RuntimeError("当前 jmcomic HTML 客户端不支持 album detail")


def _enrich_album_details_sync(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    need_detail = [album for album in albums if not album.get("title") or not album.get("tags")]
    if not need_detail:
        return albums

    try:
        client = _new_html_client(_create_option())
    except Exception as exc:
        print(f"[JM] Failed to create detail client: {exc}")
        return albums

    for album in need_detail:
        album_id = str(album.get("id") or "")
        if not album_id:
            continue
        try:
            detail = _fetch_album_detail(client, album_id)
        except Exception as exc:
            print(f"[JM] Failed to fetch album detail {album_id}: {exc}")
            continue

        title = _clean_title(_detail_get(detail, "title", ""))
        if title and not album.get("title"):
            album["title"] = title

        tags = (
            _detail_get(detail, "tags", None)
            or _detail_get(detail, "tag_list", None)
            or _detail_get(detail, "category", None)
            or _detail_get(detail, "works", None)
        )
        if tags and not album.get("tags"):
            album["tags"] = _normalize_tags(tags)
    return albums


def _fetch_recommendation_source_sync() -> tuple[str, bool]:
    client = _new_html_client(_create_option())
    pending: list[tuple[str, bool]] = [("/", False), ("", False), ("/?page=1", False)]
    seen: set[tuple[str, bool]] = set()
    fallback_html = ""

    while pending:
        path, allow_full_page = pending.pop(0)
        key = (path, allow_full_page)
        if key in seen:
            continue
        seen.add(key)

        try:
            page_html = _fetch_html_from_client(client, path)
        except Exception as exc:
            print(f"[JM] Failed to fetch recommendation page {path!r}: {exc}")
            continue

        if not fallback_html:
            fallback_html = page_html

        albums = _parse_album_links(page_html, 1, allow_full_page=allow_full_page, log_missing=False)
        if albums:
            return page_html, allow_full_page

        if not allow_full_page:
            for promote_path in reversed(_recommend_promote_paths(page_html)):
                pending.insert(0, (promote_path, True))

    if fallback_html:
        return fallback_html, False

    raise RuntimeError("无法获取 JM 推荐页")


def _write_recommend_debug_log_sync(limit: int = 10) -> str:
    limit = max(1, min(int(limit), 20))
    debug_dir = _TMP_DIR / "jm_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    report_path = debug_dir / f"jm_recommend_debug_{datetime.now():%Y%m%d_%H%M%S}.txt"

    lines: list[str] = [
        "JM recommend debug report",
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"limit: {limit}",
        "",
    ]

    try:
        option = _create_option()
        client = _new_html_client(option)
        lines.append(f"client_type: {type(client).__module__}.{type(client).__name__}")
    except Exception as exc:
        lines.append(f"client_create_error: {type(exc).__name__}: {exc}")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return str(report_path)

    pending: list[tuple[str, bool]] = [("/", False), ("", False), ("/?page=1", False)]
    seen: set[tuple[str, bool]] = set()

    while pending:
        path, allow_full_page = pending.pop(0)
        key = (path, allow_full_page)
        if key in seen:
            continue
        seen.add(key)

        lines.extend(
            [
                "",
                "=" * 72,
                f"path: {path!r}",
                f"allow_full_page: {allow_full_page}",
            ]
        )

        try:
            page_html = _fetch_html_from_client(client, path)
        except Exception as exc:
            lines.append(f"fetch_error: {type(exc).__name__}: {exc}")
            continue

        page_html = _decode_unicode_escapes(page_html)
        lines.append(f"html_length: {len(page_html)}")

        marker_matches = _recommend_marker_matches(page_html)
        lines.append(f"recommend_marker_count: {len(marker_matches)}")
        for index, marker_match in enumerate(marker_matches[:5], start=1):
            lines.append(f"marker_{index}: {marker_match.group(0)!r} at {marker_match.start()}")
            lines.append(_debug_snippet(page_html, marker_match.start(), radius=900))

        promote_paths = _recommend_promote_paths(page_html)
        lines.append(f"recommend_promote_paths: {promote_paths or []}")

        section = _recommend_section(page_html, log_missing=False)
        lines.append(f"recommend_section_length: {len(section)}")
        lines.append(f"recommend_section_album_ids: {_album_ids_in_fragment(section)}")

        parsed_normal = _parse_album_links(page_html, limit, log_missing=False)
        parsed_full = _parse_album_links(page_html, limit, allow_full_page=True, log_missing=False)
        lines.append(f"parsed_normal_ids: {[album.get('id') for album in parsed_normal]}")
        lines.append(f"parsed_full_page_ids: {[album.get('id') for album in parsed_full]}")

        if not marker_matches:
            nearby_matches = _debug_nearby_matches(page_html)
            lines.append(f"nearby_keyword_count: {len(nearby_matches)}")
            for index, nearby_match in enumerate(nearby_matches[:8], start=1):
                lines.append(f"nearby_{index}: {nearby_match.group(0)!r} at {nearby_match.start()}")
                lines.append(_debug_snippet(page_html, nearby_match.start(), radius=500))

        if not allow_full_page:
            for promote_path in reversed(promote_paths):
                pending.insert(0, (promote_path, True))

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)


async def export_recommend_debug_log(limit: int = 10) -> str:
    return await asyncio.to_thread(_write_recommend_debug_log_sync, limit)


async def get_daily_recommendations(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 20))
    try:
        page_html, allow_full_page = await asyncio.to_thread(_fetch_recommendation_source_sync)
        albums = _parse_album_links(page_html, limit, allow_full_page=allow_full_page)
        return await asyncio.to_thread(_enrich_album_details_sync, albums)
    except Exception as exc:
        print(f"[JM] Recommend failed: {exc}")
        return []
