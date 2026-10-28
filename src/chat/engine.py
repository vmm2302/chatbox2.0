"""Module điều phối trung tâm của Master Architecture (Chat Engine).

Liên kết chặt chẽ toàn bộ các tầng xử lý:
1. TopicTracker: Theo dõi thực thể active_word, khôi phục câu hỏi follow-up, phát hiện câu hỏi mơ hồ.
2. PhoBERTIntentClassifier: Phân tích ý định qua biểu diễn vector ngữ cảnh và Intent Prototypes.
3. HybridRetriever: Tìm kiếm kết hợp BM25 (từ khóa) + BGE-M3 (ngữ nghĩa) và hợp nhất RRF (k=60).
4. Threshold & Domain Gate: Phân loại DIRECT_MATCH, RAG_GENERATION, CLARIFICATION, NO_MATCH.
5. LangChain Grounded LLM: Sinh phản hồi chuẩn hóa qua Qwen2.5:7B (Ollama cục bộ), không suy diễn ngoài context.
6. Lịch sử hội thoại & Provenance Metadata: Theo dõi nguồn gốc, latency và điểm số phục vụ audit.
"""

import logging
import time
from typing import Generator, List, Optional, Tuple

from config.settings import settings
from src.chat.exception_handler import ExceptionHandler
from src.chat.query_router import QueryRouter
from src.chat.response_formatter import format_vocabulary_response
from src.chat.small_talk_handler import SmallTalkHandler
from src.chat.topic_tracker import TopicTracker
from src.core.models import ChatResponse, QARecord, ResponseMode, RetrievalCandidate
from src.data.loader import QALoader, normalize_query_text
from src.llm.client import OllamaClient
from src.llm.prompts import build_context_string, build_rag_prompt
from src.nlp.phobert_intent import PhoBERTIntentClassifier
from src.retriever.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

CLARIFICATION_MESSAGE = (
    "Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé!"
)


