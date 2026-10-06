"""Bộ kiểm thử toàn diện Master Pipeline (Unit & Integration Tests).

Kiểm thử 7 kịch bản kiểm định theo yêu cầu của GPT-6-Astra-Max:
1. Tra cứu định nghĩa chính xác (Exact Query).
2. Tra cứu ngữ nghĩa biến thể (Paraphrased Semantic Query).
3. Tra cứu tự nhiên tiếng Việt sang tiếng Anh (Natural Language Translation).
4. Câu hỏi mơ hồ thiếu ngữ cảnh (Ambiguous Query -> Clarification Gate).
5. Hội thoại nhiều lượt kế thừa ngữ cảnh (Multi-turn Follow-up Resolution).
6. Câu hỏi ngoài phạm vi (Out-of-scope Rejection).
7. Từ vựng không tồn tại trong từ điển (No-match Rejection).
"""

import os
import sys
import unittest
from pathlib import Path

# Đảm bảo đường dẫn gốc được nhận diện
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.chat.engine import CLARIFICATION_MESSAGE, ChatEngine
from src.chat.topic_tracker import TopicTracker
from src.core.models import QARecord
from src.data.loader import QALoader
from src.nlp.phobert_intent import PhoBERTIntentClassifier


class TestTopicTracker(unittest.TestCase):
    """Kiểm thử tầng TopicTracker quản lý ngữ cảnh và phân giải thực thể."""

    def setUp(self):
        self.sample_records = [
            QARecord("rec_1", "abandon", "sheet1", "Sheet 1", "B1", "abandon nghĩa là gì?", "Từ bỏ, ruồng bỏ."),
            QARecord("rec_2", "confident", "sheet1", "Sheet 1", "B1", "confident nghĩa là gì?", "Tự tin."),
            QARecord("rec_3", "hard-working", "sheet1", "Sheet 1", "A2", "hard-working nghĩa là gì?", "Chăm chỉ."),
        ]
        self.tracker = TopicTracker(records=self.sample_records)

    def test_extract_target_word_explicit(self):
        """Kiểm tra trích xuất từ vựng khi người dùng dùng cấu trúc rõ ràng hoặc ngoặc kép."""
        self.assertEqual(self.tracker.extract_target_word("từ 'abandon' nghĩa là gì?"), "abandon")
        self.assertEqual(self.tracker.extract_target_word('giải thích từ "confident"'), "confident")
        self.assertEqual(self.tracker.extract_target_word("từ hard-working thuộc cấp độ nào?"), "hard-working")

    def test_extract_target_word_standalone(self):
        """Kiểm tra trích xuất từ khi người dùng chỉ gõ tên từ tiếng Anh."""
        self.assertEqual(self.tracker.extract_target_word("abandon"), "abandon")

    def test_ambiguous_without_context(self):
        """Kiểm tra phát hiện câu hỏi mơ hồ khi chưa có active_word."""
        self.tracker.clear()
        query = "Từ này nghĩa là gì?"
        resolved, target_word, is_follow_up, is_ambiguous = self.tracker.resolve_query(query)
        self.assertTrue(is_ambiguous, "Phải nhận diện câu hỏi mơ hồ khi chưa có ngữ cảnh")
        self.assertIsNone(target_word)

    def test_follow_up_with_context(self):
        """Kiểm tra khôi phục câu hỏi nối tiếp khi đã có active_word từ lượt trước."""
        self.tracker.active_word = "abandon"
        query = "Còn câu ví dụ của từ này thì sao?"
        resolved, target_word, is_follow_up, is_ambiguous = self.tracker.resolve_query(query)

        self.assertFalse(is_ambiguous)
        self.assertTrue(is_follow_up)
        self.assertEqual(target_word, "abandon")
        self.assertIn("abandon", resolved.lower())


class TestPhoBERTIntent(unittest.TestCase):
    """Kiểm thử tầng Query Understanding sử dụng PhoBERT representation similarity."""

    @classmethod
    def setUpClass(cls):
        cls.classifier = PhoBERTIntentClassifier()
        cls.classifier.initialize()

    def test_define_vocab_intent(self):
        """Kiểm tra phân loại ý định tra cứu định nghĩa."""
        res = self.classifier.classify_intent("giải thích cho tôi từ abandon có nghĩa là gì")
        self.assertEqual(res.intent, "DEFINE_VOCAB")
        self.assertGreater(res.confidence, 0.5)

    def test_get_example_intent(self):
        """Kiểm tra phân loại ý định lấy câu ví dụ khi có từ vựng."""
        res = self.classifier.classify_intent("cho tôi một câu ví dụ với từ abandon")
        self.assertEqual(res.intent, "GET_EXAMPLE")

    def test_ambiguous_intent(self):
        """Kiểm tra nhận diện câu hỏi mơ hồ khi dùng đại từ mà không có active topic."""
        res = self.classifier.classify_intent("cho tôi một câu ví dụ với từ này", has_active_topic=False)
        self.assertEqual(res.intent, "AMBIGUOUS")
        self.assertTrue(res.is_ambiguous)

    def test_out_of_scope_intent(self):
        """Kiểm tra phát hiện câu hỏi ngoài phạm vi dự án."""
        res = self.classifier.classify_intent("thời tiết hôm nay tại Hà Nội thế nào?")
        self.assertEqual(res.intent, "OUT_OF_SCOPE")




