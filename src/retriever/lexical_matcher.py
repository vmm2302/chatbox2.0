"""Module so khớp từ khóa (Lexical / Exact / Fuzzy Matcher).

Thực hiện so khớp nhanh dựa trên quy tắc chuỗi, biểu thức chính quy và chỉ số Jaccard token,
đảm bảo độ trễ thấp và không phụ thuộc vào mô hình vector khi người dùng hỏi đúng mẫu.
"""

import re
from typing import Dict, List, Optional, Set

from src.core.models import QARecord, RetrievalResult
from src.data.loader import normalize_vietnamese_text

# Tập hợp từ dừng tiếng Việt (đã chuẩn hóa không dấu)
VIETNAMESE_STOPWORDS: Set[str] = {
    "tu", "trong", "tieng", "anh", "la", "gi", "co", "cua", "nay",
    "cho", "toi", "minh", "em", "ban", "hoi", "oi", "voi", "a",
    "vay", "nhe", "ha", "nao", "o", "duoc", "cau", "lam", "on",
    "hay", "biet", "nuoc", "se", "va", "cac", "nhung"
}


def clean_conversational_fillers(text: str) -> str:
    """Loại bỏ các từ đệm hội thoại (cho mình hỏi, bạn ơi, nhé, vậy, ạ...)."""
    q = text.strip().lower()
    # Loại bỏ tiền tố xưng hô, hỏi lịch sự
    prefix_patterns = [
        r"^(?:cho\s+(?:mình|tôi|em|anh|chị)\s+hỏi\s*(?:với|nhé|được không)?)\s*",
        r"^(?:bạn\s+ơi\s*(?:cho\s+mình\s+hỏi)?)\s*",
        r"^(?:làm\s+ơn\s+cho\s+(?:mình|tôi)\s+hỏi)\s*",
        r"^(?:hãy\s+(?:cho\s+biết|giải\s+thích))\s*",
        r"^(?:giải\s+thích\s+(?:giúp\s+mình|cho\s+mình)?)\s*"
    ]
    for pat in prefix_patterns:
        q = re.sub(pat, "", q).strip()

    # Loại bỏ hậu tố kết câu hỏi
    suffix_patterns = [
        r"\s*(?:vậy\s+bạn|nhé\s+bạn|ạ|vậy|nhé|hả|với|nhỉ)\??$",
        r"\s*\?+$"
    ]
    for pat in suffix_patterns:
        q = re.sub(pat, "", q).strip()

    return q


