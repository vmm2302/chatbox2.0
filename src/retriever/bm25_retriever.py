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

# Danh sách stop words tiếng Việt và từ đệm câu hỏi để tránh BM25 khớp nhầm từ vô nghĩa (gồm cả có dấu và không dấu)
BM25_STOPWORDS = {
    "tu", "từ", "nay", "này", "cho", "toi", "tôi", "la", "là", "gi", "gì", "do", "đó", "tren", "trên",
    "nao", "nào", "cua", "của", "hay", "hãy", "giup", "giúp", "xem", "biet", "biết", "voi", "với",
    "xin", "cam", "cảm", "on", "ơn", "va", "và", "nhung", "những", "cac", "các", "duoc", "được",
    "co", "có", "the", "thể", "con", "còn", "vay", "vậy", "sao", "dang", "dạng", "loai", "loại",
    "mot", "một", "trong", "khi", "neu", "nếu", "thi", "thì", "se", "sẽ", "da", "đã", "nhu", "như",
    "ra", "vao", "vào", "lai", "lại", "chua", "chưa", "roi", "rồi", "khong", "không", "nghia", "nghĩa",
    "cau", "câu", "vi", "ví", "du", "dụ", "ban", "bạn", "minh", "mình", "em", "anh", "chi", "chị",
    "dich", "dịch", "sang", "tieng", "tiếng"
}


def tokenize_for_bm25(text: str) -> List[str]:
    """Tách token chuẩn hóa phục vụ BM25 (bao gồm cả token nguyên bản chữ thường và token không dấu)."""
    low = text.lower()
    norm = normalize_vietnamese_text(low)
    low_clean = re.sub(r"[^\w\s]", " ", low)
    norm_clean = re.sub(r"[^\w\s]", " ", norm)
    combined = f"{low_clean} {norm_clean}"
    tokens = combined.split()
    return [t for t in tokens if t]


class BM25Retriever:
    """Lớp quản lý chỉ mục và tìm kiếm BM25."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        self.bm25: Optional[BM25Okapi] = None
        self._build_index()

    def _build_index(self) -> None:
        """Xây dựng chỉ mục BM25 từ tập câu hỏi, từ vựng và câu trả lời của bản ghi."""
        if not self.records:
            self.bm25 = None
            logger.info("Chỉ mục BM25 rỗng (0 bản ghi).")
            return

        corpus: List[List[str]] = []
        for r in self.records:
            # Kết hợp từ vựng mục tiêu, câu hỏi và một phần định nghĩa để tăng khả năng truy xuất
            doc_text = f"{r.word} {r.question} {r.answer[:200]}"
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

        # Ưu tiên các token mang nội dung thực tế (lọc bỏ các từ đệm, hỏi đáp rập khuôn)
        content_tokens = [t for t in tokens if t not in BM25_STOPWORDS]
        search_tokens = content_tokens if content_tokens else tokens

        scores = self.bm25.get_scores(search_tokens)

        # Lấy các chỉ số có điểm cao nhất
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results: List[Tuple[QARecord, float, int]] = []
        for rank, idx in enumerate(ranked_indices[:top_k], 1):
            score = float(scores[idx])
            # Chỉ lấy các bản ghi có điểm BM25 > 0
            if score > 0.0:
                results.append((self.records[idx], round(score, 4), rank))

        return results
