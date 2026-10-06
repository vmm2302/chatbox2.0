"""Unit test cho Matcher và Hybrid Retriever."""

import unittest

from src.core.models import QARecord
from src.retriever.lexical_matcher import LexicalMatcher


class TestRetrieverModule(unittest.TestCase):
    def setUp(self):
        """Tạo bộ dữ liệu Q&A giả lập có đánh dấu TEST DATA."""
        self.sample_records = [
            QARecord(
                id="TEST_001",
                sheet="danhsachtutienganhA1-B2",
                question="about nghĩa là gì?",
                answer="Phát âm : /əˈbaʊt/\nVề, khoảng chừng.",
                source="Test Dictionary",
                normalized_question="about nghia la gi"
            ),
            QARecord(
                id="TEST_002",
                sheet="danhsachtutienganhA1-B2",
                question="above nghĩa là gì?",
                answer="Phát âm : /əˈbʌv/\nỞ trên.",
                source="Test Dictionary",
                normalized_question="above nghia la gi"
            ),
            QARecord(
                id="TEST_003",
                sheet="danhsachcauhoicotutrongcau",
                question="Cho tôi câu ví dụ của từ about này.",
                answer="Do you know much about this old city?",
                source="Test Dictionary",
                normalized_question="cho toi cau vi du cua tu about nay"
            ),
            QARecord(
                id="TEST_004",
                sheet="danhsachtheotrinhdoA1-B2",
                question="Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A1",
                answer="1. a, an\n2. about",
                source="Test Framework",
                normalized_question="cho toi 1 danh sach gom cac tu tieng anh trong trinh do a1"
            )
        ]

    def test_lexical_exact_match(self):
        """Kiểm tra so khớp nguyên văn 100%."""
        matcher = LexicalMatcher(self.sample_records)
        res = matcher.match("about nghĩa là gì?")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertEqual(res.score, 1.0)
        self.assertEqual(res.method, "EXACT")

    def test_lexical_normalized_match(self):
        """Kiểm tra so khớp không dấu."""
        matcher = LexicalMatcher(self.sample_records)
        res = matcher.match("about nghia la gi?")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertGreaterEqual(res.score, 0.95)

    def test_lexical_vocab_pattern_match(self):
        """Kiểm tra trích xuất từ vựng từ mẫu câu khác."""
        matcher = LexicalMatcher(self.sample_records)
        res = matcher.match("từ about có nghĩa là gì")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_001")
        self.assertEqual(res.score, 0.95)

    def test_lexical_example_pattern_match(self):
        """Kiểm tra mẫu hỏi câu ví dụ."""
        matcher = LexicalMatcher(self.sample_records)
        res = matcher.match("ví dụ từ about")
        self.assertIsNotNone(res)
        self.assertEqual(res.record.id, "TEST_003")
        self.assertEqual(res.score, 0.95)

    def test_lexical_no_match(self):
        """Kiểm tra câu hỏi hoàn toàn ngoài lề không bị khớp sai."""
        matcher = LexicalMatcher(self.sample_records)
        res = matcher.match("Thủ đô của nước Pháp là gì?")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
