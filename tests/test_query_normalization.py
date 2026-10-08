"""Bộ kiểm thử xác thực Query Normalization và Intent Routing (Case Insensitivity & Generic Vocab).

Kiểm tra:
1. Hàm chuẩn hóa normalize_query_text (Unicode NFC, khoảng trắng, lowercasing).
2. Query Router phân luồng đồng nhất không phân biệt chữ hoa/thường:
   - 6 biến thể của từ "about":
     + "about trong Tiếng Việt có nghĩa là gì?"
     + "about trong tiếng Việt có nghĩa là gì?"
     + "ABOUT TRONG TIẾNG VIỆT CÓ NGHĨA LÀ GÌ?"
     + "About trong tiếng Việt có nghĩa là gì?"
     + "about nghĩa là gì?"
     + "nghĩa của about?"
   - Các từ vựng tiếng Anh khác (đảm bảo tính tổng quát, ZERO hardcoding).
3. ChatEngine xử lý đồng nhất cả 6 biến thể của từ "about":
   - Cùng intent (DEFINE_VOCAB / VOCAB_QUERY)
   - Cùng mode hợp lệ (DIRECT_MATCH / RAG_GENERATION)
   - KHÔNG bị trả về OUT_OF_SCOPE hay NO_MATCH.
"""

import os
import sys
import unicodedata
import unittest
from pathlib import Path

# Đảm bảo môi trường offline
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chat.engine import ChatEngine
from src.chat.query_router import QueryRouter
from src.chat.topic_tracker import TopicTracker
from src.data.loader import QALoader, normalize_query_text


class TestQueryNormalizationUnits(unittest.TestCase):
    """Kiểm thử đơn vị cho hàm normalize_query_text."""

    def test_unicode_nfc_and_whitespace(self):
        # Dạng NFD phân rã của chuỗi tiếng Việt có dấu
        raw_nfd = unicodedata.normalize("NFD", "   about   trong   Tiếng   Việt   có  nghĩa là gì?   ")
        clean_query, normalized_query = normalize_query_text(raw_nfd)

        # clean_query phải là NFC, loại bỏ khoảng trắng thừa, giữ hoa/thường
        self.assertEqual(clean_query, "about trong Tiếng Việt có nghĩa là gì?")
        self.assertTrue(unicodedata.is_normalized("NFC", clean_query))

        # normalized_query phải viết thường toàn bộ
        self.assertEqual(normalized_query, "about trong tiếng việt có nghĩa là gì?")
        self.assertTrue(unicodedata.is_normalized("NFC", normalized_query))

    def test_all_caps_normalization(self):
        raw = "   ABOUT  TRONG  TIẾNG  VIỆT  CÓ  NGHĨA  LÀ  GÌ?  "
        clean_query, normalized_query = normalize_query_text(raw)
        self.assertEqual(clean_query, "ABOUT TRONG TIẾNG VIỆT CÓ NGHĨA LÀ GÌ?")
        self.assertEqual(normalized_query, "about trong tiếng việt có nghĩa là gì?")

    def test_empty_string(self):
        clean, norm = normalize_query_text("   ")
        self.assertEqual(clean, "")
        self.assertEqual(norm, "")


class TestQueryRouterCaseInsensitivity(unittest.TestCase):
    """Kiểm thử định tuyến QueryRouter không phụ thuộc chữ hoa/thường."""

    @classmethod
    def setUpClass(cls):
        loader = QALoader()
        cls.records = loader.get_or_create_records()
        cls.tracker = TopicTracker(records=cls.records)
        cls.router = QueryRouter()

    def test_about_six_variations_route_to_vocab_query(self):
        variations = [
            "about trong Tiếng Việt có nghĩa là gì?",
            "about trong tiếng Việt có nghĩa là gì?",
            "ABOUT TRONG TIẾNG VIỆT CÓ NGHĨA LÀ GÌ?",
            "About trong tiếng Việt có nghĩa là gì?",
            "about nghĩa là gì?",
            "nghĩa của about?",
        ]
        for query in variations:
            with self.subTest(query=query):
                clean_q, norm_q = normalize_query_text(query)
                decision = self.router.route(norm_q, self.tracker)
                self.assertEqual(
                    decision.route_type,
                    "VOCAB_QUERY",
                    f"Query '{query}' phải là VOCAB_QUERY, nhưng nhận {decision.route_type}"
                )

    def test_generic_vocabulary_case_insensitivity(self):
        cases = [
            ("hello trong Tiếng Việt nghĩa là gì?", "hello"),
            ("HELLO trong tiếng Việt có nghĩa là gì?", "hello"),
            ("apple trong Tiếng Việt có nghĩa là gì?", "apple"),
            ("APPLE NGHĨA LÀ GÌ?", "apple"),
            ("abandon trong Tiếng Việt có nghĩa là gì?", "abandon"),
            ("nghĩa của abandon?", "abandon"),
        ]
        for query, expected_word in cases:
            with self.subTest(query=query):
                clean_q, norm_q = normalize_query_text(query)
                decision = self.router.route(norm_q, self.tracker)
                self.assertEqual(
                    decision.route_type,
                    "VOCAB_QUERY",
                    f"Query '{query}' phải là VOCAB_QUERY"
                )

                target_word = self.tracker.extract_target_word(clean_q)
                self.assertEqual(
                    target_word,
                    expected_word,
                    f"Từ trích xuất phải là '{expected_word}', nhận '{target_word}'"
                )

    def test_small_talk_case_insensitivity(self):
        cases = [
            "Xin chào",
            "XIN CHÀO",
            "xin chào bạn",
            "HELLO",
            "cảm ơn",
            "CẢM ƠN BẠN",
        ]
        for query in cases:
            with self.subTest(query=query):
                clean_q, norm_q = normalize_query_text(query)
                decision = self.router.route(norm_q, self.tracker)
                self.assertEqual(
                    decision.route_type,
                    "SMALL_TALK",
                    f"Query '{query}' phải là SMALL_TALK"
                )

    def test_out_of_scope_case_insensitivity(self):
        cases = [
            "Thời tiết hôm nay thế nào?",
            "THỜI TIẾT HÔM NAY THẾ NÀO?",
            "giá vàng hôm nay bao nhiêu?",
            "GIÁ VÀNG HÔM NAY",
        ]
        for query in cases:
            with self.subTest(query=query):
                clean_q, norm_q = normalize_query_text(query)
                decision = self.router.route(norm_q, self.tracker)
                self.assertEqual(
                    decision.route_type,
                    "OUT_OF_SCOPE",
                    f"Query '{query}' phải là OUT_OF_SCOPE"
                )