class TestMasterPipelineEndToEnd(unittest.TestCase):
    """Kiểm thử luồng End-to-End Master Pipeline qua ChatEngine."""

    @classmethod
    def setUpClass(cls):
        loader = QALoader()
        cls.records = loader.get_or_create_records()
        cls.engine = ChatEngine(records=cls.records)
        cls.engine.warm_up()

    def setUp(self):
        self.engine.tracker.clear()

    def test_scenario_1_exact_query(self):
        """Kịch bản 1: Câu hỏi tra cứu định nghĩa từ vựng có trong dữ liệu (khớp từ about trong Sheet 1)."""
        resp = self.engine.ask("about nghĩa là gì?")
        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertIsNotNone(resp.record_id)
        self.assertTrue("về" in resp.answer.lower() or "quanh" in resp.answer.lower())
        self.assertEqual(self.engine.tracker.active_word, "about")

    def test_scenario_2_paraphrase_query(self):
        """Kịch bản 2: Câu hỏi diễn đạt tự nhiên / biến thể ngữ nghĩa (khớp từ about trong Sheet 1)."""
        resp = self.engine.ask("bạn có thể giải thích ý nghĩa của từ about được không?")
        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertTrue("về" in resp.answer.lower() or "quanh" in resp.answer.lower())


    def test_scenario_3_vietnamese_to_english(self):
        """Kịch bản 3: Tra cứu tự nhiên tiếng Việt sang tiếng Anh (khớp từ borrow trong Sheet 3)."""
        resp = self.engine.ask("từ nào có nghĩa là vay mượn?")
        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertTrue("borrow" in resp.answer.lower() or "borrow" in str(resp.candidates[0].record.answer).lower())


    def test_scenario_4_ambiguous_clarification(self):
        """Kịch bản 4: Câu hỏi mơ hồ khi chưa có ngữ cảnh -> Kích hoạt Clarification Gate."""
        resp = self.engine.ask("từ này nghĩa là gì?")
        self.assertEqual(resp.mode, "CLARIFICATION")
        self.assertEqual(resp.answer, CLARIFICATION_MESSAGE)

    def test_scenario_5_multiturn_follow_up(self):
        """Kịch bản 5: Hội thoại nhiều lượt kế thừa ngữ cảnh thành công."""
        # Lượt 1: Giới thiệu thực thể 'about' (có trong Sheet 1)
        resp1 = self.engine.ask("từ about nghĩa là gì?")
        self.assertEqual(self.engine.tracker.active_word, "about")

        # Lượt 2: Hỏi nối tiếp dùng đại từ "từ này" (khớp câu ví dụ trong Sheet 4)
        resp2 = self.engine.ask("cho tôi câu ví dụ của từ này")
        self.assertIn(resp2.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertTrue("about" in resp2.answer.lower() or "about" in str(resp2.candidates[0].record.answer).lower())


    def test_scenario_6_out_of_scope(self):
        """Kịch bản 6: Câu hỏi ngoài phạm vi kiến thức từ vựng -> Từ chối lịch sự."""
        resp = self.engine.ask("thời tiết hôm nay thế nào?")
        self.assertEqual(resp.mode, "NO_MATCH")
        self.assertEqual(resp.answer, settings.OUT_OF_SCOPE_RESPONSE)

    def test_scenario_7_unseen_vocabulary(self):
        """Kịch bản 7: Từ vựng không tồn tại trong từ điển 3,725 bản ghi -> Từ chối chuẩn hóa."""
        resp = self.engine.ask("từ zzzzqqqxyz nghĩa là gì?")
        self.assertEqual(resp.mode, "NO_MATCH")
        self.assertEqual(resp.answer, settings.OUT_OF_SCOPE_RESPONSE)

    def test_scenario_8_strict_sequential_pipeline_order(self):
        """Kịch bản 8: Kiểm định thứ tự thực thi tuyệt đối của pipeline theo Architecture Lock:
        User Query -> PhoBERT (Intent) -> Hybrid Retrieval (BM25 + BGE-M3) -> RRF Gate -> Qwen2.5:7B -> Final Answer.
        """
        execution_order = []

        orig_classify = self.engine.intent_classifier.classify_intent
        orig_retrieve = self.engine.retriever.retrieve
        orig_generate = self.engine.llm_client.generate_with_langchain

        def spy_classify(*args, **kwargs):
            execution_order.append("1_PhoBERT_Intent")
            return orig_classify(*args, **kwargs)

        def spy_retrieve(*args, **kwargs):
            execution_order.append("2_Hybrid_Retrieval_BM25_BGEM3")
            return orig_retrieve(*args, **kwargs)

        def spy_generate(question, context):
            execution_order.append("3_Qwen2.5_7B_Generation")
            # Kiểm tra context được truyền từ retrieval chứ không rỗng
            self.assertTrue(len(context) > 0, "Qwen phải nhận context được truy xuất từ BM25 + BGE-M3")
            return "Qwen test grounded answer"

        self.engine.intent_classifier.classify_intent = spy_classify
        self.engine.retriever.retrieve = spy_retrieve
        self.engine.llm_client.generate_with_langchain = spy_generate

        try:
            resp = self.engine.ask("bạn hãy phân tích nghĩa và cách dùng của từ confident")
            # Kiểm tra thứ tự các bước
            self.assertEqual(
                execution_order,
                ["1_PhoBERT_Intent", "2_Hybrid_Retrieval_BM25_BGEM3", "3_Qwen2.5_7B_Generation"]
            )
            # Kiểm tra kết quả trả về
            self.assertIsNotNone(resp.answer)
            self.assertEqual(resp.intent, "DEFINE_VOCAB")
            self.assertGreater(len(resp.candidates), 0)
        finally:
            self.engine.intent_classifier.classify_intent = orig_classify
            self.engine.retriever.retrieve = orig_retrieve
            self.engine.llm_client.generate_with_langchain = orig_generate

    def test_scenario_9_small_talk_and_special_queries(self):
        """Kịch bản 9: Kiểm tra các ý định Small Talk (Greeting, Thanks, Goodbye, Casual Chat, Ack, Bot Profile)."""
        test_cases = [
            ("Xin chào", "GREETING"),
            ("Chào bạn", "GREETING"),
            ("Cảm ơn bạn", "THANKS"),
            ("Thank you", "THANKS"),
            ("Tạm biệt", "GOODBYE"),
            ("Bạn khỏe không?", "CASUAL_CHAT"),
            ("Ok", "SIMPLE_ACKNOWLEDGEMENT"),
            ("Được rồi", "SIMPLE_ACKNOWLEDGEMENT"),
            ("Bạn là ai?", "CHATBOT_IDENTITY"),
            ("Bạn có thể làm gì?", "CHATBOT_CAPABILITIES"),
        ]
        for query, expected_intent in test_cases:
            with self.subTest(query=query):
                resp = self.engine.ask(query)
                self.assertIn(resp.mode, ["SMALL_TALK", "EXCEPTION_MATCH"])
                self.assertEqual(resp.intent, expected_intent)
                self.assertTrue(len(resp.answer) > 0)

    def test_scenario_10_small_talk_stream(self):
        """Kịch bản 10: Kiểm tra phản hồi stream đối với Small Talk câu hỏi ngoại lệ."""
        final_resp = None
        collected = []
        for chunk, resp in self.engine.ask_stream("Bạn là ai?"):
            collected.append(chunk)
            if resp:
                final_resp = resp

        self.assertIsNotNone(final_resp)
        self.assertIn(final_resp.mode, ["SMALL_TALK", "EXCEPTION_MATCH"])
        self.assertEqual(final_resp.intent, "CHATBOT_IDENTITY")
        self.assertTrue(len(final_resp.answer) > 0)

    def test_scenario_11_query_router_three_branches(self):
        """Kịch bản 11: Kiểm thử phân luồng 3 nhánh theo Architecture Lock:
        1. Small Talk -> Small Talk Handler
        2. Vocab Query -> PhoBERT + Hybrid Retrieval + RRF + Qwen
        3. Out of Scope -> Rejection mà không qua Hybrid Retrieval
        4. Ambiguous -> Clarification
        """
        # Nhánh 1: Small Talk
        resp_st = self.engine.ask("Xin chào")
        self.assertEqual(resp_st.mode, "SMALL_TALK")
        self.assertEqual(resp_st.intent, "GREETING")

        # Nhánh 2: Vocab Query
        resp_vq = self.engine.ask("abandon nghĩa là gì?")
        self.assertIn(resp_vq.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(resp_vq.word, "abandon")

        # Nhánh 3: Out of Scope
        resp_oos = self.engine.ask("Bitcoin hôm nay bao nhiêu?")
        self.assertEqual(resp_oos.mode, "NO_MATCH")
        self.assertEqual(resp_oos.intent, "OUT_OF_SCOPE")

        # Trường hợp mơ hồ thiếu thực thể khi chưa có ngữ cảnh
        self.engine.tracker.clear()
        resp_clarify = self.engine.ask("từ này nghĩa gì?")
        self.assertEqual(resp_clarify.mode, "CLARIFICATION")


if __name__ == "__main__":
    unittest.main()