class ChatEngine:
    """Động cơ điều phối chính của chatbot tra cứu từ vựng tiếng Anh."""

    def __init__(
        self,
        records: Optional[List[QARecord]] = None,
        retriever: Optional[HybridRetriever] = None,
        intent_classifier: Optional[PhoBERTIntentClassifier] = None,
        llm_client: Optional[OllamaClient] = None,
        tracker: Optional[TopicTracker] = None,
        exception_handler: Optional[ExceptionHandler] = None,
        small_talk_handler: Optional[SmallTalkHandler] = None,
        query_router: Optional[QueryRouter] = None,
    ):
        # 0. Bộ điều phối Query Router và xử lý Small Talk (Architecture Lock)
        self.small_talk_handler = small_talk_handler or exception_handler or SmallTalkHandler()
        self.exception_handler = self.small_talk_handler
        self.query_router = query_router or QueryRouter(small_talk_handler=self.small_talk_handler)

        # 1. Nạp tri thức Q&A
        if records is None:
            loader = QALoader()
            self.records = loader.get_or_create_records()
        else:
            self.records = records

        # 2. Bộ theo dõi chủ đề và ngữ cảnh hội thoại
        self.tracker = tracker or TopicTracker(records=self.records)

        # 3. Bộ tìm kiếm Hybrid (BM25 + BGE-M3 + RRF)
        self.retriever = retriever or HybridRetriever(self.records)

        # 4. Bộ phân loại ý định PhoBERT
        self.intent_classifier = intent_classifier or PhoBERTIntentClassifier()

        # 5. LLM Client giao tiếp Ollama
        self.llm_client = llm_client or OllamaClient()

        self._is_initialized = False

    @property
    def hybrid_retriever(self) -> HybridRetriever:
        return self.retriever

    @property
    def bge_retriever(self):
        return self.retriever.bge_chroma

    @property
    def bm25_retriever(self):
        return self.retriever.bm25_retriever

    def warm_up(self) -> None:
        """Khởi động toàn bộ chỉ mục BM25, ChromaDB và PhoBERT."""
        if not self._is_initialized:
            logger.info("Đang khởi tạo các thành phần trong ChatEngine...")
            self.retriever.initialize()
            self.intent_classifier.initialize()
            self._is_initialized = True
            logger.info("ChatEngine đã sẵn sàng phục vụ 100% offline.")

    def update_knowledge_base(self, new_records: List[QARecord]) -> None:
        """Cập nhật dữ liệu tri thức mới cho toàn bộ pipeline dưới khóa ghi độc quyền an toàn."""
        from src.resource.manager import get_resource_manager
        with get_resource_manager().coordinator.write_lock():
            self.records = new_records
            self.retriever.reload(new_records)
            self.tracker.load_known_words(new_records)
            if not new_records:
                self.tracker.clear()
            logger.info("ChatEngine đã đồng bộ thành công %d bản ghi tri thức mới.", len(new_records))

    def clear_knowledge_base(self) -> None:
        """Đưa ChatEngine và toàn bộ pipeline RAG về trạng thái rỗng an toàn."""
        from src.resource.manager import get_resource_manager
        with get_resource_manager().coordinator.write_lock():
            self.records = []
            self.retriever.reload([])
            self.tracker.load_known_words([])
            self.tracker.clear()
            logger.info("ChatEngine: Đã làm sạch toàn bộ tri thức và ngữ cảnh hội thoại.")


    def _create_and_log_response(
        self,
        clean_query: str,
        resolved_query: str,
        intent: str,
        answer: str,
        mode: ResponseMode,
        start_time: float,
        active_word: Optional[str] = None,
        candidate: Optional[RetrievalCandidate] = None,
        candidates: Optional[List[RetrievalCandidate]] = None,
        tracker: Optional[TopicTracker] = None,
    ) -> ChatResponse:
        """Ghi nhận lượt hội thoại vào TopicTracker và đóng gói kết quả ChatResponse."""
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        matched_id = candidate.record.record_id if candidate else None
        active_trk = tracker if tracker is not None else self.tracker
        active_trk.add_turn(
            user_query=clean_query,
            resolved_query=resolved_query,
            intent=intent,
            active_word=active_word,
            answer=answer,
            mode=mode,
            matched_record_id=matched_id,
        )
        return ChatResponse(
            answer=answer,
            mode=mode,
            record_id=matched_id,
            word=candidate.record.word if candidate else None,
            source=candidate.record.source if candidate else None,
            sheet=candidate.record.sheet if candidate else None,
            bm25_score=candidate.bm25_score if candidate else 0.0,
            bge_score=candidate.bge_score if candidate else 0.0,
            rrf_score=candidate.rrf_score if candidate else 0.0,
            intent=intent,
            latency_ms=round(elapsed_ms, 2),
            candidates=candidates if candidates is not None else [],
        )

    def ask(self, query: str, tracker: Optional[TopicTracker] = None) -> ChatResponse:
        """Xử lý câu hỏi người dùng ở chế độ đồng bộ (hỗ trợ session tracker cô lập)."""
        start_time = time.perf_counter()
        clean_query, normalized_query = normalize_query_text(query)
        active_tracker = tracker if tracker is not None else self.tracker

        if not clean_query:
            return ChatResponse(
                answer="Vui lòng nhập câu hỏi.",
                mode="NO_MATCH",
                latency_ms=0.0
            )

        # Kiểm tra trạng thái điều phối tài nguyên
        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()
        if rm.state in (ResourceState.INDEXING_GPU, ResourceState.RESTORING_CHAT):
            return ChatResponse(
                answer="⚠️ Hệ thống đang đồng bộ dữ liệu chỉ mục và điều phối tài nguyên. Vui lòng thử lại sau vài giây.",
                mode="NO_MATCH",
                latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )

        self.warm_up()

        # Bước 1: Query Router điều phối 3 nhánh (Small Talk, Out of Scope, Vocab Query)
        routing = self.query_router.route(normalized_query, active_tracker)

        # 1.1 NHÁNH SMALL TALK: Phản hồi xã giao không đưa vào Hybrid Retrieval
        if routing.route_type == "SMALL_TALK":
            answer = self.small_talk_handler.handle(
                query=clean_query,
                intent=routing.intent,
                template_response=routing.template_response,
                use_llm=False,
                llm_client=self.llm_client
            )
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent=routing.intent,
                answer=answer,
                mode="SMALL_TALK",
                start_time=start_time,
                active_word=active_tracker.active_word,
                tracker=active_tracker,
            )

        # 1.2 Kiểm tra Knowledge Base rỗng (Empty Knowledge Base Gate)
        if len(self.records) == 0:
            empty_ans = getattr(settings, "EMPTY_KB_RESPONSE", "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này. Vui lòng nạp thêm tài liệu vào hệ thống.")
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent="EMPTY_KB",
                answer=empty_ans,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )

        # 1.3 NHÁNH OUT OF SCOPE: Từ chối câu hỏi ngoài phạm vi không đưa vào Hybrid Retrieval
        if routing.route_type == "OUT_OF_SCOPE":
            answer = routing.template_response or settings.OUT_OF_SCOPE_RESPONSE
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent="OUT_OF_SCOPE",
                answer=answer,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                tracker=active_tracker,
            )

        # 1.4 NHÁNH VOCAB QUERY: Thực hiện tuần tự Sequential Pipeline
        # Bước 2: Quản lý ngữ cảnh và phân giải thực thể qua TopicTracker
        resolved_query, target_word, is_follow_up, is_ambiguous = active_tracker.resolve_query(clean_query)

        # Bước 2: Xử lý trạng thái MƠ HỒ (Thiếu từ vựng và chưa có active_word)
        if is_ambiguous:
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )

        # Bước 3: Phân loại ý định qua PhoBERT
        has_active_topic = bool(active_tracker.active_word)
        intent_res = self.intent_classifier.classify_intent(
            resolved_query,
            has_active_topic=has_active_topic,
            tracker=active_tracker
        )

        # Nếu PhoBERT phát hiện mơ hồ
        if intent_res.is_ambiguous:
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )

        # Nếu câu hỏi hoàn toàn ngoài phạm vi (OUT_OF_SCOPE) và không có từ tiếng Anh nào được phát hiện
        if intent_res.intent == "OUT_OF_SCOPE" and not target_word and not active_tracker.active_word:
            if not any(token.lower().strip("?,.!") in active_tracker.vocab_words for token in clean_query.split()):
                return self._create_and_log_response(
                    clean_query=clean_query,
                    resolved_query=resolved_query,
                    intent="OUT_OF_SCOPE",
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH",
                    start_time=start_time,
                    active_word=None,
                    tracker=active_tracker,
                )

        # Bước 4: Truy xuất Hybrid dưới khóa đọc IndexAccessCoordinator
        # Khóa đọc CHỈ GIỮ trong giai đoạn truy xuất dữ liệu (~150ms), cho phép nhiều người đọc đồng thời
        with rm.coordinator.read_lock():
            mode, best_candidate, candidates = self.retriever.retrieve(
                resolved_query,
                top_k=settings.TOP_K_RETRIEVAL
            )
            # Trích xuất ngữ cảnh bất biến ngay trong khóa đọc
            context_str = build_context_string(candidates) if candidates else ""

        # Nếu người dùng chỉ định rõ target_word và trong top candidates có bản ghi khớp chính xác target_word
        if target_word and candidates:
            exact_target_match = next((c for c in candidates if c.record.word and c.record.word.strip().lower() == target_word.strip().lower()), None)
            if exact_target_match:
                best_candidate = exact_target_match

        # KHÓA ĐỌC ĐÃ ĐƯỢC NHẢ TẠI ĐÂY!
        # Bước 5: Kiểm tra Domain & Threshold Gate
        if not candidates or best_candidate is None or mode == "NO_MATCH":
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                candidates=candidates,
                tracker=active_tracker,
            )

        # Cập nhật thực thể đang nói đến nếu tìm được ứng viên phù hợp
        if best_candidate.record.word:
            active_tracker.active_word = best_candidate.record.word.strip().lower()

        # Bước 6: Xử lý theo Response Mode
        query_word = best_candidate.record.word if (best_candidate and best_candidate.record.word) else target_word

        # 6.1 Khớp chính xác (DIRECT_MATCH)
        if mode == "DIRECT_MATCH":
            answer = format_vocabulary_response(best_candidate.record.answer, word=query_word)
            return self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                answer=answer,
                mode="DIRECT_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                candidate=best_candidate,
                candidates=candidates,
                tracker=active_tracker,
            )

        # 6.2 Tổng hợp và diễn đạt qua LLM (RAG_GENERATION) hoàn toàn NGOÀI khóa dữ liệu
        try:
            llm_answer = self.llm_client.generate_with_langchain(
                question=resolved_query,
                context=context_str
            )
        except Exception as err:
            logger.warning("Lỗi LangChain LCEL, chuyển sang HTTP chat client: %s", err)
            try:
                messages = build_rag_prompt(resolved_query, candidates)
                llm_answer = self.llm_client.chat(messages)
            except Exception as final_err:
                logger.error("Lỗi khi gọi Qwen2.5:7B: %s", final_err)
                llm_answer = f"{settings.OLLAMA_OFFLINE_RESPONSE}\n(Chi tiết: {final_err})"

        formatted_answer = format_vocabulary_response(llm_answer, word=query_word)
        return self._create_and_log_response(
            clean_query=clean_query,
            resolved_query=resolved_query,
            intent=intent_res.intent,
            answer=formatted_answer,
            mode="RAG_GENERATION",
            start_time=start_time,
            active_word=active_tracker.active_word,
            candidate=best_candidate,
            candidates=candidates,
            tracker=active_tracker,
        )


    def ask_stream(
        self,
        query: str,
        tracker: Optional[TopicTracker] = None,
    ) -> Generator[Tuple[str, Optional[ChatResponse]], None, None]:
        """Xử lý câu hỏi người dùng theo dạng stream token phục vụ UI (hỗ trợ session tracker cô lập)."""
        start_time = time.perf_counter()
        clean_query, normalized_query = normalize_query_text(query)
        active_tracker = tracker if tracker is not None else self.tracker

        if not clean_query:
            resp = ChatResponse(
                answer="Vui lòng nhập câu hỏi.",
                mode="NO_MATCH",
                latency_ms=0.0
            )
            yield resp.answer, resp
            return

        # Kiểm tra trạng thái điều phối tài nguyên
        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()
        if rm.state in (ResourceState.INDEXING_GPU, ResourceState.RESTORING_CHAT):
            resp = ChatResponse(
                answer="⚠️ Hệ thống đang đồng bộ dữ liệu chỉ mục và điều phối tài nguyên. Vui lòng thử lại sau vài giây.",
                mode="NO_MATCH",
                latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )
            yield resp.answer, resp
            return

        self.warm_up()

        # Bước 1: Query Router điều phối 3 nhánh (Small Talk, Out of Scope, Vocab Query)
        routing = self.query_router.route(normalized_query, active_tracker)

        # 1.1 NHÁNH SMALL TALK: Phản hồi xã giao không đưa vào Hybrid Retrieval
        if routing.route_type == "SMALL_TALK":
            answer = self.small_talk_handler.handle(
                query=clean_query,
                intent=routing.intent,
                template_response=routing.template_response,
                use_llm=False,
                llm_client=self.llm_client
            )
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent=routing.intent,
                answer=answer,
                mode="SMALL_TALK",
                start_time=start_time,
                active_word=active_tracker.active_word,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        # 1.2 Kiểm tra Knowledge Base rỗng (Empty Knowledge Base Gate)
        if len(self.records) == 0:
            empty_ans = getattr(settings, "EMPTY_KB_RESPONSE", "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này. Vui lòng nạp thêm tài liệu vào hệ thống.")
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent="EMPTY_KB",
                answer=empty_ans,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        # 1.3 NHÁNH OUT OF SCOPE: Từ chối câu hỏi ngoài phạm vi không đưa vào Hybrid Retrieval
        if routing.route_type == "OUT_OF_SCOPE":
            answer = routing.template_response or settings.OUT_OF_SCOPE_RESPONSE
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=clean_query,
                intent="OUT_OF_SCOPE",
                answer=answer,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        # 1.4 NHÁNH VOCAB QUERY: Thực hiện tuần tự Sequential Pipeline
        # Bước 2: Quản lý ngữ cảnh và phân giải thực thể qua TopicTracker
        resolved_query, target_word, is_follow_up, is_ambiguous = active_tracker.resolve_query(clean_query)

        # Bước 2: Kiểm tra MƠ HỒ
        if is_ambiguous:
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        # Bước 3: Phân loại ý định
        intent_res = self.intent_classifier.classify_intent(
            resolved_query,
            has_active_topic=bool(active_tracker.active_word),
            tracker=active_tracker
        )

        if intent_res.is_ambiguous:
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                start_time=start_time,
                active_word=None,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        if intent_res.intent == "OUT_OF_SCOPE" and not target_word and not active_tracker.active_word:
            if not any(token.lower().strip("?,.!") in active_tracker.vocab_words for token in clean_query.split()):
                resp = self._create_and_log_response(
                    clean_query=clean_query,
                    resolved_query=resolved_query,
                    intent="OUT_OF_SCOPE",
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH",
                    start_time=start_time,
                    active_word=None,
                    tracker=active_tracker,
                )
                yield resp.answer, resp
                return

        # Bước 4: Truy xuất Hybrid dưới khóa đọc IndexAccessCoordinator
        # Khóa đọc CHỈ GIỮ trong giai đoạn truy xuất dữ liệu (~150ms), cho phép nhiều người đọc đồng thời
        with rm.coordinator.read_lock():
            mode, best_candidate, candidates = self.retriever.retrieve(
                resolved_query,
                top_k=settings.TOP_K_RETRIEVAL
            )
            context_str = build_context_string(candidates) if candidates else ""
            messages = build_rag_prompt(resolved_query, candidates) if candidates else []

        # Nếu người dùng chỉ định rõ target_word và trong top candidates có bản ghi khớp chính xác target_word
        if target_word and candidates:
            exact_target_match = next((c for c in candidates if c.record.word and c.record.word.strip().lower() == target_word.strip().lower()), None)
            if exact_target_match:
                best_candidate = exact_target_match

        # KHÓA ĐỌC ĐÃ ĐƯỢC NHẢ TẠI ĐÂY!
        # Bước 5: Threshold Gate
        if not candidates or best_candidate is None or mode == "NO_MATCH":
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                candidates=candidates,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        if best_candidate.record.word:
            active_tracker.active_word = best_candidate.record.word.strip().lower()

        query_word = best_candidate.record.word if (best_candidate and best_candidate.record.word) else target_word

        # 6.1 DIRECT_MATCH
        if mode == "DIRECT_MATCH":
            answer = format_vocabulary_response(best_candidate.record.answer, word=query_word)
            resp = self._create_and_log_response(
                clean_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                answer=answer,
                mode="DIRECT_MATCH",
                start_time=start_time,
                active_word=active_tracker.active_word,
                candidate=best_candidate,
                candidates=candidates,
                tracker=active_tracker,
            )
            yield resp.answer, resp
            return

        # 6.2 RAG_GENERATION (Streaming từ LangChain LCEL hoàn toàn NGOÀI khóa dữ liệu)
        accumulated_text = ""
        try:
            for token in self.llm_client.generate_with_langchain_stream(resolved_query, context_str):
                accumulated_text += token
                yield token, None
        except Exception as lcel_err:
            logger.warning("Lỗi LangChain LCEL streaming: %s", lcel_err)
            if not accumulated_text:
                # Chỉ kích hoạt fallback sang HTTP stream client khi chưa có token nào được phát ra
                logger.info("Chuyển sang HTTP stream client fallback...")
                try:
                    for token in self.llm_client.stream_chat(messages):
                        accumulated_text += token
                        yield token, None
                except Exception as err:
                    error_msg = f"\n{settings.OLLAMA_OFFLINE_RESPONSE}\n({err})"
                    accumulated_text += error_msg
                    yield error_msg, None
            else:
                # Đã phát ra một phần nội dung: không gọi lại từ đầu để tránh trùng lặp nội dung
                error_msg = f"\n\n⚠️ Quá trình truyền dữ liệu bị gián đoạn: {lcel_err}"
                accumulated_text += error_msg
                yield error_msg, None


        formatted_final = format_vocabulary_response(accumulated_text, word=query_word)
        final_resp = self._create_and_log_response(
            clean_query=clean_query,
            resolved_query=resolved_query,
            intent=intent_res.intent,
            answer=formatted_final,
            mode="RAG_GENERATION",
            start_time=start_time,
            active_word=active_tracker.active_word,
            candidate=best_candidate,
            candidates=candidates,
            tracker=active_tracker,
        )
        yield "", final_resp


