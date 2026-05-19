import importlib
import sys
import types
import unittest
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "Bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))


def load_api_with_fake_config():
    previous_api = sys.modules.pop("api", None)
    previous_config = sys.modules.get("config")

    fake_config = types.ModuleType("config")
    fake_config.DEEPSEEK_API_KEY = "REDACTED_API_KEY"
    fake_config.DEEPSEEK_BASE_URL = "https://example.invalid"
    fake_config.DEEPSEEK_MODEL = "deepseek-v4-flash"
    fake_config.DEEPSEEK_TEMPERATURE = 0.75
    fake_config.PROXY_URL = ""
    fake_config.GROQ_API_KEY = ""
    fake_config.WEB_SEARCH_ENABLED = True
    fake_config.WEB_SEARCH_MAX_RESULTS = 4
    fake_config.WEB_SEARCH_TIMEOUT_SECONDS = 10
    fake_config.WEB_SEARCH_AUTO_FOR_TIME_SENSITIVE = True
    fake_config.WEB_SEARCH_ALLOW_MODEL_REQUEST = True
    sys.modules["config"] = fake_config

    try:
        module = importlib.import_module("api")
    finally:
        if previous_config is None:
            sys.modules.pop("config", None)
        else:
            sys.modules["config"] = previous_config
        if previous_api is not None:
            sys.modules["_previous_api_for_test"] = previous_api

    return module


class ApiWebSearchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_api_with_fake_config()

    @classmethod
    def tearDownClass(cls):
        previous_api = sys.modules.pop("_previous_api_for_test", None)
        sys.modules.pop("api", None)
        if previous_api is not None:
            sys.modules["api"] = previous_api

    def test_chinese_year_query_is_time_sensitive(self):
        self.assertTrue(self.api._looks_time_sensitive("2026年张雪峰发生了什么事？"))

    def test_event_meme_with_person_name_is_time_sensitive(self):
        message = "一箱巧乐兹和复活张雪峰你选哪一个"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "张雪峰 复活 最新")

    def test_bracketed_work_summary_query_uses_web_search(self):
        message = "对类似《超时空辉夜姬》进行简述"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "超时空辉夜姬 简介 剧情 评价")

    def test_quoted_work_summary_and_review_query_uses_web_search(self):
        message = "简述并评价“超时空辉夜姬”这个作品"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "超时空辉夜姬 简介 剧情 评价")

    def test_plain_work_summary_and_review_query_uses_web_search(self):
        message = "简述并评价超时空辉夜姬这个作品"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "超时空辉夜姬 简介 剧情 评价")

    def test_unbracketed_work_opinion_query_uses_web_search(self):
        message = "你对从零开始的异世界生活有什么看法"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "从零开始的异世界生活 简介 剧情 评价")

    def test_short_work_alias_query_uses_web_search(self):
        message = "你对re0有什么看法"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(self.api._search_query_for_message(message), "re0 简介 剧情 评价")

    def test_slash_separated_work_aliases_are_kept_for_search(self):
        message = "你对re0/从零开始的异世界生活有什么看法"

        self.assertTrue(self.api._looks_time_sensitive(message))
        self.assertEqual(
            self.api._search_query_for_message(message),
            "re0 从零开始的异世界生活 简介 剧情 评价",
        )

    def test_casual_personal_opinion_does_not_trigger_work_search(self):
        self.assertFalse(self.api._looks_time_sensitive("你对我有什么看法"))

    def test_knowledge_gap_response_retries_with_search_for_event_context(self):
        self.assertTrue(
            self.api._should_retry_with_search(
                "一箱巧乐兹和复活张雪峰你选哪一个",
                "张雪峰是谁？丛雨不认识。",
            )
        )

    def test_user_can_disable_search_in_message(self):
        self.assertFalse(self.api._looks_time_sensitive("不要联网，2026年张雪峰发生了什么事？"))

    def test_runtime_context_is_inserted_after_persona_system_prompt(self):
        messages = self.api._with_runtime_context(
            [
                {"role": "system", "content": "persona"},
                {"role": "user", "content": "hi"},
            ]
        )

        self.assertEqual(messages[0]["content"], "persona")
        self.assertIn("current local date", messages[1]["content"])
        self.assertEqual(messages[2]["content"], "hi")


if __name__ == "__main__":
    unittest.main()
