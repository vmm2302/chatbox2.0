"""Unit test cho LLM Client và Prompt Builder."""

import unittest

from config.settings import settings
from src.core.models import QARecord, RetrievalResult
from src.llm.client import clean_chinese_characters
from src.llm.prompts import SYSTEM_PROMPT, build_rag_prompt


class TestLLMClientModule(unittest.TestCase):
    def test_clean_chinese_characters(self):
        """Kiểm tra bộ lọc loại bỏ ký tự chữ Hán / tiếng Trung."""
        text_with_hanzi = "Nghĩa là 你好 (hello) và 谢谢."
        cleaned = clean_chinese_characters(text_with_hanzi)
        self.assertNotIn("你好", cleaned)
        self.assertNotIn("谢谢", cleaned)
        self.assertIn("(hello) và .", cleaned)

        text_pure_vietnamese = "Từ này có nghĩa là xin chào và cảm ơn."
        self.assertEqual(clean_chinese_characters(text_pure_vietnamese), text_pure_vietnamese)

    def test_build_rag_prompt(self):
        """Kiểm tra cấu trúc prompt gửi tới mô hình."""
        record = QARecord(
            id="VOCAB_0001",
            sheet="sheet1",
            question="apple nghĩa là gì?",
            answer="Quả táo",
            source="Dict"
        )
        ctx = RetrievalResult(record=record, score=0.85, method="VECTOR")

        messages = build_rag_prompt("trái apple là gì", [ctx])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("VOCAB_0001", messages[1]["content"])
        self.assertIn("Quả táo", messages[1]["content"])
        self.assertIn("trái apple là gì", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