# ==============================================================================
# SINGLETON CHAT ENGINE & BACKGROUND WARM-UP COORDINATOR
# ==============================================================================

import concurrent.futures
import threading

_shared_engine_lock = threading.Lock()
_shared_engine_instance: Optional[ChatEngine] = None
_shared_engine_future: Optional[concurrent.futures.Future] = None
_shared_warmup_error: Optional[str] = None
_shared_warmup_started: bool = False


def start_engine_warmup() -> None:
    """Kích hoạt tác vụ nạp và làm nóng ChatEngine dưới luồng nền (idempotent, cùng tiến trình)."""
    global _shared_warmup_started, _shared_engine_future
    with _shared_engine_lock:
        if _shared_warmup_started or _shared_engine_instance is not None:
            return
        _shared_warmup_started = True
        fut = concurrent.futures.Future()
        _shared_engine_future = fut

    def _worker():
        global _shared_engine_instance, _shared_warmup_error
        try:
            t0 = time.perf_counter()
            logger.info("[WARMUP] Bắt đầu khởi tạo ChatEngine trong tiến trình nền...")
            eng = ChatEngine()
            eng.warm_up()
            with _shared_engine_lock:
                _shared_engine_instance = eng
            fut.set_result(eng)
            logger.info("[WARMUP] ChatEngine đã sẵn sàng sau %.3f giây.", time.perf_counter() - t0)
        except Exception as exc:
            err_msg = str(exc)
            logger.error("[WARMUP] Lỗi khi nạp ChatEngine dưới nền: %s", exc, exc_info=True)
            with _shared_engine_lock:
                _shared_warmup_error = err_msg
            fut.set_exception(exc)

    t = threading.Thread(target=_worker, name="chatbox-engine-warmup", daemon=True)
    t.start()


