"""Module điều phối truy xuất lai (Hybrid Retrieval) kết hợp BM25 và BGE-M3 qua RRF.

Áp dụng thuật toán Reciprocal Rank Fusion (RRF) theo chuẩn Information Retrieval,
kết hợp Cổng kiểm soát miền (Domain Gate) và Cổng kiểm soát ngưỡng (Relevance Gate).
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from config.settings import settings
from src.core.models import (
    QARecord,
    ResponseMode,
    RetrievalCandidate,
)
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever
from src.retriever.lexical_matcher import (
    VIETNAMESE_STOPWORDS,
    LexicalMatcher,
    clean_conversational_fillers,
)

logger = logging.getLogger(__name__)


def is_in_scope_domain(query: str, vocab_words: Set[str], knowledge_words: Optional[Set[str]] = None) -> bool:
    """Kiểm tra câu hỏi có thuộc phạm vi tri thức hiện có hay không."""
    q_lower = query.lower()

    # 1. Có chứa từ vựng hoặc từ khóa nằm trong kho tri thức
    tokens = re.findall(r"\b[\w\-]+\b", q_lower)
    if any(t in vocab_words for t in tokens):
        return True
    if knowledge_words and any(t in knowledge_words for t in tokens):
        return True

    # 2. Câu hỏi yêu cầu danh sách từ theo trình độ (A1, A2, B1, B2)
    for level in ["a1", "a2", "b1", "b2"]:
        if level in q_lower and any(k in q_lower for k in ["trình độ", "trinh do", "cấp độ", "danh sách"]):
            return True

    # 3. Câu hỏi tra cứu từ tiếng Việt sang tiếng Anh hoặc dịch thuật, tra nghĩa
    tieng_anh_indicators = [
        "tiếng anh", "tieng anh", "dịch sang anh", "dich sang anh",
        "trong tiếng anh", "trong tieng anh", "tiếng anh là gì",
        "tieng anh la gi", "từ tiếng anh", "tu tieng anh",
        "nghĩa tiếng anh", "nghia tieng anh", "từ nào", "tu nao",
        "có nghĩa là", "co nghia la", "mang nghĩa là", "dịch từ", "dich tu",
        "nghĩa là gì", "nghia la gi", "nghĩa của", "nghia cua",
        "nghĩa là", "nghia la", "nghĩa sao", "nghia sao"
    ]
    if any(ind in q_lower for ind in tieng_anh_indicators):
        return True

    return False



class HybridRetriever:
    """Bộ điều phối Hybrid Retrieval kết hợp BM25, BGE-M3 và ChromaDB qua RRF."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        self.rec_map: Dict[str, QARecord] = {r.record_id: r for r in records}

        # Khởi tạo các thành phần truy xuất
        self.bm25_retriever = BM25Retriever(records)
        self.bge_chroma = BGEChromaRetriever(records)
        self.lexical_matcher = LexicalMatcher(records)

        # Tập hợp từ vựng tiếng Anh có trong tri thức dự án
        self.english_vocab_words: Set[str] = {
            r.word.lower() for r in records if r.word and r.word.lower() != "list"
        }
        # Tập hợp từ khóa đầy đủ từ toàn bộ kho tri thức
        self.knowledge_words: Set[str] = {
            w.lower()
            for r in records
            for w in re.findall(r"\b[\w\-]+\b", f"{r.word} {r.question}")
            if len(w) > 1 and w.lower() not in VIETNAMESE_STOPWORDS
        }

    @property
    def bge_retriever(self) -> BGEChromaRetriever:
        return self.bge_chroma

    def initialize(self, force_reindex: bool = False) -> None:
        """Khởi tạo trước ChromaDB và chỉ mục vector."""
        self.bge_chroma.build_or_load_collection(force_reindex=force_reindex)

    def reload(self, new_records: List[QARecord]) -> None:
        """Cập nhật dữ liệu cho toàn bộ các bộ tìm kiếm thành phần."""
        self.records = new_records
        self.rec_map = {r.record_id: r for r in new_records}
        self.bm25_retriever.reload(new_records)
        self.lexical_matcher.reload(new_records)
        self.bge_chroma.records = new_records
        self.bge_chroma.rec_map = self.rec_map
        self.english_vocab_words = {
            r.word.lower() for r in new_records if r.word and r.word.lower() != "list"
        }
        self.knowledge_words = {
            w.lower()
            for r in new_records
            for w in re.findall(r"\b[\w\-]+\b", f"{r.word} {r.question}")
            if len(w) > 1 and w.lower() not in VIETNAMESE_STOPWORDS
        }
        logger.info("HybridRetriever đã cập nhật hoàn tất %d bản ghi tri thức.", len(new_records))

    def retrieve(
        self,
        query: str,
        active_entity: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> Tuple[ResponseMode, Optional[RetrievalCandidate], List[RetrievalCandidate]]:

        """Thực hiện truy xuất kết hợp BM25 + BGE-M3 và xếp hạng bằng RRF.

        Returns:
            Tuple[ResponseMode, Optional[RetrievalCandidate], List[RetrievalCandidate]]:
                - mode: 'DIRECT_MATCH' | 'RAG_GENERATION' | 'NO_MATCH'
                - best_candidate: Ứng viên điểm cao nhất
                - final_candidates: Top các ứng viên được chọn
        """
        clean_query = query.strip()
        if not clean_query or not self.records:
            return "NO_MATCH", None, []

        # 0. Cổng kiểm soát miền (Domain Gate)
        # Nếu đang có active entity từ lượt trước thì vẫn coi là in-scope
        if not active_entity and not is_in_scope_domain(clean_query, self.english_vocab_words, self.knowledge_words):
            logger.info("Câu hỏi '%s' nằm ngoài phạm vi tra cứu tri thức -> Chặn tại Domain Gate", clean_query)
            return "NO_MATCH", None, []

        # 1. Fast-path Lexical Match (So khớp chính xác hoặc mẫu câu chuẩn)
        lexical_res = self.lexical_matcher.match(clean_query)
        if lexical_res and lexical_res.score >= 0.95:
            cand = RetrievalCandidate(
                record=lexical_res.record,
                bm25_score=25.0,
                bm25_rank=1,
                bge_score=1.0,
                bge_rank=1,
                rrf_score=0.033,  # 1/61 + 1/61
                method=f"LEXICAL_{lexical_res.method}"
            )
            logger.info("Fast-path Lexical Match: %s (Score: %.4f)", cand.record.record_id, cand.rrf_score)
            return "DIRECT_MATCH", cand, [cand]

        # 2. Chạy song song BM25 và BGE-M3 ChromaDB
        bm25_results = self.bm25_retriever.search(clean_query, top_k=settings.BM25_TOP_K)
        bge_results = self.bge_chroma.search(clean_query, top_k=settings.BGE_TOP_K)

        if not bm25_results and not bge_results:
            return "NO_MATCH", None, []

        # 3. Hợp nhất thứ hạng bằng Reciprocal Rank Fusion (RRF)
        # RRF_score(d) = 1 / (k + rank_bm25) + 1 / (k + rank_bge)
        k = settings.RRF_K
        candidates_map: Dict[str, RetrievalCandidate] = {}

        # Ghi nhận kết quả từ BM25
        for rec, score, rank in bm25_results:
            candidates_map[rec.record_id] = RetrievalCandidate(
                record=rec,
                bm25_score=score,
                bm25_rank=rank,
                rrf_score=1.0 / (k + rank)
            )

        # Hợp nhất kết quả từ BGE-M3
        for rec, score, rank in bge_results:
            bge_component = 1.0 / (k + rank)
            if rec.record_id in candidates_map:
                cand = candidates_map[rec.record_id]
                cand.bge_score = score
                cand.bge_rank = rank
                cand.rrf_score += bge_component
            else:
                candidates_map[rec.record_id] = RetrievalCandidate(
                    record=rec,
                    bge_score=score,
                    bge_rank=rank,
                    rrf_score=bge_component
                )

        ranked_candidates = sorted(
            candidates_map.values(),
            key=lambda c: c.rrf_score,
            reverse=True
        )

        limit = top_k or settings.FINAL_TOP_K
        top_candidates = ranked_candidates[:limit]
        best_candidate = top_candidates[0] if top_candidates else None


        if not best_candidate:
            return "NO_MATCH", None, []

        # 4. Cổng kiểm soát ngưỡng (Relevance Gate)
        if best_candidate.rrf_score >= settings.DIRECT_MATCH_RRF_THRESHOLD:
            mode: ResponseMode = "DIRECT_MATCH"
        elif best_candidate.rrf_score >= settings.RAG_RRF_THRESHOLD:
            mode = "RAG_GENERATION"
        else:
            mode = "NO_MATCH"

        logger.info(
            "Hybrid RRF cho '%s' -> Best: %s (RRF: %.4f | BM25: %.2f [#%s] | BGE: %.4f [#%s]) -> Mode: %s",
            clean_query,
            best_candidate.record.record_id,
            best_candidate.rrf_score,
            best_candidate.bm25_score,
            best_candidate.bm25_rank,
            best_candidate.bge_score,
            best_candidate.bge_rank,
            mode
        )

        return mode, best_candidate, top_candidates
