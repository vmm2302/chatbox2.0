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
        """Cập nhật dữ liệu tri thức mới cho toàn bộ pipeline mà không cần khởi động lại."""
        self.records = new_records
        self.retriever.reload(new_records)
        self.tracker.load_known_words(new_records)
        logger.info("ChatEngine đã đồng bộ thành công %d bản ghi tri thức mới.", len(new_records))

    def ask(self, query: str) -> ChatResponse:
        """Xử lý câu hỏi người dùng ở chế độ đồng bộ."""
        start_time = time.perf_counter()
        clean_query, normalized_query = normalize_query_text(query)

        if not clean_query:
            return ChatResponse(
                answer="Vui lòng nhập câu hỏi.",
                mode="NO_MATCH",
                latency_ms=0.0
            )

        self.warm_up()

        # Bước 1: Query Router điều phối 3 nhánh (Small Talk, Out of Scope, Vocab Query)
        routing = self.query_router.route(normalized_query, self.tracker)

        # 1.1 NHÁNH SMALL TALK: Phản hồi xã giao không đưa vào Hybrid Retrieval
        if routing.route_type == "SMALL_TALK":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = self.small_talk_handler.handle(
                query=clean_query,
                intent=routing.intent,
                template_response=routing.template_response,
                use_llm=False,
                llm_client=self.llm_client
            )
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent=routing.intent,
                active_word=self.tracker.active_word,
                answer=answer,
                mode="SMALL_TALK"
            )
            return ChatResponse(
                answer=answer,
                mode="SMALL_TALK",
                intent=routing.intent,
                latency_ms=round(elapsed_ms, 2)
            )

        # 1.2 Kiểm tra Knowledge Base rỗng (Empty Knowledge Base Gate)
        if len(self.records) == 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            empty_ans = getattr(settings, "EMPTY_KB_RESPONSE", "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này. Vui lòng nạp thêm tài liệu vào hệ thống.")
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent="EMPTY_KB",
                active_word=None,
                answer=empty_ans,
                mode="NO_MATCH"
            )
            return ChatResponse(
                answer=empty_ans,
                mode="NO_MATCH",
                intent="EMPTY_KB",
                latency_ms=round(elapsed_ms, 2)
            )

        # 1.3 NHÁNH OUT OF SCOPE: Từ chối câu hỏi ngoài phạm vi không đưa vào Hybrid Retrieval
        if routing.route_type == "OUT_OF_SCOPE":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = routing.template_response or settings.OUT_OF_SCOPE_RESPONSE
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent="OUT_OF_SCOPE",
                active_word=self.tracker.active_word,
                answer=answer,
                mode="NO_MATCH"
            )
            return ChatResponse(
                answer=answer,
                mode="NO_MATCH",
                intent="OUT_OF_SCOPE",
                latency_ms=round(elapsed_ms, 2)
            )

        # 1.4 NHÁNH VOCAB QUERY: Thực hiện tuần tự Sequential Pipeline
        # Bước 2: Quản lý ngữ cảnh và phân giải thực thể qua TopicTracker
        resolved_query, target_word, is_follow_up, is_ambiguous = self.tracker.resolve_query(clean_query)

        # Bước 2: Xử lý trạng thái MƠ HỒ (Thiếu từ vựng và chưa có active_word)
        if is_ambiguous:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                active_word=None,
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION"
            )
            return ChatResponse(
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                intent="AMBIGUOUS",
                latency_ms=round(elapsed_ms, 2)
            )

        # Bước 3: Phân loại ý định qua PhoBERT
        has_active_topic = bool(self.tracker.active_word)
        intent_res = self.intent_classifier.classify_intent(
            resolved_query,
            has_active_topic=has_active_topic,
            tracker=self.tracker
        )

        # Nếu PhoBERT phát hiện mơ hồ
        if intent_res.is_ambiguous:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                active_word=None,
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION"
            )
            return ChatResponse(
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                intent="AMBIGUOUS",
                latency_ms=round(elapsed_ms, 2)
            )

        # Nếu câu hỏi hoàn toàn ngoài phạm vi (OUT_OF_SCOPE) và không có từ tiếng Anh nào được phát hiện
        if intent_res.intent == "OUT_OF_SCOPE" and not target_word and not self.tracker.active_word:
            # Kiểm tra xem có từ tiếng Anh hợp lệ trong query không
            if not any(token.lower() in self.tracker.known_words for token in clean_query.split()):
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                self.tracker.add_turn(
                    user_query=clean_query,
                    resolved_query=resolved_query,
                    intent="OUT_OF_SCOPE",
                    active_word=None,
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH"
                )
                return ChatResponse(
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH",
                    intent="OUT_OF_SCOPE",
                    latency_ms=round(elapsed_ms, 2)
                )

        # Bước 4: Truy xuất Hybrid (BM25 + BGE-M3 + RRF)
        mode, best_candidate, candidates = self.retriever.retrieve(
            resolved_query,
            top_k=settings.TOP_K_RETRIEVAL
        )

        # Bước 5: Kiểm tra Domain & Threshold Gate
        if not candidates or best_candidate is None or mode == "NO_MATCH":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                active_word=self.tracker.active_word,
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH"
            )
            return ChatResponse(
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH",
                intent=intent_res.intent,
                latency_ms=round(elapsed_ms, 2),
                candidates=candidates
            )

        # Cập nhật thực thể đang nói đến nếu tìm được ứng viên phù hợp
        if best_candidate.record.word:
            self.tracker.active_word = best_candidate.record.word.strip().lower()

        # Bước 6: Xử lý theo Response Mode
        # 6.1 Khớp chính xác (DIRECT_MATCH)
        if mode == "DIRECT_MATCH":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = format_vocabulary_response(best_candidate.record.answer)
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                active_word=self.tracker.active_word,
                answer=answer,
                mode="DIRECT_MATCH",
                matched_record_id=best_candidate.record.record_id
            )
            return ChatResponse(
                answer=answer,
                mode="DIRECT_MATCH",
                record_id=best_candidate.record.record_id,
                word=best_candidate.record.word,
                source=best_candidate.record.source,
                bm25_score=best_candidate.bm25_score,
                bge_score=best_candidate.bge_score,
                rrf_score=best_candidate.rrf_score,
                intent=intent_res.intent,
                latency_ms=round(elapsed_ms, 2),
                candidates=candidates
            )

        # 6.2 Tổng hợp và diễn đạt qua LLM có căn cứ ngữ cảnh (RAG_GENERATION)
        context_str = build_context_string(candidates)
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

        formatted_answer = format_vocabulary_response(llm_answer)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.tracker.add_turn(
            user_query=clean_query,
            resolved_query=resolved_query,
            intent=intent_res.intent,
            active_word=self.tracker.active_word,
            answer=formatted_answer,
            mode="RAG_GENERATION",
            matched_record_id=best_candidate.record.record_id
        )

        return ChatResponse(
            answer=formatted_answer,
            mode="RAG_GENERATION",
            record_id=best_candidate.record.record_id,
            word=best_candidate.record.word,
            source=best_candidate.record.source,
            bm25_score=best_candidate.bm25_score,
            bge_score=best_candidate.bge_score,
            rrf_score=best_candidate.rrf_score,
            intent=intent_res.intent,
            latency_ms=round(elapsed_ms, 2),
            candidates=candidates
        )

    def ask_stream(
        self,
        query: str
    ) -> Generator[Tuple[str, Optional[ChatResponse]], None, None]:
        """Xử lý câu hỏi người dùng theo dạng stream token phục vụ UI."""
        start_time = time.perf_counter()
        clean_query, normalized_query = normalize_query_text(query)

        if not clean_query:
            resp = ChatResponse(
                answer="Vui lòng nhập câu hỏi.",
                mode="NO_MATCH",
                latency_ms=0.0
            )
            yield resp.answer, resp
            return

        self.warm_up()

        # Bước 1: Query Router điều phối 3 nhánh (Small Talk, Out of Scope, Vocab Query)
        routing = self.query_router.route(normalized_query, self.tracker)

        # 1.1 NHÁNH SMALL TALK: Phản hồi xã giao không đưa vào Hybrid Retrieval
        if routing.route_type == "SMALL_TALK":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = self.small_talk_handler.handle(
                query=clean_query,
                intent=routing.intent,
                template_response=routing.template_response,
                use_llm=False,
                llm_client=self.llm_client
            )
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent=routing.intent,
                active_word=self.tracker.active_word,
                answer=answer,
                mode="SMALL_TALK"
            )
            resp = ChatResponse(
                answer=answer,
                mode="SMALL_TALK",
                intent=routing.intent,
                latency_ms=round(elapsed_ms, 2)
            )
            yield resp.answer, resp
            return

        # 1.2 Kiểm tra Knowledge Base rỗng (Empty Knowledge Base Gate)
        if len(self.records) == 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            empty_ans = getattr(settings, "EMPTY_KB_RESPONSE", "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này. Vui lòng nạp thêm tài liệu vào hệ thống.")
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent="EMPTY_KB",
                active_word=None,
                answer=empty_ans,
                mode="NO_MATCH"
            )
            resp = ChatResponse(
                answer=empty_ans,
                mode="NO_MATCH",
                intent="EMPTY_KB",
                latency_ms=round(elapsed_ms, 2)
            )
            yield resp.answer, resp
            return

        # 1.3 NHÁNH OUT OF SCOPE: Từ chối câu hỏi ngoài phạm vi không đưa vào Hybrid Retrieval
        if routing.route_type == "OUT_OF_SCOPE":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = routing.template_response or settings.OUT_OF_SCOPE_RESPONSE
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=clean_query,
                intent="OUT_OF_SCOPE",
                active_word=self.tracker.active_word,
                answer=answer,
                mode="NO_MATCH"
            )
            resp = ChatResponse(
                answer=answer,
                mode="NO_MATCH",
                intent="OUT_OF_SCOPE",
                latency_ms=round(elapsed_ms, 2)
            )
            yield resp.answer, resp
            return

        # 1.4 NHÁNH VOCAB QUERY: Thực hiện tuần tự Sequential Pipeline
        # Bước 2: Quản lý ngữ cảnh và phân giải thực thể qua TopicTracker
        resolved_query, target_word, is_follow_up, is_ambiguous = self.tracker.resolve_query(clean_query)

        # Bước 2: Kiểm tra MƠ HỒ
        if is_ambiguous:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                active_word=None,
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION"
            )
            resp = ChatResponse(
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                intent="AMBIGUOUS",
                latency_ms=round(elapsed_ms, 2)
            )
            yield resp.answer, resp
            return

        # Bước 3: Phân loại ý định
        intent_res = self.intent_classifier.classify_intent(
            resolved_query,
            has_active_topic=bool(self.tracker.active_word),
            tracker=self.tracker
        )

        if intent_res.is_ambiguous:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent="AMBIGUOUS",
                active_word=None,
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION"
            )
            resp = ChatResponse(
                answer=CLARIFICATION_MESSAGE,
                mode="CLARIFICATION",
                intent="AMBIGUOUS",
                latency_ms=round(elapsed_ms, 2)
            )
            yield resp.answer, resp
            return

        if intent_res.intent == "OUT_OF_SCOPE" and not target_word and not self.tracker.active_word:
            if not any(token.lower() in self.tracker.known_words for token in clean_query.split()):
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                self.tracker.add_turn(
                    user_query=clean_query,
                    resolved_query=resolved_query,
                    intent="OUT_OF_SCOPE",
                    active_word=None,
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH"
                )
                resp = ChatResponse(
                    answer=settings.OUT_OF_SCOPE_RESPONSE,
                    mode="NO_MATCH",
                    intent="OUT_OF_SCOPE",
                    latency_ms=round(elapsed_ms, 2)
                )
                yield resp.answer, resp
                return

        # Bước 4: Truy xuất
        mode, best_candidate, candidates = self.retriever.retrieve(
            resolved_query,
            top_k=settings.TOP_K_RETRIEVAL
        )

        # Bước 5: Threshold Gate
        if not candidates or best_candidate is None or mode == "NO_MATCH":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                active_word=self.tracker.active_word,
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH"
            )
            resp = ChatResponse(
                answer=settings.OUT_OF_SCOPE_RESPONSE,
                mode="NO_MATCH",
                intent=intent_res.intent,
                latency_ms=round(elapsed_ms, 2),
                candidates=candidates
            )
            yield resp.answer, resp
            return

        if best_candidate.record.word:
            self.tracker.active_word = best_candidate.record.word.strip().lower()

        # 6.1 DIRECT_MATCH
        if mode == "DIRECT_MATCH":
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            answer = format_vocabulary_response(best_candidate.record.answer)
            self.tracker.add_turn(
                user_query=clean_query,
                resolved_query=resolved_query,
                intent=intent_res.intent,
                active_word=self.tracker.active_word,
                answer=answer,
                mode="DIRECT_MATCH",
                matched_record_id=best_candidate.record.record_id
            )
            resp = ChatResponse(
                answer=answer,
                mode="DIRECT_MATCH",
                record_id=best_candidate.record.record_id,
                word=best_candidate.record.word,
                source=best_candidate.record.source,
                bm25_score=best_candidate.bm25_score,
                bge_score=best_candidate.bge_score,
                rrf_score=best_candidate.rrf_score,
                intent=intent_res.intent,
                latency_ms=round(elapsed_ms, 2),
                candidates=candidates
            )
            yield resp.answer, resp
            return

        # 6.2 RAG_GENERATION (Streaming từ LLM)
        messages = build_rag_prompt(resolved_query, candidates)
        accumulated_text = ""
        try:
            for token in self.llm_client.stream_chat(messages):
                accumulated_text += token
                yield token, None
        except Exception as err:
            error_msg = f"\n{settings.OLLAMA_OFFLINE_RESPONSE}\n({err})"
            accumulated_text += error_msg
            yield error_msg, None

        formatted_final = format_vocabulary_response(accumulated_text)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.tracker.add_turn(
            user_query=clean_query,
            resolved_query=resolved_query,
            intent=intent_res.intent,
            active_word=self.tracker.active_word,
            answer=formatted_final,
            mode="RAG_GENERATION",
            matched_record_id=best_candidate.record.record_id
        )

        final_resp = ChatResponse(
            answer=formatted_final,
            mode="RAG_GENERATION",
            record_id=best_candidate.record.record_id,
            word=best_candidate.record.word,
            source=best_candidate.record.source,
            bm25_score=best_candidate.bm25_score,
            bge_score=best_candidate.bge_score,
            rrf_score=best_candidate.rrf_score,
            intent=intent_res.intent,
            latency_ms=round(elapsed_ms, 2),
            candidates=candidates
        )
        yield "", final_resp