def get_engine_state() -> Tuple[str, Optional[str]]:
    """Trả về trạng thái hiện tại của ChatEngine và thông báo lỗi (nếu có).

    Returns:
        (state, error):
        - ("READY", None): Động cơ AI đã sẵn sàng phục vụ.
        - ("ERROR", error_msg): Khởi tạo gặp lỗi, không thể phục vụ.
        - ("WARMING_UP", None): Đang nạp mô hình dưới luồng nền.
        - ("NOT_STARTED", None): Chưa kích hoạt khởi tạo.
    """
    global _shared_engine_instance, _shared_engine_future, _shared_warmup_error, _shared_warmup_started
    with _shared_engine_lock:
        if _shared_engine_instance is not None:
            return "READY", None
        if _shared_warmup_error is not None:
            return "ERROR", _shared_warmup_error
        fut = _shared_engine_future

    if fut is not None:
        if fut.done():
            exc = fut.exception()
            if exc is not None:
                err_msg = str(exc)
                with _shared_engine_lock:
                    _shared_warmup_error = err_msg
                return "ERROR", err_msg
            return "READY", None
        return "WARMING_UP", None

    if _shared_warmup_started:
        return "WARMING_UP", None

    return "NOT_STARTED", None


def is_engine_ready() -> bool:
    """Kiểm tra ChatEngine đã hoàn tất khởi tạo và sẵn sàng phục vụ chưa."""
    state, _ = get_engine_state()
    return state == "READY"


