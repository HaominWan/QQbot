import asyncio
import importlib.util
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "Bot"


def load_jm2pdf():
    sys.modules.setdefault("jmcomic", types.SimpleNamespace())
    pil_module = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")
    pil_module.Image = image_module
    sys.modules.setdefault("PIL", pil_module)
    sys.modules.setdefault("PIL.Image", image_module)
    module_path = BOT_DIR / "plugins" / "jm2pdf.py"
    spec = importlib.util.spec_from_file_location("jm2pdf_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


JM_HOME_RECOMMEND_HTML = """
<div class="col-lg-12 col-md-12">
  <div class="row">
    <div class="pull-left">
      <h4 class="talk-title"><span class="p-r-15">C107&推薦本本</span></h4>
    </div>
    <div class="pull-right m-t-10">
      <a class="talk-more-btn" href="/promotes/29">看更多</a>
    </div>
  </div>
  <div class="row m-b-10">
    <ul class="owl-carousel owl-comic-block">
      <div class="p-b-15 p-l-5 p-r-5">
        <div class="thumb-overlay-albums">
          <a href="/album/1437829/禁漫漢化組-c107-のりんこ-先生と明日香-中国翻訳">
            <img data-src="https://cdn.example/1437829_3x4.jpg"
                 title="[禁漫漢化組](C107)[のりんこ]先生と明日香[中国翻訳]"
                 alt="[禁漫漢化組](C107)[のりんこ]先生と明日香[中国翻訳]" />
          </a>
          <div class="category-icon">
            <div class="label-category">同人</div>
            <div class="label-sub">漢化</div>
          </div>
        </div>
        <span class="video-title title-truncate-index">[禁漫漢化組](C107)[のりんこ]先生と明日香[中国翻訳]</span>
      </div>
      <div class="p-b-15 p-l-5 p-r-5">
        <div class="thumb-overlay-albums">
          <a href="/album/1437530/禁漫漢化組-c107-ennui-のこっぱ-山の神は淫乱お狐様-中国翻訳">
            <img title="[禁漫漢化組](C107)[ENNUI(のこっぱ)]山の神は淫乱お狐様[中国翻訳]"
                 alt="[禁漫漢化組](C107)[ENNUI(のこっぱ)]山の神は淫乱お狐様[中国翻訳]" />
          </a>
        </div>
        <span class="video-title title-truncate-index">[禁漫漢化組](C107)[ENNUI(のこっぱ)]山の神は淫乱お狐様[中国翻訳]</span>
      </div>
    </ul>
  </div>
</div>
<div class="col-lg-12 col-md-12">
  <div class="row">
    <h4 class="talk-title"><span>禁漫去碼&全彩化</span></h4>
  </div>
  <div class="row m-b-10">
    <a href="/album/1435728/other"><img title="Other title" /></a>
  </div>
</div>
"""


PROMOTE_ENTRY_HOME_HTML = """
<div class="col-lg-12 col-md-12">
  <form><input name="password" type="password" value="secret-password" /></form>
  <div class="row">
    <h4 class="talk-title"><span>C108&&推荐本本</span></h4>
    <a class="talk-more-btn" href="https://18comic.vip/promotes/29">看更多</a>
  </div>
</div>
"""


PROMOTE_LIST_HTML = """
<div class="row">
  <div class="list-col">
    <a href="/album/1439001/promoted-one">
      <img title="Promoted One" alt="Promoted One" />
    </a>
    <div class="tags"><a href="/search/photos?search_query=中文">中文</a></div>
  </div>
  <div class="list-col">
    <a href="/album/1439002/promoted-two">
      <img title="Promoted Two" alt="Promoted Two" />
    </a>
  </div>
</div>
"""


MEIMAN_CATEGORY_HTML = """
<!doctype html>
<html>
<head>
  <meta property="og:title" content=" 最新的English Manga Comics - 禁漫天堂">
  <meta property="og:url" content="https://jmcomic-zzz.one/albums/meiman">
  <link rel="canonical" href="https://jmcomic-zzz.one/albums/meiman">
</head>
<body>
  <a href="/album/205460/meiman"><img title="English category entry" /></a>
</body>
</html>
"""


class FakeRecommendClient:
    def __init__(self):
        self.paths: list[str] = []

    def get_jm_html(self, path: str) -> str:
        self.paths.append(path)
        if path == "/":
            return PROMOTE_ENTRY_HOME_HTML
        if path == "/promotes/29":
            return PROMOTE_LIST_HTML
        return ""


class FakeCategoryClient:
    def __init__(self):
        self.paths: list[str] = []

    def get_jm_html(self, path: str) -> str:
        self.paths.append(path)
        if path == "https://18comic.vip/":
            return JM_HOME_RECOMMEND_HTML
        return MEIMAN_CATEGORY_HTML


class JmRecommendParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jm2pdf = load_jm2pdf()

    def test_parses_homepage_c107_recommendation_row(self):
        albums = self.jm2pdf._parse_album_links(JM_HOME_RECOMMEND_HTML, 10)

        self.assertEqual([album["id"] for album in albums], ["1437829", "1437530"])
        self.assertIn("先生と明日香", albums[0]["title"])
        self.assertNotIn("1435728", [album["id"] for album in albums])

    def test_dom_parser_skips_html_comment_nodes(self):
        html = f"<main><!-- ad marker -->{JM_HOME_RECOMMEND_HTML}<!-- trailing --></main>"
        albums = self.jm2pdf._parse_album_links(html, 10)

        self.assertEqual([album["id"] for album in albums], ["1437829", "1437530"])

    def test_regex_fallback_accepts_double_ampersand_simplified_marker(self):
        original_dom_parser = self.jm2pdf._recommend_section_by_dom
        self.jm2pdf._recommend_section_by_dom = lambda _html, **_kwargs: ""
        try:
            html = JM_HOME_RECOMMEND_HTML.replace("C107&推薦本本", "C108&&推荐本本")
            albums = self.jm2pdf._parse_album_links(html, 1)
        finally:
            self.jm2pdf._recommend_section_by_dom = original_dom_parser

        self.assertEqual([album["id"] for album in albums], ["1437829"])

    def test_fetch_follows_recommend_promote_page_when_home_section_has_no_albums(self):
        client = FakeRecommendClient()
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        try:
            self.jm2pdf._create_option = lambda: object()
            self.jm2pdf._new_html_client = lambda _option: client
            html, allow_full_page = self.jm2pdf._fetch_recommendation_source_sync()
            albums = self.jm2pdf._parse_album_links(html, 10, allow_full_page=allow_full_page)
        finally:
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client

        self.assertEqual(client.paths, ["/", "/promotes/29"])
        self.assertTrue(allow_full_page)
        self.assertEqual([album["id"] for album in albums], ["1439001", "1439002"])
        self.assertEqual(albums[0]["tags"], ["中文"])

    def test_fetch_tries_absolute_homepage_when_jmcomic_root_returns_category_page(self):
        client = FakeCategoryClient()
        direct_urls: list[str] = []
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        original_fetch_direct_html = self.jm2pdf._fetch_direct_html
        try:
            self.jm2pdf._create_option = lambda: object()
            self.jm2pdf._new_html_client = lambda _option: client

            def fake_fetch_direct_html(url: str) -> str:
                direct_urls.append(url)
                if url == "https://18comic.vip/":
                    return JM_HOME_RECOMMEND_HTML
                return MEIMAN_CATEGORY_HTML

            self.jm2pdf._fetch_direct_html = fake_fetch_direct_html
            html, allow_full_page = self.jm2pdf._fetch_recommendation_source_sync()
            albums = self.jm2pdf._parse_album_links(html, 10, allow_full_page=allow_full_page)
        finally:
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client
            self.jm2pdf._fetch_direct_html = original_fetch_direct_html

        self.assertEqual(client.paths, ["/", "https://18comic.vip/"])
        self.assertEqual(direct_urls, [])
        self.assertFalse(allow_full_page)
        self.assertEqual([album["id"] for album in albums], ["1437829", "1437530"])

    def test_debug_log_follows_promote_page_and_redacts_sensitive_values(self):
        client = FakeRecommendClient()
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        original_tmp_dir = self.jm2pdf._TMP_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.jm2pdf._TMP_DIR = Path(tmp)
                self.jm2pdf._create_option = lambda: object()
                self.jm2pdf._new_html_client = lambda _option: client
                report_path = Path(self.jm2pdf._write_recommend_debug_log_sync())
                report = report_path.read_text(encoding="utf-8")
        finally:
            self.jm2pdf._TMP_DIR = original_tmp_dir
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client

        self.assertIn("path: '/'", report)
        self.assertIn("path: '/promotes/29'", report)
        self.assertIn("recommend_promote_paths: ['/promotes/29']", report)
        self.assertIn("parsed_full_page_ids: ['1439001', '1439002']", report)
        self.assertIn('value="<redacted>"', report)
        self.assertNotIn("secret-password", report)

    def test_debug_export_timeout_returns_partial_report_path(self):
        original_tmp_dir = self.jm2pdf._TMP_DIR
        original_writer = self.jm2pdf._write_recommend_debug_log_sync
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.jm2pdf._TMP_DIR = Path(tmp)

                def slow_writer(*_args, **_kwargs):
                    time.sleep(0.2)
                    return ""

                self.jm2pdf._write_recommend_debug_log_sync = slow_writer
                report_path = Path(asyncio.run(self.jm2pdf.export_recommend_debug_log(timeout=0.01)))
                self.assertTrue(report_path.exists())
                report = report_path.read_text(encoding="utf-8")
        finally:
            self.jm2pdf._TMP_DIR = original_tmp_dir
            self.jm2pdf._write_recommend_debug_log_sync = original_writer

        self.assertIn("debug_timeout", report)


if __name__ == "__main__":
    unittest.main()
