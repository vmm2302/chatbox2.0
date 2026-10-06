"""Bộ kiểm thử đơn vị cho QueryRouter."""

import unittest
from pathlib import Path

from src.chat.query_router import QueryRouter
from src.chat.small_talk_handler import SmallTalkHandler
from src.chat.topic_tracker import TopicTracker
from src.core.models import QARecord


class TestQueryRouter(unittest.TestCase):
    """Kiểm thử tầng Query Router điều phối 3 nhánh: SMALL_TALK, OUT_OF_SCOPE, VOCAB_QUERY."""

    def setUp(self):
        self.router = QueryRouter()
        sample_records = [
            QARecord("rec_1", "abandon", "sheet1", "Sheet 1", "B1", "abandon nghĩa là gì?", "Từ bỏ."),
            QARecord("rec_2", "confident", "sheet1", "Sheet 1", "B1", "confident nghĩa là gì?", "Tự tin."),
            QARecord("rec_3", "borrow", "sheet3", "Sheet 3", "A2", "borrow nghĩa là gì?", "Vay mượn."),
        ]
        self.tracker = TopicTracker(records=sample_records)

    def test_small_talk_greetings(self):
        for q in ["Xin chào", "Hello", "Hi", "Chào bạn"]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "SMALL_TALK", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "GREETING")
            self.assertTrue(len(decision.template_response) > 0)

    def test_small_talk_thanks(self):
        for q in ["Cảm ơn", "Thank you", "Cảm ơn bạn", "Thanks"]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "SMALL_TALK", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "THANKS")

    def test_small_talk_goodbye(self):
        for q in ["Tạm biệt", "Bye", "Goodbye", "Hẹn gặp lại"]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "SMALL_TALK", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "GOODBYE")

    def test_small_talk_casual_chat(self):
        for q in ["Bạn khỏe không?", "khỏe không", "how are you", "dạo này thế nào?"]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "SMALL_TALK", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "CASUAL_CHAT")

    def test_small_talk_simple_acknowledgement(self):
        for q in ["Ok", "Được rồi", "oke", "dạ", "vâng", "ừ", "uh"]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "SMALL_TALK", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "SIMPLE_ACKNOWLEDGEMENT")

    def test_small_talk_bot_profile(self):
        decision_who = self.router.route("Bạn là ai?", self.tracker)
        self.assertEqual(decision_who.route_type, "SMALL_TALK")
        self.assertEqual(decision_who.intent, "CHATBOT_IDENTITY")

        decision_cap = self.router.route("Bạn có thể làm gì?", self.tracker)
        self.assertEqual(decision_cap.route_type, "SMALL_TALK")
        self.assertEqual(decision_cap.intent, "CHATBOT_CAPABILITIES")

    def test_out_of_scope_queries(self):
        for q in [
            "Bitcoin hôm nay bao nhiêu?",
            "Thời tiết hôm nay thế nào?",
            "Giá vàng hôm nay bao nhiêu?",
            "Cho tôi công thức nấu ăn",
            "Viết code Python cho tôi",
        ]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "OUT_OF_SCOPE", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "OUT_OF_SCOPE")
            self.assertIsNotNone(decision.template_response)

    def test_vocab_queries(self):
        for q in [
            "Abandon nghĩa là gì?",
            "từ nào có nghĩa là vay mượn?",
            "cho tôi câu ví dụ của từ confident",
            "từ này nghĩa gì?",
            "giải thích từ challenge",
        ]:
            decision = self.router.route(q, self.tracker)
            self.assertEqual(decision.route_type, "VOCAB_QUERY", f"Failed for '{q}'")
            self.assertEqual(decision.intent, "VOCAB_QUERY")


if __name__ == "__main__":
    unittest.main()
