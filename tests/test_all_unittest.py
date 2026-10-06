"""Bộ kiểm thử hoàn chỉnh sử dụng thư viện chuẩn unittest (Không cần cài thêm pytest).

Sẵn sàng phục vụ cho quy trình audit độc lập của GPT-6-Astra-Max.
"""

import sys
import unittest
from pathlib import Path

# Đảm bảo đường dẫn gốc được nhận diện
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.core.chatbot import ChatbotEngine
from src.core.models import QARecord, RetrievalResult
from src.data.loader import QALoader, normalize_vietnamese_text
from src.llm.client import clean_chinese_characters
from src.llm.prompts import build_rag_prompt
from src.retriever.lexical_matcher import LexicalMatcher


class TestStringNormalization(unittest.TestCase):
    """Kiểm tra xử lý chuỗi và chuẩn hóa tiếng Việt."""

    def test_normalize_vietnamese(self):
        self.assertEqual(normalize_vietnamese_text("Xin Chào Thế Giới!"), "xin chao the gioi")
        self.assertEqual(normalize_vietnamese_text("Đường đi, Đất nước"), "duong di dat nuoc")
        self.assertEqual(normalize_vietnamese_text("a, an nghĩa là gì?"), "a an nghia la gi")
        self.assertEqual(normalize_vietnamese_text(""), "")

    def test_chinese_character_filtering(self):
        text = "Nghĩa là 你好 (hello) và 谢谢."
        cleaned = clean_chinese_characters(text)
        self.assertNotIn("你好", cleaned)
        self.assertNotIn("谢谢", cleaned)
        self.assertIn("(hello) và .", cleaned)


class TestQALoader(unittest.TestCase):
    """Kiểm tra chức năng của bộ nạp dữ liệu QALoader."""

    def test_record_to_dict_and_back(self):
        record = QARecord(
            id="T_01",
            sheet="sheet1",
            question="about nghĩa là gì?",
            answer="Về, khoảng.",
            source="Test Source",
            normalized_question="about nghia la gi"
        )
        d = record.to_dict()
        self.assertEqual(d["id"], "T_01")
        self.assertEqual(d["question"], "about nghĩa là gì?")

        restored = QARecord.from_dict(d)
        self.assertEqual(restored.id, record.id)
        self.assertEqual(restored.question, record.question)
        self.assertEqual(restored.answer, record.answer)


class TestLexicalMatcher(unittest.TestCase):
    """Kiểm tra khả năng so khớp Lexical và biểu thức quy tắc."""

    def setUp(self):
        self.sample_records = [
            QARecord(
                id="TEST_001",
                sheet="danhsachtutienganhA1-B2",
                question="about nghĩa là gì?",
                answer="Về, khoảng chừng.",
                normalized_question="about nghia la gi"
            ),
            QARecord(
                id="TEST_002",
                sheet="danhsachcauhoicotutrongcau",
                question="Cho tôi câu ví dụ của từ about này.",
                answer="Do you know much about this old city?",
                normalized_question="cho toi cau vi du cua tu about nay"
            ),
            QARecord(
                id="TEST_003",
                sheet="danhsachtheotrinhdoA1-B2",
                question="Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A1",
                answer="1. a, an\n2. about",
                normalized_question="cho toi 1 danh sach gom cac tu tieng anh trong trinh do a1"
            )
        ]
        self.matcher = LexicalMatcher(self.sample_records)

    def test_exact_match(self):
        res = self.matcher.match("about nghĩa là gì?")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertEqual(res.score, 1.0)
        self.assertEqual(res.method, "EXACT")

    def test_normalized_match(self):
        res = self.matcher.match("about nghia la gi?")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertGreaterEqual(res.score, 0.95)

    def test_vocab_pattern(self):
        res = self.matcher.match("từ about có nghĩa là gì")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertEqual(res.score, 0.95)

    def test_example_pattern(self):
        res = self.matcher.match("ví dụ từ about")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_002")
        self.assertEqual(res.score, 0.95)

    def test_out_of_scope_rejection(self):
        res = self.matcher.match("Thủ đô của nước Pháp là gì?")
        self.assertIsNone(res)


class TestSafetyGate(unittest.TestCase):
    """Kiểm tra cổng kiểm soát an toàn từ chối câu hỏi ngoài phạm vi."""

    def setUp(self):
        self.test_records = [
            QARecord(
                id="VOCAB_ABOUT",
                sheet="danhsachtutienganhA1-B2",
                question="about nghĩa là gì?",
                answer="Về, khoảng chừng.",
                normalized_question="about nghia la gi"
            )
        ]
        self.engine = ChatbotEngine(records=self.test_records)

    def test_out_of_scope_queries(self):
        out_of_scope_queries = [
            "Thủ đô của nước Pháp là gì?",
            "Giải phương trình bậc hai x^2 + 5x + 6 = 0",
            "Thời tiết Hà Nội hôm nay thế nào?",
            "Cho tôi công thức làm bánh ngọt"
        ]
        for query in out_of_scope_queries:
            with self.subTest(query=query):
                resp = self.engine.ask(query)
                self.assertEqual(
                    resp.mode, "NO_MATCH",
                    f"Câu hỏi '{query}' không bị chặn bởi cổng an toàn!"
                )
                self.assertEqual(resp.answer, settings.OUT_OF_SCOPE_RESPONSE)
                self.assertLess(resp.confidence_score, settings.RAG_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
