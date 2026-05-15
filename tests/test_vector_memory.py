import sys
import unittest
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "Bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from memory.vector_memory import _format_memory_line, _overlap_score, _terms


class VectorMemoryHelpersTests(unittest.TestCase):
    def test_terms_include_words_and_chinese_characters(self):
        terms = _terms("Hello 丛雨 memory")

        self.assertIn("hello", terms)
        self.assertIn("memory", terms)
        self.assertIn("丛", terms)
        self.assertIn("雨", terms)

    def test_overlap_score_rewards_exact_terms(self):
        query_terms = _terms("丛雨 likes tea")

        self.assertGreater(
            _overlap_score(query_terms, "today 丛雨 likes tea"),
            _overlap_score(query_terms, "unrelated content"),
        )

    def test_format_memory_line_preserves_speaker(self):
        line = _format_memory_line(
            {
                "role": "user",
                "user_id": "123",
                "content": "hello",
            }
        )

        self.assertEqual(line, "QQ123 曾说: hello")


if __name__ == "__main__":
    unittest.main()
