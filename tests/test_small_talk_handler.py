"""Bộ kiểm thử đơn vị cho SmallTalkHandler."""

import unittest
from unittest.mock import MagicMock

from src.chat.small_talk_handler import SmallTalkHandler


class TestSmallTalkHandler(unittest.TestCase):
    """Kiểm thử SmallTalkHandler xử lý Small Talk & Casual Chat."""

    def setUp(self):
        self.handler = SmallTalkHandler()

    def test_greetings(self):
        for q in ["Xin chào", "Hello", "Hi", "Chào bạn", "alo"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "greeting")
            self.assertTrue(len(resp) > 0)

    def test_thanks(self):
        for q in ["Cảm ơn", "Thank you", "Cảm ơn bạn", "Thanks"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "thanks")

    def test_goodbye(self):
        for q in ["Tạm biệt", "Bye", "Goodbye", "Hẹn gặp lại"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "goodbye")

    def test_casual_chat(self):
        for q in ["Bạn khỏe không?", "khỏe không", "how are you", "dạo này thế nào"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "casual_chat")

    def test_simple_acknowledgement(self):
        for q in ["Ok", "Được rồi", "oke", "dạ", "vâng", "ừ", "uh", "okay"]:
            match = self.handler.match(q)
            self.assertIsNotNone(match, f"Failed for '{q}'")
            intent, resp = match
            self.assertEqual(intent, "simple_acknowledgement")

    def test_handle_template_mode(self):
        resp = self.handler.handle("Xin chào", "greeting", "Chào bạn nhé!", use_llm=False)
        self.assertEqual(resp, "Chào bạn nhé!")

    def test_handle_llm_mode(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Chào bạn! Tôi rất vui được gặp bạn."
        resp = self.handler.handle("Xin chào", "greeting", use_llm=True, llm_client=mock_llm)
        self.assertEqual(resp, "Chào bạn! Tôi rất vui được gặp bạn.")
        mock_llm.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