class LexicalMatcher:
    """Lớp thực hiện so khớp từ vựng theo quy tắc và từ khóa."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        # Ánh xạ câu hỏi gốc viết thường -> QARecord
        self.exact_map: Dict[str, QARecord] = {
            r.question.strip().lower(): r for r in records
        }
        # Ánh xạ câu hỏi đã chuẩn hóa (bỏ dấu tiếng Việt) -> QARecord
        self.normalized_map: Dict[str, QARecord] = {
            r.normalized_question: r for r in records if r.normalized_question
        }
        # Chỉ mục từ tiếng Anh trong sheet danhsachtutienganhA1-B2
        self.vocab_en_map: Dict[str, QARecord] = {}
        for r in records:
            if r.sheet == "danhsachtutienganhA1-B2" or r.sheet == "DICTIONARY_ENTRIES":
                # Trích xuất từ vựng từ mẫu: "{word} nghĩa là gì?"
                m = re.match(r"^([a-zA-Z0-9_\s,\-]+)\s+nghĩa là gì", r.question, re.IGNORECASE)
                if m:
                    word = m.group(1).strip().lower()
                    self.vocab_en_map[word] = r

    @staticmethod
    def _calculate_token_jaccard(tokens1: List[str], tokens2: List[str]) -> float:
        """Tính chỉ số Jaccard giữa hai tập hợp token."""
        set1 = set(tokens1)
        set2 = set(tokens2)
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def match(self, query: str) -> Optional[RetrievalResult]:
        """Thực hiện so khớp câu hỏi với cơ sở tri thức theo mức độ ưu tiên."""
        clean_raw = query.strip().lower()
        if not clean_raw:
            return None

        # 1. So khớp chính xác 100% nguyên văn
        if clean_raw in self.exact_map:
            return RetrievalResult(
                record=self.exact_map[clean_raw],
                score=1.0,
                method="EXACT"
            )

        # 2. So khớp sau khi chuẩn hóa (bỏ dấu câu, dấu tiếng Việt)
        norm_query = normalize_vietnamese_text(query)
        if norm_query in self.normalized_map:
            return RetrievalResult(
                record=self.normalized_map[norm_query],
                score=0.98,
                method="NORMALIZED_EXACT"
            )

        # 3. Lọc bỏ các từ đệm hội thoại để lấy câu hỏi nòng cốt
        core_query = clean_conversational_fillers(clean_raw)
        norm_core = normalize_vietnamese_text(core_query)

        if norm_core in self.normalized_map:
            return RetrievalResult(
                record=self.normalized_map[norm_core],
                score=0.96,
                method="CORE_NORMALIZED_EXACT"
            )

        # 4. So khớp mẫu tra nghĩa từ vựng: "từ [X] là gì", "nghĩa của [X]", "[X] có nghĩa là gì"
        patterns = [
            r"^(?:từ|nghĩa của từ|nghĩa của)?\s*([a-zA-Z0-9_\s,\-]+?)\s*(?:nghĩa là gì|có nghĩa là gì|là gì|nghĩa sao)\??$",
            r"^([a-zA-Z0-9_\s,\-]+?)\s+(?:nghĩa là gì|có nghĩa là gì|là gì)\??$"
        ]
        for pat in patterns:
            match = re.match(pat, core_query)
            if match:
                extracted_word = match.group(1).strip().lower()
                if extracted_word in self.vocab_en_map:
                    return RetrievalResult(
                        record=self.vocab_en_map[extracted_word],
                        score=0.95,
                        method="VOCAB_PATTERN"
                    )

        # 5. So khớp mẫu hỏi câu ví dụ: "ví dụ của từ [X]", "cho câu ví dụ từ [X]"
        example_pat = r"^(?:cho tôi |cho xin |hãy cho |)?(?:câu ví dụ|ví dụ)(?: của từ| từ| về từ)?\s+([a-zA-Z\s,\-]+?)(?: này)?\??$"
        ex_match = re.match(example_pat, core_query)
        if ex_match:
            ex_word = ex_match.group(1).strip().lower()
            ex_target_q = f"cho toi cau vi du cua tu {ex_word} nay"
            if ex_target_q in self.normalized_map:
                return RetrievalResult(
                    record=self.normalized_map[ex_target_q],
                    score=0.95,
                    method="EXAMPLE_PATTERN"
                )

        # 6. So khớp mẫu danh sách theo trình độ: "A1", "A2", "B1", "B2"
        for level in ["a1", "a2", "b1", "b2"]:
            if f"trình độ {level}" in core_query or f"trinh do {level}" in norm_core or f"từ {level}" in core_query:
                target_q = f"cho toi 1 danh sach gom cac tu tieng anh trong trinh do {level}"
                if target_q in self.normalized_map:
                    return RetrievalResult(
                        record=self.normalized_map[target_q],
                        score=0.95,
                        method="LEVEL_PATTERN"
                    )

        # 7. Tìm kiếm theo Jaccard token trên tập câu hỏi đã chuẩn hóa
        query_tokens = [t for t in norm_core.split() if t not in VIETNAMESE_STOPWORDS]
        if not query_tokens:
            return None

        best_rec: Optional[QARecord] = None
        best_jaccard = 0.0

        for r in self.records:
            if not r.normalized_question:
                continue
            # Bắt buộc: Nếu bản ghi gắn với từ vựng cụ thể, câu hỏi phải chứa từ đó
            if r.word and r.word.lower() not in ("list", ""):
                w_lower = r.word.strip().lower()
                if w_lower not in clean_raw and w_lower not in norm_core:
                    continue

            r_tokens = [t for t in r.normalized_question.split() if t not in VIETNAMESE_STOPWORDS]
            jaccard = self._calculate_token_jaccard(query_tokens, r_tokens)
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_rec = r


        if best_rec and best_jaccard >= 0.70:
            return RetrievalResult(
                record=best_rec,
                score=round(best_jaccard, 3),
                method="TOKEN_JACCARD"
            )

        return None
