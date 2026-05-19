from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import aiohttp
from aiohttp import ClientTimeout


_DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
_DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_CQ_RE = re.compile(r"\[CQ:[^\]]*\]")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    content: str = ""


class _ReadableTextParser(HTMLParser):
    _SKIP_TAGS = {
        "aside",
        "button",
        "canvas",
        "footer",
        "form",
        "header",
        "iframe",
        "nav",
        "noscript",
        "option",
        "script",
        "select",
        "style",
        "svg",
    }
    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }

    def __init__(self, max_chars: int):
        super().__init__(convert_charrefs=True)
        self.max_chars = max_chars
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._append(data)

    def text(self) -> str:
        return _trim_text("\n".join(_clean_text(part) for part in self.parts), self.max_chars)

    def _append(self, text: str) -> None:
        if len("".join(self.parts)) < self.max_chars * 2:
            self.parts.append(text)


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self, max_results: int):
        super().__init__(convert_charrefs=True)
        self.max_results = max_results
        self.results: list[SearchResult] = []
        self._current: dict[str, object] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        class_name = attrs_dict.get("class", "")

        if tag == "a" and "result__a" in class_name:
            self._flush_current()
            self._current = {
                "title": [],
                "url": _clean_duckduckgo_url(attrs_dict.get("href", "")),
                "snippet": [],
            }
            self._capture = "title"
            return

        if self._current is not None and "result__snippet" in class_name:
            self._capture = "snippet"

    def handle_data(self, data: str) -> None:
        if self._current is None or self._capture is None:
            return

        parts = self._current.get(self._capture)
        if isinstance(parts, list):
            parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "div", "span"} and self._capture in {"title", "snippet"}:
            self._capture = None

    def close(self) -> None:
        super().close()
        self._flush_current()

    def _flush_current(self) -> None:
        if self._current is None or len(self.results) >= self.max_results:
            self._current = None
            return

        title = _clean_text("".join(self._current.get("title", [])))
        url = str(self._current.get("url", "")).strip()
        snippet = _clean_text("".join(self._current.get("snippet", [])))
        if title and _is_http_url(url):
            self.results.append(SearchResult(title=title, url=url, snippet=snippet))
        self._current = None


def normalize_query(query: str, max_chars: int = 160) -> str:
    query = _CQ_RE.sub(" ", query or "")
    query = re.sub(r"^by\s+\d+\s*:\s*", "", query.strip(), flags=re.I)
    query = re.split(r"\n\s*\[", query, maxsplit=1)[0]
    query = _clean_text(query)
    if len(query) <= max_chars:
        return query
    return query[:max_chars].rsplit(" ", 1)[0].strip() or query[:max_chars].strip()


async def search_web(
    query: str,
    *,
    max_results: int = 4,
    timeout_seconds: float = 10.0,
    proxy_url: str | None = None,
    fetch_pages: bool = True,
    page_max_chars: int = 1400,
) -> list[SearchResult]:
    query = normalize_query(query)
    if not query or max_results <= 0:
        return []

    timeout = ClientTimeout(total=timeout_seconds)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        results = await _search_duckduckgo_html(
            session,
            query,
            max_results=max_results,
            proxy_url=proxy_url,
        )
        if results:
            return await enrich_search_results(
                session,
                results,
                proxy_url=proxy_url,
                fetch_pages=fetch_pages,
                page_max_chars=page_max_chars,
            )

        results = await _search_duckduckgo_api(
            session,
            query,
            max_results=max_results,
            proxy_url=proxy_url,
        )
        return await enrich_search_results(
            session,
            results,
            proxy_url=proxy_url,
            fetch_pages=fetch_pages,
            page_max_chars=page_max_chars,
        )


async def enrich_search_results(
    session: aiohttp.ClientSession,
    results: list[SearchResult],
    *,
    proxy_url: str | None,
    fetch_pages: bool = True,
    page_max_chars: int = 1400,
) -> list[SearchResult]:
    if not fetch_pages or page_max_chars <= 0 or not results:
        return results

    tasks = [
        _fetch_readable_page_text(
            session,
            result.url,
            proxy_url=proxy_url,
            max_chars=page_max_chars,
        )
        for result in results
    ]
    contents = await asyncio.gather(*tasks, return_exceptions=True)
    enriched: list[SearchResult] = []
    for result, content in zip(results, contents):
        page_text = "" if isinstance(content, Exception) else str(content)
        enriched.append(
            SearchResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                content=page_text,
            )
        )
    return enriched


