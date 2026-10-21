"""Unit tests kiểm thử UI Chat orchestration, streaming, thứ tự hiển thị và xử lý lỗi."""

import time
import unittest
from typing import Generator, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import streamlit as st

from src.core.models import ChatResponse, QARecord, RetrievalCandidate
from src.chat.engine import ChatEngine
from src.chat.topic_tracker import TopicTracker
from src.ui.app import (
    process_user_query,
    render_user_turn,
    render_assistant_turn,
)


class MockSessionState(dict):
    """Giả lập st.session_state cho kiểm thử đơn vị."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setgetattr__(self, key, value):
        self[key] = value

    def get(self, key, default=None):
        return super().get(key, default)


class TestChatUIStreaming(unittest.TestCase):
    def setUp(self):
        # Thiết lập session state giả lập
        self.mock_state = MockSessionState({
            "messages": [],
            "audit_logs": [],
            "status": "Sẵn sàng!",
            "is_processing": False,
            "dev_mode": False,
        })
        self.patcher_session = patch("streamlit.session_state", self.mock_state)
        self.patcher_session.start()

    def tearDown(self):
        self.patcher_session.stop()

    @patch("src.ui.app.render_user_turn")
    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.container")
    @patch("streamlit.empty")
    @patch("streamlit.write_stream")
    def test_01_new_question_displayed_before_backend_completion(
        self,
        mock_write_stream,
        mock_empty,
        mock_container,
        mock_columns,
        mock_chat_message,
        mock_render_user_turn,
    ):
        """Test 1 — Câu hỏi mới hiển thị trước khi backend hoàn tất:
        Xác minh user message được thêm vào session_state.messages và
        render_user_turn được gọi TRƯỚC KHI tác vụ ask_stream hoàn tất.
        """
        events = []
        mock_render_user_turn.side_effect = lambda content: events.append(f"user_rendered: {content}")

        mock_status = MagicMock()
        mock_status.markdown.side_effect = lambda *a, **kw: events.append("status_shown")
        mock_status.empty.side_effect = lambda: events.append("status_cleared")
        mock_empty.return_value = mock_status

        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_chat_message.return_value.__enter__ = MagicMock()
        mock_chat_message.return_value.__exit__ = MagicMock()
        mock_container.return_value.__enter__ = MagicMock()
        mock_container.return_value.__exit__ = MagicMock()

        def slow_ask_stream(query):
            events.append("ask_stream_started")
            # Kiểm tra ngay khi backend bắt đầu: tin nhắn người dùng PHẢI ĐÃ CÓ trong session_state
            self.assertEqual(len(self.mock_state.messages), 1)
            self.assertEqual(self.mock_state.messages[0]["content"], query)
            yield "Chunk 1", None
            yield "Chunk 2", None
            resp = ChatResponse(answer="Chunk 1Chunk 2", mode="RAG_GENERATION", latency_ms=10.0)
            events.append("ask_stream_finished")
            yield "", resp

        mock_engine = MagicMock(spec=ChatEngine)
        mock_engine.ask_stream.side_effect = slow_ask_stream

        def fake_write_stream(generator):
            tokens = []
            for t in generator:
                tokens.append(t)
            return "".join(tokens)

        mock_write_stream.side_effect = fake_write_stream

        query = "about nghĩa là gì?"
        process_user_query(clean_input=query, chat_engine=mock_engine)

        # Thứ tự sự kiện bắt buộc:
        # 1. render user
        # 2. hiển thị status placeholder
        # 3. ask_stream bắt đầu
        # 4. ask_stream hoàn tất
        self.assertIn(f"user_rendered: {query}", events)
        self.assertIn("status_shown", events)
        self.assertIn("ask_stream_started", events)
        self.assertIn("ask_stream_finished", events)

        user_render_idx = events.index(f"user_rendered: {query}")
        status_shown_idx = events.index("status_shown")
        stream_start_idx = events.index("ask_stream_started")
        stream_finish_idx = events.index("ask_stream_finished")

        self.assertLess(user_render_idx, stream_start_idx)
        self.assertLess(status_shown_idx, stream_start_idx)
        self.assertLess(stream_start_idx, stream_finish_idx)

    @patch("src.ui.app.render_user_turn")
    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.container")
    @patch("streamlit.empty")
    @patch("streamlit.write_stream")
    def test_02_streaming_multiple_chunks_in_order(
        self,
        mock_write_stream,
        mock_empty,
        mock_container,
        mock_columns,
        mock_chat_message,
        mock_render_user_turn,
    ):
        """Test 2 — Streaming nhiều chunk:
        Xác minh giao diện tiêu thụ các chunk theo thứ tự và không bị trùng lặp.
        """
        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_status = MagicMock()
        mock_empty.return_value = mock_status

        mock_engine = MagicMock(spec=ChatEngine)
        expected_chunks = ["Từ ", "này ", "nghĩa ", "là ", "về."]
        final_meta = ChatResponse(answer="Từ này nghĩa là về.", mode="RAG_GENERATION", latency_ms=12.0)

        def mock_stream(query):
            for c in expected_chunks:
                yield c, None
            yield "", final_meta

        mock_engine.ask_stream.side_effect = mock_stream

        consumed_chunks = []
        def capture_write_stream(stream_gen):
            for chunk in stream_gen:
                consumed_chunks.append(chunk)
            return "".join(consumed_chunks)

        mock_write_stream.side_effect = capture_write_stream

        process_user_query(clean_input="about nghĩa là gì?", chat_engine=mock_engine)

        self.assertEqual(consumed_chunks, expected_chunks)
        self.assertEqual(self.mock_state.messages[-1]["content"], "Từ này nghĩa là về.")
        self.assertEqual(self.mock_state.messages[-1]["meta"], final_meta)

    @patch("src.ui.app.render_user_turn")
    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.container")
    @patch("streamlit.empty")
    @patch("streamlit.write_stream")
    def test_03_second_question_immediate_display(
        self,
        mock_write_stream,
        mock_empty,
        mock_container,
        mock_columns,
        mock_chat_message,
        mock_render_user_turn,
    ):
        """Test 3 — Câu hỏi thứ hai:
        Sau khi lượt 1 hoàn thành, gửi tiếp câu hỏi thứ 2.
        Xác minh câu hỏi 2 xuất hiện ngay trong state và giao diện trước khi backend lượt 2 hoàn tất.
        """
        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_status = MagicMock()
        mock_empty.return_value = mock_status
        mock_write_stream.side_effect = lambda gen: "".join([t for t in gen])

        mock_engine = MagicMock(spec=ChatEngine)

        # Lượt 1
        resp_1 = ChatResponse(answer="Nghĩa của about là...", mode="DIRECT_MATCH")
        mock_engine.ask_stream.return_value = iter([("Nghĩa của about là...", resp_1)])
        process_user_query(clean_input="about là gì?", chat_engine=mock_engine)

        self.assertEqual(len(self.mock_state.messages), 2)
        self.assertEqual(self.mock_state.messages[0]["content"], "about là gì?")
        self.assertEqual(self.mock_state.messages[1]["content"], "Nghĩa của about là...")

        # Lượt 2
        query_2 = "cho tôi câu ví dụ của từ này"
        turn_2_started = []

        def turn_2_stream(q):
            turn_2_started.append(True)
            # Tại thời điểm lượt 2 vừa bắt đầu: câu hỏi 2 ĐÃ PHẢI CÓ trong messages (tổng là 3 tin nhắn: U1, A1, U2)
            self.assertEqual(len(self.mock_state.messages), 3)
            self.assertEqual(self.mock_state.messages[2]["role"], "user")
            self.assertEqual(self.mock_state.messages[2]["content"], query_2)
            yield "Ví dụ: What is it about?", ChatResponse(answer="Ví dụ: What is it about?", mode="DIRECT_MATCH")

        mock_engine.ask_stream.side_effect = turn_2_stream
        process_user_query(clean_input=query_2, chat_engine=mock_engine)

        self.assertTrue(turn_2_started[0])
        self.assertEqual(len(self.mock_state.messages), 4)
        self.assertEqual(self.mock_state.messages[2]["content"], query_2)
        self.assertEqual(self.mock_state.messages[3]["content"], "Ví dụ: What is it about?")

    @patch("src.ui.app.render_user_turn")
    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.container")
    @patch("streamlit.empty")
    @patch("streamlit.write_stream")
    def test_04_no_duplicates_in_history(
        self,
        mock_write_stream,
        mock_empty,
        mock_container,
        mock_columns,
        mock_chat_message,
        mock_render_user_turn,
    ):
        """Test 4 — Không duplicate:
        Xác minh mỗi lượt chỉ tạo đúng 1 user message và 1 assistant message.
        """
        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_status = MagicMock()
        mock_empty.return_value = mock_status
        mock_write_stream.side_effect = lambda gen: "".join([t for t in gen])

        mock_engine = MagicMock(spec=ChatEngine)
        resp = ChatResponse(answer="Phản hồi kiểm tra", mode="DIRECT_MATCH")
        mock_engine.ask_stream.return_value = iter([("Phản hồi kiểm tra", resp)])

        # Chạy 3 lượt
        for i in range(1, 4):
            process_user_query(clean_input=f"Câu hỏi {i}", chat_engine=mock_engine)
            # Số tin nhắn phải tăng chính xác 2 mỗi lượt
            self.assertEqual(len(self.mock_state.messages), i * 2)
            self.assertEqual(self.mock_state.messages[(i - 1) * 2]["role"], "user")
            self.assertEqual(self.mock_state.messages[(i - 1) * 2 + 1]["role"], "assistant")

    @patch("src.ui.app.render_user_turn")
    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.container")
    @patch("streamlit.empty")
    @patch("streamlit.write_stream")
    def test_05_backend_error_handling(
        self,
        mock_write_stream,
        mock_empty,
        mock_container,
        mock_columns,
        mock_chat_message,
        mock_render_user_turn,
    ):
        """Test 5 — Lỗi backend:
        Giả lập lỗi trong backend.
        Xác minh user message vẫn tồn tại, assistant hiển thị lỗi và loading kết thúc.
        """
        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_status = MagicMock()
        mock_empty.return_value = mock_status

        mock_engine = MagicMock(spec=ChatEngine)
        mock_engine.ask_stream.side_effect = ConnectionError("Ollama offline")
        mock_write_stream.side_effect = ConnectionError("Ollama offline")

        process_user_query(clean_input="test lỗi", chat_engine=mock_engine)

        # 1. User message vẫn tồn tại nguyên vẹn
        self.assertEqual(len(self.mock_state.messages), 2)
        self.assertEqual(self.mock_state.messages[0]["role"], "user")
        self.assertEqual(self.mock_state.messages[0]["content"], "test lỗi")

        # 2. Assistant hiển thị thông báo lỗi phù hợp
        bot_msg = self.mock_state.messages[1]
        self.assertEqual(bot_msg["role"], "assistant")
        self.assertIn("Không thể kết nối", bot_msg["content"])
        self.assertEqual(bot_msg["meta"].mode, "ERROR")

        # 3. Status loading placeholder đã được dọn sạch
        self.assertTrue(mock_status.empty.called)
        # 4. is_processing được trả về False
        self.assertFalse(self.mock_state.is_processing)

    def test_06_multi_turn_topic_tracker_context(self):
        """Test 6 — Multi-turn context:
        Kiểm tra TopicTracker duy trì đúng từ vựng qua nhiều lượt hỏi.
        """
        records = [
            QARecord(id="V1", sheet="s", question="about nghĩa là gì?", answer="Về, khoảng", word="about", source="d"),
            QARecord(id="V2", sheet="s", question="book nghĩa là gì?", answer="Quyển sách", word="book", source="d"),
        ]
        tracker = TopicTracker(records=records)

        # Turn 1: Hỏi từ 'about'
        res1, word1, is_followup1, is_ambig1 = tracker.resolve_query("about nghĩa là gì?")
        self.assertEqual(word1, "about")
        tracker.active_word = "about"

        # Turn 2: Hỏi tiếp nối 'từ này'
        res2, word2, is_followup2, is_ambig2 = tracker.resolve_query("cho tôi câu ví dụ của từ này")
        self.assertTrue(is_followup2)
        self.assertIn("about", res2)

        # Turn 3: Hỏi tiếp 'còn trình độ của nó thì sao?'
        res3, word3, is_followup3, is_ambig3 = tracker.resolve_query("còn trình độ của nó thì sao?")
        self.assertTrue(is_followup3)
        self.assertIn("about", res3)

        # Turn 4: Đổi chủ đề sang từ 'book'
        res4, word4, is_followup4, is_ambig4 = tracker.resolve_query("book nghĩa là gì?")
        self.assertEqual(word4, "book")
        tracker.active_word = "book"
        self.assertEqual(tracker.active_word, "book")

    def test_07_streaming_and_fallback_logic(self):
        """Test 7 — Streaming và fallback:
        - Nếu stream thất bại trước khi có nội dung: fallback chạy.
        - Nếu đã phát ra một phần nội dung: không restart generation gây duplicate.
        """
        records = [
            QARecord(id="V1", sheet="s", question="about nghĩa là gì?", answer="Về", word="about", source="d")
        ]
        engine = ChatEngine(records=records)
        engine._is_initialized = True

        # Mock hybrid retriever
        candidate = RetrievalCandidate(
            record=records[0],
            bm25_score=1.0,
            bge_score=1.0,
            rrf_score=0.9,
            method="HYBRID"
        )
        engine.retriever = MagicMock()
        engine.retriever.retrieve.return_value = ("RAG_GENERATION", candidate, [candidate])

        # Case A: LCEL lỗi ngay từ đầu (chưa yield token nào) -> fallback sang stream_chat
        engine.llm_client = MagicMock()
        engine.llm_client.generate_with_langchain_stream.side_effect = RuntimeError("LCEL timeout")
        engine.llm_client.stream_chat.return_value = iter(["Fallback ", "response"])

        stream_gen = engine.ask_stream("about là gì?")
        emitted_tokens = []
        for token, meta in stream_gen:
            if token:
                emitted_tokens.append(token)

        self.assertIn("Fallback ", emitted_tokens)
        self.assertIn("response", emitted_tokens)

        # Case B: LCEL đã yield 2 token rồi mới bị ngắt -> không gọi stream_chat để tránh trùng lặp
        def partial_stream(*args, **kwargs):
            yield "Partial 1 "
            yield "Partial 2 "
            raise RuntimeError("Stream disconnected")

        engine.llm_client.generate_with_langchain_stream.side_effect = partial_stream
        engine.llm_client.stream_chat.reset_mock()

        stream_gen_b = engine.ask_stream("about là gì?")
        emitted_b = []
        for token, meta in stream_gen_b:
            if token:
                emitted_b.append(token)

        # Không được gọi fallback stream_chat
        self.assertFalse(engine.llm_client.stream_chat.called)
        # Token đã phát ra không bị xóa, và có thông báo lỗi gián đoạn
        all_text_b = "".join(emitted_b)
        self.assertIn("Partial 1", all_text_b)
        self.assertIn("Partial 2", all_text_b)
        self.assertIn("Quá trình truyền dữ liệu bị gián đoạn", all_text_b)

    @patch("streamlit.chat_message")
    @patch("streamlit.columns")
    @patch("streamlit.markdown")
    def test_08_user_icon_replaces_ban_label(
        self,
        mock_markdown,
        mock_columns,
        mock_chat_message,
    ):
        """Test 8 — Icon người dùng thay thế nhãn 'BẠN':
        Xác minh HTML render cho user message:
        - Sử dụng đúng icon hình người có sẵn (user-turn-avatar).
        - Tuyệt đối không chứa chữ 'BẠN'.
        """
        mock_columns.return_value = (MagicMock(), MagicMock())
        mock_chat_message.return_value.__enter__ = MagicMock()
        mock_chat_message.return_value.__exit__ = MagicMock()

        rendered_html = []
        mock_markdown.side_effect = lambda html_text, *a, **kw: rendered_html.append(html_text)

        render_user_turn("Kiểm tra câu hỏi của người dùng")

        self.assertTrue(len(rendered_html) > 0)
        full_html = "".join(rendered_html)

        # 1. Chữ 'BẠN' đã bị xóa hoàn toàn khỏi vùng hiển thị
        self.assertNotIn("BẠN", full_html)

        # 2. Icon người dùng có sẵn (user-turn-avatar) xuất hiện tại vị trí tác giả kèm kích thước 32px
        self.assertIn("user-turn-author", full_html)
        self.assertIn("user-turn-avatar", full_html)
        self.assertIn("32", full_html)

        # 3. Nội dung câu hỏi vẫn hiển thị đầy đủ
        self.assertIn("Kiểm tra câu hỏi của người dùng", full_html)


if __name__ == "__main__":
    unittest.main()
