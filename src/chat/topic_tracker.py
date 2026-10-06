"""Module quản lý ngữ cảnh hội thoại nhiều lượt và theo dõi thực thể từ vựng (Active Topic Tracker).

Đảm bảo xử lý chính xác:
1. Duy trì thực thể từ vựng hiện tại (active_word, active_level).
2. Phục hồi ngữ cảnh cho câu hỏi nối tiếp (Follow-up resolution) khi người dùng dùng đại từ ('từ này', 'nó', 'còn ví dụ').
3. Phát hiện câu hỏi mơ hồ (Ambiguous query) khi thiếu từ vựng và chưa có ngữ cảnh trước đó để kích hoạt Clarification Gate.
4. Lưu trữ lịch sử hội thoại nhiều lượt (Conversation Turn History).
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.core.models import QARecord

logger = logging.getLogger(__name__)

# Danh sách stop words tiếng Việt phổ biến để tránh nhận diện nhầm thành từ tiếng Anh
VIETNAMESE_STOPWORDS = {
    "tu", "nay", "cho", "toi", "la", "gi", "do", "tren", "nao", "cua", "hay",
    "giup", "xem", "biet", "voi", "xin", "cam", "on", "va", "nhung", "cac",
    "duoc", "co", "the", "con", "the", "vay", "sao", "dang", "loai", "mot",
    "hai", "ba", "bon", "nam", "trong", "ngoai", "khi", "luc", "neu", "thi",
    "se", "da", "dang", "nhu", "ra", "vao", "lai", "chua", "roi", "khong"
}

# Các cụm từ chỉ đại từ tham chiếu đến từ vựng ở lượt trước
REFERENTIAL_PATTERNS = [
    r"\btừ\s+này\b",
    r"\btừ\s+đó\b",
    r"\btừ\s+trên\b",
    r"\btừ\s+vựng\s+này\b",
    r"\bcủa\s+nó\b",
    r"\bvới\s+nó\b",
    r"\bcho\s+nó\b",
    r"\bnó\b",
]

# Các dấu hiệu câu hỏi nối tiếp (Follow-up cues)
FOLLOW_UP_CUES = [
    "còn", "thế còn", "vậy còn", "dạng từ", "dạng danh từ", "dạng tính từ",
    "dạng động từ", "dạng trạng từ", "còn ví dụ", "thêm ví dụ", "ví dụ nữa",
    "còn trình độ", "còn phát âm", "phát âm thế nào", "cách dùng thế nào"
]


@dataclass
class ConversationTurn:
    """Lưu trữ thông tin một lượt tương tác giữa người dùng và chatbot."""
    turn_id: int
    user_query: str
    resolved_query: str
    intent: str
    active_word: Optional[str]
    answer: str
    mode: str
    matched_record_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class TopicTracker:
    """Bộ theo dõi ngữ cảnh chủ đề và hội thoại nhiều lượt."""

    def __init__(self, records: Optional[List[QARecord]] = None, max_history_turns: int = 10):
        self.active_word: Optional[str] = None
        self.active_level: Optional[str] = None
        self.active_intent: Optional[str] = None
        self.history: List[ConversationTurn] = []
        self.max_history_turns = max_history_turns
        self.known_words: Set[str] = set()

        if records:
            self.load_known_words(records)

    def load_known_words(self, records: List[QARecord]) -> None:
        """Tải danh sách các từ vựng hợp lệ từ dataset vào bộ nhớ tìm kiếm O(1)."""
        self.known_words = {
            r.word.strip().lower()
            for r in records
            if r.word and len(r.word.strip()) > 1
        }
        logger.info("TopicTracker đã nạp %d từ vựng hợp lệ từ bộ dữ liệu.", len(self.known_words))

    def extract_target_word(self, query: str) -> Optional[str]:
        """Trích xuất từ tiếng Anh mục tiêu từ câu hỏi của người dùng."""
        clean = query.strip()
        if not clean:
            return None

        clean_lower = clean.lower()

        # 1. Ưu tiên kiểm tra với tập từ vựng chuẩn trong Dataset (known_words)
        # Sắp xếp theo độ dài giảm dần để ưu tiên từ ghép như 'hard-working', 'give up'
        if self.known_words:
            sorted_known = sorted(self.known_words, key=len, reverse=True)
            for kw in sorted_known:
                pattern = r"(?:\b|\W)" + re.escape(kw) + r"(?:\b|\W)"
                if re.search(pattern, f" {clean_lower} "):
                    return kw

        # 2. Ưu tiên từ nằm trong dấu ngoặc kép hoặc ngoặc đơn: "word", 'word', “word”, ‘word’
        quote_match = re.search(r"[\"'\u201c\u2018]([a-zA-Z\s\-]{2,})[\"'\u201d\u2019]", clean)
        if quote_match:
            candidate = quote_match.group(1).strip().lower()
            if candidate not in VIETNAMESE_STOPWORDS:
                return candidate

        # 3. Phân rã theo khoảng trắng và kiểm tra token thuần tiếng Anh (re.fullmatch)
        # Bỏ qua các token chứa ký tự tiếng Việt hoặc dấu câu
        raw_tokens = clean.split()
        cleaned_tokens = [re.sub(r"^[^\w]+|[^\w]+$", "", t) for t in raw_tokens]

        # Kiểm tra mẫu tường minh: từ đứng ngay sau "từ", "chữ", "từ vựng"
        cue_indices = [
            i for i, t in enumerate(cleaned_tokens)
            if t.lower() in ("từ", "chữ", "từ-vựng") or (i > 0 and cleaned_tokens[i-1].lower() == "từ" and t.lower() == "vựng")
        ]
        for idx in cue_indices:
            next_idx = idx + 1
            if next_idx < len(cleaned_tokens):
                nxt = cleaned_tokens[next_idx]
                if re.fullmatch(r"[a-zA-Z0-9_\-]{2,}", nxt):
                    nxt_lower = nxt.lower()
                    if nxt_lower not in VIETNAMESE_STOPWORDS and nxt_lower not in ("nay", "do", "tren", "kia"):
                        return nxt_lower

        # 4. Nếu toàn bộ câu hỏi chỉ là 1 từ hoặc cụm 2 từ tiếng Anh thuần túy
        valid_en_tokens = [t.lower() for t in cleaned_tokens if re.fullmatch(r"[a-zA-Z0-9_\-]{2,}", t) and t.lower() not in VIETNAMESE_STOPWORDS]
        if len(cleaned_tokens) <= 3 and valid_en_tokens:
            return valid_en_tokens[0]

        # 5. Token tiếng Anh hợp lệ đầu tiên nếu dài >= 3 ký tự và không phải stopword
        for t in valid_en_tokens:
            if len(t) >= 3 and t not in VIETNAMESE_STOPWORDS:
                return t

        return None


    def extract_target_level(self, query: str) -> Optional[str]:
        """Trích xuất cấp độ CEFR (A1, A2, B1, B2) từ câu hỏi."""
        lvl_match = re.search(r"\b(A1|A2|B1|B2)\b", query, re.IGNORECASE)
        if lvl_match:
            return lvl_match.group(1).upper()
        return None

    def is_referential_query(self, query: str) -> bool:
        """Kiểm tra câu hỏi có chứa đại từ tham chiếu ('từ này', 'nó', ...) hay không."""
        clean = query.lower()
        return any(re.search(pattern, clean) for pattern in REFERENTIAL_PATTERNS)

    def is_follow_up_cues(self, query: str) -> bool:
        """Kiểm tra xem câu hỏi có chứa các cụm nối tiếp (Follow-up cues) hay không."""
        clean = query.lower().strip()
        return any(clean.startswith(cue) or f" {cue} " in f" {clean} " for cue in FOLLOW_UP_CUES)

    def resolve_query(self, query: str) -> Tuple[str, Optional[str], bool, bool]:
        """Phân tích, giải quyết liên kết ngữ cảnh và phát hiện mơ hồ.

        Args:
            query: Câu hỏi đầu vào của người dùng.

        Returns:
            Tuple gồm:
            - resolved_query: Câu hỏi đã được làm giàu ngữ cảnh (thay thế đại từ bằng active_word)
            - target_word: Từ vựng mục tiêu (nếu có)
            - is_follow_up: True nếu đây là câu hỏi nối tiếp
            - is_ambiguous: True nếu câu hỏi thiếu từ vựng và chưa có ngữ cảnh (cần hỏi lại)
        """
        clean_query = query.strip()
        if not clean_query:
            return clean_query, None, False, True

        extracted_word = self.extract_target_word(clean_query)
        extracted_level = self.extract_target_level(clean_query)
        has_referential = self.is_referential_query(clean_query)
        has_follow_up_cue = self.is_follow_up_cues(clean_query)

        # Trường hợp 1: Người dùng nêu rõ từ vựng mới trong câu hỏi
        if extracted_word:
            self.active_word = extracted_word
            if extracted_level:
                self.active_level = extracted_level
            return clean_query, extracted_word, False, False

        # Trường hợp 2: Câu hỏi có đại từ tham chiếu hoặc câu hỏi nối tiếp
        if has_referential or has_follow_up_cue:
            if self.active_word:
                # Đã có ngữ cảnh từ vựng ở các lượt trước: Tái tạo câu hỏi đầy đủ
                resolved = clean_query
                # Thay thế các đại từ 'từ này', 'từ đó', 'nó' bằng từ vựng thực tế
                for pattern in REFERENTIAL_PATTERNS:
                    resolved = re.sub(pattern, f"từ {self.active_word}", resolved, flags=re.IGNORECASE)

                # Nếu câu hỏi quá ngắn (ví dụ: "còn ví dụ?", "còn danh từ?"), bổ sung chủ ngữ
                if resolved.lower().startswith("còn ") or resolved.lower().startswith("thế còn "):
                    resolved = f"{resolved} của từ {self.active_word}"

                logger.info("Phục hồi câu hỏi nối tiếp: '%s' -> '%s' (active_word=%s)", query, resolved, self.active_word)
                return resolved, self.active_word, True, False
            else:
                # Không có ngữ cảnh trước đó: Rơi vào trạng thái MƠ HỒ (Ambiguous)
                logger.info("Phát hiện câu hỏi mơ hồ thiếu thực thể: '%s'", query)
                return clean_query, None, False, True

        # Trường hợp 3: Câu hỏi cấp độ không cần từ vựng (ví dụ: "danh sách từ trình độ A1")
        if extracted_level and ("danh sách" in clean_query.lower() or "trình độ" in clean_query.lower() or "cấp độ" in clean_query.lower()):
            self.active_level = extracted_level
            return clean_query, None, False, False

        # Trường hợp 4: Câu hỏi tra cứu tiếng Việt sang tiếng Anh (ví dụ: "từ nào có nghĩa là từ bỏ?")
        if "từ nào" in clean_query.lower() or "nghĩa là" in clean_query.lower() or "dịch" in clean_query.lower():
            # Đây là câu hỏi dịch thuật tự nhiên, không phải mơ hồ
            return clean_query, None, False, False

        # Trường hợp 5: Câu hỏi thông thường
        return clean_query, None, False, False

    def add_turn(
        self,
        user_query: str,
        resolved_query: str,
        intent: str,
        active_word: Optional[str],
        answer: str,
        mode: str,
        matched_record_id: Optional[str] = None
    ) -> None:
        """Ghi nhận một lượt hội thoại vào lịch sử."""
        turn_id = len(self.history) + 1
        turn = ConversationTurn(
            turn_id=turn_id,
            user_query=user_query,
            resolved_query=resolved_query,
            intent=intent,
            active_word=active_word or self.active_word,
            answer=answer,
            mode=mode,
            matched_record_id=matched_record_id
        )
        self.history.append(turn)

        # Cắt tỉa lịch sử theo giới hạn max_history_turns
        if len(self.history) > self.max_history_turns:
            self.history = self.history[-self.max_history_turns:]

    def get_history(self) -> List[ConversationTurn]:
        """Lấy toàn bộ lịch sử các lượt tương tác."""
        return list(self.history)

    def clear(self) -> None:
        """Xóa toàn bộ trạng thái và lịch sử hội thoại."""
        self.active_word = None
        self.active_level = None
        self.active_intent = None
        self.history.clear()
        logger.info("Đã xóa toàn bộ trạng thái hội thoại và active topic.")
