"""Bộ kiểm thử đơn vị cho ExceptionHandler."""

import unittest
from pathlib import Path

from config.settings import settings
from src.chat.exception_handler import ExceptionHandler


class TestExceptionHandler(unittest.TestCase):
    """Kiểm thử tầng lọc và xử lý ngoại lệ / chitchat."""

    def setUp(self):
        self.handler = ExceptionHandler()

    def test_greetings(self):
        for q in ["Xin chào", "chào bạn", "hello", "hi", "hey"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "greeting")
            self.assertTrue(len(resp) > 0)

    def test_thanks(self):
        for q in ["Cảm ơn bạn", "cảm ơn", "thank you", "thanks"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "thanks")

    def test_goodbye(self):
        for q in ["Tạm biệt", "bye", "goodbye", "hẹn gặp lại"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "goodbye")

    def test_chatbot_identity(self):
        for q in ["Bạn là ai?", "Bạn tên gì?", "ai là bạn"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "chatbot_identity")

    def test_chatbot_capabilities(self):
        for q in ["Bạn có thể làm gì?", "Bạn hỗ trợ gì?", "Bạn làm được gì?"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "chatbot_capabilities")

    def test_unclear_input(self):
        for q in ["????", "......", "123456", "qwrtyp"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "unclear_input")

    def test_vocab_queries_should_not_match(self):
        """Các câu hỏi tra cứu từ vựng thực tế không được phép khớp với ExceptionHandler."""
        vocab_queries = [
            "từ about nghĩa là gì?",
            "cho tôi câu ví dụ của từ confident",
            "từ nào có nghĩa là vay mượn?",
            "abandon",
            "giải thích từ challenge",
        ]
        for q in vocab_queries:
            match = self.handler.match(q)
            self.assertIsNone(match, f"Query '{q}' should NOT match ExceptionHandler")


if __name__ == "__main__":
    unittest.main()
