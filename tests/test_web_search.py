import sys
import unittest
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "Bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from web_search import (
    SearchResult,
    extract_readable_text,
    format_search_context,
    normalize_query,
    parse_duckduckgo_html,
)


class WebSearchHelpersTests(unittest.TestCase):
    def test_normalize_query_removes_cq_codes_sender_and_memory_context(self):
        query = normalize_query(
            "by 123456: [CQ:at,qq=42] 今天有什么新闻?\n\n[history]\nold chat",
        )

        self.assertEqual(query, "今天有什么新闻?")

    def test_parse_duckduckgo_html_extracts_results_and_cleans_redirect_urls(self):
        html = """
        <div class="result">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnews">
            Example &amp; News
          </a>
          <a class="result__snippet">A fresh snippet about the result.</a>
        </div>
        <div class="result">
          <a class="result__a" href="https://example.org/direct">Direct Result</a>
          <div class="result__snippet">Another snippet.</div>
        </div>
        """

        results = parse_duckduckgo_html(html, max_results=5)

        self.assertEqual(
            results,
            [
                SearchResult(
                    title="Example & News",
                    url="https://example.com/news",
                    snippet="A fresh snippet about the result.",
                ),
                SearchResult(
                    title="Direct Result",
                    url="https://example.org/direct",
                    snippet="Another snippet.",
                ),
            ],
        )

    def test_format_search_context_includes_sources(self):
        context = format_search_context(
            "test query",
            [SearchResult("Title", "https://example.com", "Snippet", "Full page text")],
        )

        self.assertIn("Web search query: test query", context)
        self.assertIn("[1] Title", context)
        self.assertIn("URL: https://example.com", context)
        self.assertIn("Snippet: Snippet", context)
        self.assertIn("Page excerpt: Full page text", context)

    def test_extract_readable_text_ignores_script_and_keeps_body(self):
        html = """
        <html>
          <head><script>var bad = "noise";</script></head>
          <body>
            <h1>作品标题</h1>
            <p>这是作品简介正文。</p>
            <style>.hidden { display: none; }</style>
            <p>这是剧情摘要。</p>
          </body>
        </html>
        """

        text = extract_readable_text(html, max_chars=200)

        self.assertIn("作品标题", text)
        self.assertIn("这是作品简介正文。", text)
        self.assertIn("这是剧情摘要。", text)
        self.assertNotIn("noise", text)


if __name__ == "__main__":
    unittest.main()
