"""Unit test cho Cổng kiểm soát an toàn (Safety Gate) và câu hỏi ngoài phạm vi tri thức."""

import unittest

from config.settings import settings
from src.core.chatbot import ChatbotEngine
from src.core.models import QARecord


class TestSafetyGateModule(unittest.TestCase):
    def setUp(self):
        test_records = [
            QARecord(
                id="TEST_001",
                sheet="danhsachtutienganhA1-B2",
                question="about nghĩa là gì?",
                answer="Về, khoảng chừng.",
                normalized_question="about nghia la gi"
            )
        ]
        self.engine = ChatbotEngine(records=test_records)

    def test_out_of_scope_questions(self):
        """Đảm bảo mọi câu hỏi ngoài phạm vi đều bị từ chối và trả về câu chuẩn."""
        queries = [
            "Thủ đô của nước Pháp là gì?",
            "Giải phương trình bậc hai: x^2 + 5x + 6 = 0",
            "Thời tiết Hà Nội hôm nay thế nào?",
            "Ai là tổng thống đầu tiên của Hoa Kỳ?",
            "Công thức nấu món phở bò truyền thống"
        ]
        for q in queries:
            with self.subTest(query=q):
                response = self.engine.ask(q)
                self.assertEqual(response.mode, "NO_MATCH")
                self.assertEqual(response.answer, settings.OUT_OF_SCOPE_RESPONSE)
                self.assertLess(response.confidence_score, settings.RAG_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