def get_shared_chat_engine(timeout: Optional[float] = None) -> ChatEngine:
    """Trả về singleton ChatEngine dùng chung, đồng bộ an toàn qua Future/Lock.

    - Nếu đã sẵn sàng: Trả về ngay lập tức (O(1)).
    - Nếu đang nạp nền: Chờ tối đa `timeout` giây (nếu truyền).
    - Nếu gặp lỗi: Ném ngoại lệ rõ ràng, tuyệt đối không lặp lại vô hạn.
    - Nếu chưa warm-up: Khởi tạo một lần an toàn trong lock.
    """
    global _shared_engine_instance, _shared_engine_future, _shared_warmup_error
    with _shared_engine_lock:
        if _shared_engine_instance is not None:
            return _shared_engine_instance
        if _shared_warmup_error is not None:
            raise RuntimeError(f"ChatEngine khởi tạo thất bại: {_shared_warmup_error}")
        fut = _shared_engine_future

    if fut is not None:
        try:
            eng = fut.result(timeout=timeout)
            with _shared_engine_lock:
                _shared_engine_instance = eng
            return eng
        except concurrent.futures.TimeoutError as to_err:
            raise TimeoutError("ChatEngine đang khởi tạo dưới nền, chưa hoàn tất.") from to_err
        except Exception as exc:
            with _shared_engine_lock:
                _shared_warmup_error = str(exc)
            logger.error("[WARMUP] Nạp nền thất bại: %s", exc)
            raise RuntimeError(f"ChatEngine khởi tạo thất bại: {exc}") from exc

    # Khởi tạo trực tiếp nếu chưa có warmup nền
    with _shared_engine_lock:
        if _shared_engine_instance is not None:
            return _shared_engine_instance
        if _shared_warmup_error is not None:
            raise RuntimeError(f"ChatEngine khởi tạo thất bại: {_shared_warmup_error}")
        try:
            t0 = time.perf_counter()
            logger.info("[WARMUP] Khởi tạo ChatEngine trực tiếp...")
            eng = ChatEngine()
            eng.warm_up()
            _shared_engine_instance = eng
            logger.info("[WARMUP] ChatEngine đã khởi tạo trực tiếp sau %.3f giây.", time.perf_counter() - t0)
            return eng
        except Exception as exc:
            _shared_warmup_error = str(exc)
            raise RuntimeError(f"ChatEngine khởi tạo thất bại: {exc}") from exc