class TestChatEngineAboutVariations(unittest.TestCase):
    """Kiểm thử tích hợp ChatEngine trên toàn bộ 6 biến thể câu hỏi về từ 'about'."""

    @classmethod
    def setUpClass(cls):
        loader = QALoader()
        cls.records = loader.get_or_create_records()
        cls.engine = ChatEngine(records=cls.records)
        cls.engine.warm_up()

    def setUp(self):
        # Reset tracker để mỗi test case hoàn toàn độc lập
        self.engine.tracker.active_word = None
        self.engine.tracker.history.clear()

    def test_about_six_variations_produce_valid_answers(self):
        variations = [
            "about trong Tiếng Việt có nghĩa là gì?",
            "about trong tiếng Việt có nghĩa là gì?",
            "ABOUT TRONG TIẾNG VIỆT CÓ NGHĨA LÀ GÌ?",
            "About trong tiếng Việt có nghĩa là gì?",
            "about nghĩa là gì?",
            "nghĩa của about?",
        ]
        for query in variations:
            with self.subTest(query=query):
                self.engine.tracker.active_word = None
                self.engine.tracker.history.clear()

                resp = self.engine.ask(query)

                # 1. Không bao giờ được là OUT_OF_SCOPE hoặc NO_MATCH
                self.assertNotEqual(
                    resp.mode, "NO_MATCH", f"Query '{query}' không được trả về NO_MATCH"
                )
                self.assertNotEqual(
                    resp.intent, "OUT_OF_SCOPE", f"Query '{query}' không được có intent OUT_OF_SCOPE"
                )

                # 2. Intent phải là DEFINE_VOCAB hoặc VOCAB_QUERY
                self.assertIn(
                    resp.intent,
                    ("DEFINE_VOCAB", "VOCAB_QUERY"),
                    f"Query '{query}' phải có intent DEFINE_VOCAB, nhận '{resp.intent}'"
                )

                # 3. Phải trả lời từ 'about' và nội dung giải nghĩa chuẩn
                has_about_word = (resp.word == "about") or (
                    resp.candidates and any(c.record.word == "about" for c in resp.candidates)
                )
                self.assertTrue(has_about_word, f"Query '{query}' phải khớp từ 'about'")
                self.assertTrue(resp.answer and len(resp.answer.strip()) > 0)
                ans_lower = resp.answer.lower()
                has_meaning = ("về" in ans_lower or "khoảng" in ans_lower or "liên quan" in ans_lower)
                self.assertTrue(has_meaning, f"Câu trả lời cho '{query}' phải chứa nghĩa tiếng Việt của 'about'")

    def test_case_consistency_across_all_variations(self):
        """Kiểm tra câu trả lời của Input 1 ('Tiếng Việt') và Input 2 ('tiếng Việt') phải giống hệt nhau."""
        self.engine.tracker.active_word = None
        self.engine.tracker.history.clear()
        resp_cap = self.engine.ask("about trong Tiếng Việt có nghĩa là gì?")

        self.engine.tracker.active_word = None
        self.engine.tracker.history.clear()
        resp_lower = self.engine.ask("about trong tiếng Việt có nghĩa là gì?")

        self.assertEqual(resp_cap.mode, resp_lower.mode)
        self.assertEqual(resp_cap.record_id, resp_lower.record_id)
        self.assertEqual(resp_cap.answer, resp_lower.answer)


if __name__ == "__main__":
    unittest.main()
