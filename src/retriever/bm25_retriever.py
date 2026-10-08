"""Module truy xuất từ khóa BM25 (Lexical Retrieval) sử dụng rank-bm25.

Lập chỉ mục ngược (Inverted Index) trên toàn bộ tập câu hỏi và từ vựng chuẩn hóa,
chạy 100% cục bộ, độ trễ cực thấp.
"""

import logging
import re
from typing import List, Optional, Tuple

from rank_bm25 import BM25Okapi

from config.settings import settings
from src.core.models import QARecord
from src.data.loader import normalize_vietnamese_text

logger = logging.getLogger(__name__)


def tokenize_for_bm25(text: str) -> List[str]:
    """Tách token chuẩn hóa phục vụ BM25."""
    clean = normalize_vietnamese_text(text)
    tokens = clean.split()
    # Giữ lại token có độ dài > 0
    return [t for t in tokens if t]


class BM25Retriever:
    """Lớp quản lý chỉ mục và tìm kiếm BM25."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        self.bm25: Optional[BM25Okapi] = None
        self._build_index()

    def _build_index(self) -> None:
        """Xây dựng chỉ mục BM25 từ tập câu hỏi và từ vựng của bản ghi."""
        if not self.records:
            self.bm25 = None
            logger.info("Chỉ mục BM25 rỗng (0 bản ghi).")
            return

        corpus: List[List[str]] = []
        for r in self.records:
            # Kết hợp từ vựng mục tiêu và câu hỏi để tăng độ khớp từ khóa
            doc_text = f"{r.word} {r.question}"
            tokens = tokenize_for_bm25(doc_text)
            corpus.append(tokens)

        if not corpus or all(len(c) == 0 for c in corpus):
            self.bm25 = None
            return

        self.bm25 = BM25Okapi(corpus)
        logger.info("Đã lập chỉ mục BM25 thành công cho %d văn bản.", len(corpus))

    def reload(self, new_records: List[QARecord]) -> None:
        """Cập nhật danh sách bản ghi và tái lập chỉ mục BM25 tức thì."""
        self.records = new_records
        self._build_index()

    def search(self, query: str, top_k: int = 15) -> List[Tuple[QARecord, float, int]]:
        """Tìm kiếm top_k bản ghi theo điểm số BM25.

        Returns:
            List[Tuple[QARecord, float, int]]: Danh sách (bản ghi, điểm số BM25, thứ hạng rank 1-indexed)
        """
        if not query.strip() or self.bm25 is None or not self.records:
            return []

        tokens = tokenize_for_bm25(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        # Lấy các chỉ số có điểm cao nhất
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results: List[Tuple[QARecord, float, int]] = []
        for rank, idx in enumerate(ranked_indices[:top_k], 1):
            score = float(scores[idx])
            # Chỉ lấy các bản ghi có điểm BM25 > 0
            if score > 0.0:
                results.append((self.records[idx], round(score, 4), rank))

        return results