def parse_duckduckgo_html(html: str, max_results: int = 4) -> list[SearchResult]:
    parser = _DuckDuckGoHTMLParser(max_results=max_results)
    parser.feed(html or "")
    parser.close()
    return _dedupe_results(parser.results, max_results)


def format_search_context(query: str, results: Iterable[SearchResult]) -> str:
    clean_query = normalize_query(query)
    lines = [
        f"Web search query: {clean_query}",
        "Use the following external search results as current reference material.",
        "If the results are weak or conflicting, say what is uncertain.",
    ]

    result_list = list(results)
    if not result_list:
        lines.append("No useful web results were returned.")
        return "\n".join(lines)

    for index, result in enumerate(result_list, start=1):
        title = result.title[:180].strip()
        snippet = result.snippet[:500].strip()
        lines.append(f"[{index}] {title}")
        lines.append(f"URL: {result.url}")
        if snippet:
            lines.append(f"Snippet: {snippet}")
        content = result.content[:1400].strip()
        if content:
            lines.append(f"Page excerpt: {content}")
    return "\n".join(lines)


async def _search_duckduckgo_html(
    session: aiohttp.ClientSession,
    query: str,
    *,
    max_results: int,
    proxy_url: str | None,
) -> list[SearchResult]:
    url = f"{_DUCKDUCKGO_HTML_URL}?q={quote_plus(query)}&kl=wt-wt"
    async with session.get(url, proxy=proxy_url) as response:
        if response.status != 200:
            return []
        html = await response.text(errors="ignore")

    return parse_duckduckgo_html(html, max_results=max_results)


async def _search_duckduckgo_api(
    session: aiohttp.ClientSession,
    query: str,
    *,
    max_results: int,
    proxy_url: str | None,
) -> list[SearchResult]:
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    }
    async with session.get(_DUCKDUCKGO_API_URL, params=params, proxy=proxy_url) as response:
        if response.status != 200:
            return []
        data = await response.json(content_type=None)

    results: list[SearchResult] = []
    abstract = _clean_text(data.get("AbstractText", ""))
    abstract_url = data.get("AbstractURL") or data.get("AbstractSource")
    heading = _clean_text(data.get("Heading", ""))
    if abstract and _is_http_url(str(abstract_url)):
        results.append(SearchResult(title=heading or query, url=str(abstract_url), snippet=abstract))

    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        _append_related_topic(results, topic)

    return _dedupe_results(results, max_results)


def _append_related_topic(results: list[SearchResult], topic: dict) -> None:
    if "Topics" in topic:
        for nested in topic.get("Topics", []):
            _append_related_topic(results, nested)
        return

    text = _clean_text(topic.get("Text", ""))
    url = str(topic.get("FirstURL", "")).strip()
    if not text or not _is_http_url(url):
        return

    title, _, snippet = text.partition(" - ")
    results.append(SearchResult(title=title or text, url=url, snippet=snippet or text))


def _clean_duckduckgo_url(url: str) -> str:
    url = unescape(url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://duckduckgo.com" + url

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return url


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


async def _fetch_readable_page_text(
    session: aiohttp.ClientSession,
    url: str,
    *,
    proxy_url: str | None,
    max_chars: int,
) -> str:
    if not _is_fetchable_page_url(url):
        return ""

    try:
        async with session.get(url, proxy=proxy_url, allow_redirects=True) as response:
            if response.status != 200:
                return ""
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ""
            html = await response.text(errors="ignore")
    except Exception:
        return ""

    return extract_readable_text(html, max_chars=max_chars)


def extract_readable_text(html: str, max_chars: int = 1400) -> str:
    parser = _ReadableTextParser(max_chars=max_chars)
    parser.feed(html or "")
    parser.close()
    return parser.text()


def _trim_text(text: str, max_chars: int) -> str:
    lines = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = _clean_text(line)
        if len(line) < 2 or line in seen:
            continue
        seen.add(line)
        lines.append(line)

    cleaned = "\n".join(lines)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit("\n", 1)[0].strip() or cleaned[:max_chars].strip()


def _is_fetchable_page_url(url: str) -> bool:
    if not _is_http_url(url):
        return False
    path = urlparse(url).path.lower()
    return not path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".zip", ".rar", ".7z"))


def _dedupe_results(results: Iterable[SearchResult], max_results: int) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        url = result.url.strip()
        if not _is_http_url(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(result)
        if len(deduped) >= max_results:
            break
    return deduped


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
