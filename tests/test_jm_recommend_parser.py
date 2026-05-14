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


class FakeCategoryWithPromoteClient:
    def __init__(self):
        self.paths: list[str] = []

    def get_jm_html(self, path: str) -> str:
        self.paths.append(path)
        if path == "/promotes/29":
            return PROMOTE_LIST_HTML
        return MEIMAN_CATEGORY_HTML


class JmRecommendParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jm2pdf = load_jm2pdf()

    def test_pdf_password_uses_jm_digits(self):
        self.assertEqual(self.jm2pdf.pdf_password_for_code("350234"), "350234")
        self.assertEqual(self.jm2pdf.pdf_password_for_code("jm350234"), "350234")
        self.assertEqual(self.jm2pdf.pdf_password_for_code("JM350234"), "350234")

    def test_encrypt_pdf_replaces_plain_file_with_password_protected_output(self):
        writer_instances = []

        class FakeReader:
            def __init__(self, _path):
                self.pages = ["page-1", "page-2"]
                self.metadata = {"/Title": "Plain PDF"}

        class FakeWriter:
            def __init__(self):
                self.pages = []
                self.metadata = {}
                self.passwords = None
                writer_instances.append(self)

            def add_page(self, page):
                self.pages.append(page)

            def add_metadata(self, metadata):
                self.metadata.update(metadata)

            def encrypt(self, user_password, owner_password):
                self.passwords = (user_password, owner_password)

            def write(self, file):
                file.write(b"encrypted-pdf")

        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = FakeReader
        fake_pypdf.PdfWriter = FakeWriter
        original_pypdf = sys.modules.get("pypdf")
        sys.modules["pypdf"] = fake_pypdf
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pdf_path = Path(tmp) / "350234.pdf"
                pdf_path.write_bytes(b"plain-pdf")
                self.jm2pdf._encrypt_pdf(pdf_path, "350234")

                self.assertEqual(pdf_path.read_bytes(), b"encrypted-pdf")
                self.assertEqual(writer_instances[0].pages, ["page-1", "page-2"])
                self.assertEqual(writer_instances[0].metadata, {"/Title": "Plain PDF"})
                self.assertEqual(writer_instances[0].passwords, ("350234", "350234"))
        finally:
            if original_pypdf is None:
                sys.modules.pop("pypdf", None)
            else:
                sys.modules["pypdf"] = original_pypdf

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

        self.assertEqual(client.paths, ["/"])
        self.assertEqual(direct_urls, ["https://18comic.vip/"])
        self.assertFalse(allow_full_page)
        self.assertEqual([album["id"] for album in albums], ["1437829", "1437530"])

    def test_fetch_falls_back_to_known_recommend_promote_page(self):
        client = FakeCategoryWithPromoteClient()
        direct_urls: list[str] = []
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        original_fetch_direct_html = self.jm2pdf._fetch_direct_html
        try:
            self.jm2pdf._create_option = lambda: object()
            self.jm2pdf._new_html_client = lambda _option: client

            def fake_fetch_direct_html(url: str) -> str:
                direct_urls.append(url)
                if url.endswith("/promotes/29"):
                    return PROMOTE_LIST_HTML
                return MEIMAN_CATEGORY_HTML

            self.jm2pdf._fetch_direct_html = fake_fetch_direct_html
            html, allow_full_page = self.jm2pdf._fetch_recommendation_source_sync()
            albums = self.jm2pdf._parse_album_links(html, 10, allow_full_page=allow_full_page)
        finally:
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client
            self.jm2pdf._fetch_direct_html = original_fetch_direct_html

        self.assertNotIn("/promotes/29", client.paths)
        self.assertIn("https://18comic.vip/promotes/29", direct_urls)
        self.assertTrue(allow_full_page)
        self.assertEqual([album["id"] for album in albums], ["1439001", "1439002"])

    def test_fetch_uses_direct_promote_page_when_client_creation_fails(self):
        direct_urls: list[str] = []
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        original_fetch_direct_html = self.jm2pdf._fetch_direct_html
        try:
            self.jm2pdf._create_option = lambda: object()
            self.jm2pdf._new_html_client = lambda _option: (_ for _ in ()).throw(RuntimeError("tls boom"))

            def fake_fetch_direct_html(url: str) -> str:
                direct_urls.append(url)
                if url.endswith("/promotes/29"):
                    return PROMOTE_LIST_HTML
                return MEIMAN_CATEGORY_HTML

            self.jm2pdf._fetch_direct_html = fake_fetch_direct_html
            html, allow_full_page = self.jm2pdf._fetch_recommendation_source_sync()
            albums = self.jm2pdf._parse_album_links(html, 10, allow_full_page=allow_full_page)
        finally:
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client
            self.jm2pdf._fetch_direct_html = original_fetch_direct_html

        self.assertIn("https://18comic.vip/promotes/29", direct_urls)
        self.assertTrue(allow_full_page)
        self.assertEqual([album["id"] for album in albums], ["1439001", "1439002"])

    def test_home_candidates_include_domains_discovered_by_jmcomic_config(self):
        original_config = getattr(self.jm2pdf.jmcomic, "JmModuleConfig", None)
        try:
            self.jm2pdf.jmcomic.JmModuleConfig = types.SimpleNamespace(
                get_html_domain_all_via_github=lambda: [
                    "jmcomic-new.example",
                    "https://18comic.vip/",
                    "t.me/hcomic18",
                ],
                get_html_domain_all=lambda: ["jm18c-backup.example/path", "jm-88.cc/ZNPJam"],
            )
            candidates = self.jm2pdf._home_page_candidates()
        finally:
            if original_config is None:
                delattr(self.jm2pdf.jmcomic, "JmModuleConfig")
            else:
                self.jm2pdf.jmcomic.JmModuleConfig = original_config

        self.assertEqual(candidates[0], "/")
        self.assertIn("https://jmcomic-new.example/", candidates)
        self.assertIn("https://jm18c-backup.example/", candidates)
        self.assertNotIn("https://t.me/", candidates)
        self.assertNotIn("https://jm-88.cc/", candidates)
        self.assertEqual(candidates.count("https://18comic.vip/"), 1)

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

    def test_debug_log_continues_when_client_creation_fails(self):
        direct_urls: list[str] = []
        original_create_option = self.jm2pdf._create_option
        original_new_html_client = self.jm2pdf._new_html_client
        original_fetch_direct_html = self.jm2pdf._fetch_direct_html
        original_tmp_dir = self.jm2pdf._TMP_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.jm2pdf._TMP_DIR = Path(tmp)
                self.jm2pdf._create_option = lambda: object()
                self.jm2pdf._new_html_client = lambda _option: (_ for _ in ()).throw(RuntimeError("tls boom"))

                def fake_fetch_direct_html(url: str) -> str:
                    direct_urls.append(url)
                    if url.endswith("/promotes/29"):
                        return PROMOTE_LIST_HTML
                    return MEIMAN_CATEGORY_HTML

                self.jm2pdf._fetch_direct_html = fake_fetch_direct_html
                report_path = Path(self.jm2pdf._write_recommend_debug_log_sync())
                report = report_path.read_text(encoding="utf-8")
        finally:
            self.jm2pdf._TMP_DIR = original_tmp_dir
            self.jm2pdf._create_option = original_create_option
            self.jm2pdf._new_html_client = original_new_html_client
            self.jm2pdf._fetch_direct_html = original_fetch_direct_html

        self.assertIn("client_create_error: RuntimeError: tls boom", report)
        self.assertIn("client_mode: direct-only fallback", report)
        self.assertIn("path: 'https://18comic.vip/promotes/29'", report)
        self.assertIn("parsed_full_page_ids: ['1439001', '1439002']", report)
        self.assertIn("https://18comic.vip/promotes/29", direct_urls)

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
