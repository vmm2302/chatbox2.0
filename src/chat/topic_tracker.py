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
    "se", "da", "dang", "nhu", "ra", "vao", "lai", "chua", "roi", "khong",
    "danh", "tinh", "dong", "trang", "gioi", "pho", "lien", "than",
    "nghia", "vi", "du", "phat", "am", "cau", "hoi", "tra", "cuu",
    "ban", "minh", "em", "anh", "chi", "giai", "thich", "giup", "doc"
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
        self.vocab_words: Set[str] = set()
        self.known_words: Set[str] = set()
        self.vie_meanings: Set[str] = set()

        if records:
            self.load_known_words(records)

    def load_known_words(self, records: List[QARecord]) -> None:
        """Tải danh sách các từ vựng, từ khóa hợp lệ và nghĩa tiếng Việt từ dataset vào bộ nhớ tìm kiếm O(1)."""
        self.vocab_words = {
            r.word.strip().lower()
            for r in records
            if r.word and len(r.word.strip()) > 1 and bool(re.search(r"[a-zA-Z]", r.word))
        }
        self.known_words = set(self.vocab_words)
        for r in records:
            for token in re.findall(r"\b\w+\b", r.question.lower()):
                if len(token) > 1 and token not in VIETNAMESE_STOPWORDS:
                    self.known_words.add(token)

        self.vie_meanings = set()
        for r in records:
            # 1. Trích xuất nghĩa từ câu hỏi dịch tiếng Việt mẫu, ví dụ: "Quả táo" tiếng Anh là gì?
            m_q = re.search(r'["\u201c\u2018]([^"\u201d\u2019]+)["\u201d\u2019]\s+tiếng anh là gì', r.question, re.IGNORECASE)
            if m_q:
                q_phrase = m_q.group(1).strip().lower()
                if len(q_phrase) >= 2:
                    self.vie_meanings.add(q_phrase)
                    for sub in re.split(r'[,;/]', q_phrase):
                        clean_sub = sub.strip()
                        if len(clean_sub) >= 2:
                            self.vie_meanings.add(clean_sub)

            # 2. Trích xuất nghĩa từ các dòng định nghĩa trong answer
            lines = [l.strip() for l in r.answer.split('\n') if l.strip()]
            for line in lines:
                if line.startswith(('Từ bạn tìm kiếm', 'Từ tiếng Anh phù hợp', 'Trình độ:', 'Phát âm:', '•', 'Danh từ', 'Động từ', 'Tính từ', 'Trạng từ', 'Mạo từ', 'Giới từ', 'Liên từ')):
                    continue
                # Xóa ngoặc đơn trước để tránh việc dấu phẩy trong ngoặc đơn làm đứt cụm
                line_no_parens = re.sub(r'\(.*?\)', '', line)
                meanings = re.split(r'[,;/]', line_no_parens)
                for m in meanings:
                    clean_m = re.sub(r'^\d+[\.\)]\s*', '', m).strip('* ').strip().lower()
                    if len(clean_m) >= 2 and not clean_m.startswith(('từ bạn', 'từ tiếng anh', 'ví dụ', 'trình độ')):
                        self.vie_meanings.add(clean_m)

        logger.info(
            "TopicTracker đã nạp %d từ vựng tiếng Anh, %d từ khóa và %d nghĩa tiếng Việt.",
            len(self.vocab_words),
            len(self.known_words),
            len(self.vie_meanings),
        )

    def is_known_vietnamese_meaning(self, phrase: str) -> bool:
        """Kiểm tra xem một cụm từ tiếng Việt có nằm trong kho nghĩa tiếng Việt của từ vựng không."""
        if not phrase:
            return False
        clean_p = phrase.strip().lower()
        clean_p = re.sub(r"^[\"'\s]+|[\"'\s\?]+$", "", clean_p)
        clean_p = re.sub(r"^(?:từ\s+|chữ\s+|nghĩa\s+của\s+từ\s+|nghĩa\s+từ\s+)", "", clean_p).strip()
        if clean_p in self.vie_meanings:
            return True
        for m in self.vie_meanings:
            if clean_p == m or clean_p == re.sub(r'\(.*?\)', '', m).strip():
                return True
        return False

    @staticmethod
    def extract_vietnamese_phrase(query: str) -> str:
        """Trích xuất từ hoặc cụm từ tiếng Việt cốt lõi cần tra cứu dịch sang tiếng Anh."""
        if not query:
            return ""
        # Xóa sạch dấu ngoặc, dấu câu và khoảng trắng ở đầu và cuối chuỗi trước khi so khớp
        clean = re.sub(r"^[\"'\u201c\u2018\s]+|[\"'\u201d\u2019\s\?\.\!]+$", "", query.strip().lower())
        patterns = [
            # 1. Các mẫu "... trong tiếng Anh có nghĩa là gì / nghĩa là gì / là gì / viết thế nào"
            r"^(?:từ\s+|từ vựng\s+|chữ\s+)?(.+?)\s+(?:trong\s+tiếng\s+anh|tiếng\s+anh)\s+(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì|viết\s+thế\s+nào|viết\s+sao)$",
            # 2. Các mẫu "... có nghĩa là gì / nghĩa là gì / là gì trong tiếng Anh"
            r"^(?:từ\s+|từ vựng\s+|chữ\s+)?(.+?)\s+(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì)\s+(?:trong\s+tiếng\s+anh|sang\s+tiếng\s+anh)$",
            # 3. Các mẫu bắt đầu bằng "trong tiếng Anh (thì) ... có nghĩa là gì / là gì"
            r"^(?:trong\s+tiếng\s+anh\s+(?:thì\s+)?)(.+?)(?:\s+(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì|viết\s+thế\s+nào))?$",
            # 4. Các mẫu "dịch từ ... sang / ra tiếng Anh"
            r"^(?:dịch\s+(?:từ\s+)?)(.+?)(?:\s+sang\s+tiếng\s+anh|\s+ra\s+tiếng\s+anh)$",
            # 5. Các mẫu "từ nào có nghĩa là / mang nghĩa là ..."
            r"^(?:từ\s+nào\s+có\s+nghĩa\s+là|từ\s+nào\s+nghĩa\s+là|từ\s+nào\s+mang\s+nghĩa\s+là)\s+(.+?)$",
            # 6. Các mẫu "tiếng Anh của từ ... là gì"
            r"^(?:tiếng\s+anh\s+của\s+(?:từ\s+)?)(.+?)(?:\s+(?:là\s+gì|có\s+nghĩa\s+là\s+gì))?$",
            # 7. Các mẫu "nghĩa của từ ... trong tiếng Anh"
            r"^(?:nghĩa của từ|nghĩa của|nghĩa từ)\s+(.+?)(?:\s+(?:trong\s+tiếng\s+anh|tiếng\s+anh))?(?:\s+(?:là\s+gì|có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì))?$",
            # 8. Các mẫu định nghĩa thông thường "X có nghĩa là gì / X là gì"
            r"^(?:từ\s+|từ vựng\s+)?(.+?)\s+(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì|nghĩa\s+sao)$",
        ]
        for pat in patterns:
            m = re.match(pat, clean)
            if m:
                clean = m.group(1).strip()
                break

        # Loại bỏ các tiền tố / hậu tố thừa nếu còn sót lại
        if clean.startswith("từ vựng ") or clean.startswith("chữ "):
            clean = re.sub(r"^(?:từ vựng\s+|chữ\s+)", "", clean).strip()
        elif clean.startswith("từ ") and len(clean.split()) > 2:
            clean = clean[3:].strip()
        clean = re.sub(r"\s+(?:trong\s+tiếng\s+anh|tiếng\s+anh)$", "", clean).strip()
        clean = re.sub(r"^[\"'\u201c\u2018\s]+|[\"'\u201d\u2019\s\?\.\!]+$", "", clean)
        return clean

    def extract_target_word(self, query: str) -> Optional[str]:
        """Trích xuất từ tiếng Anh mục tiêu từ câu hỏi của người dùng."""
        clean = query.strip()
        if not clean:
            return None

        clean_lower = clean.lower()

        # 0. Nếu câu hỏi có dấu hiệu dịch từ tiếng Việt sang tiếng Anh thì không coi là tra từ tiếng Anh mục tiêu
        trans_markers = [
            "tiếng anh là gì", "tieng anh la gi", "nghĩa tiếng anh", "dịch sang tiếng anh",
            "dịch từ", "sang tiếng anh", "từ nào có nghĩa là", "từ nào nghĩa là", "từ nào có nghĩa",
            "trong tiếng anh có nghĩa là gì", "trong tieng anh co nghia la gi",
            "trong tiếng anh nghĩa là gì", "trong tieng anh nghia la gi",
            "trong tiếng anh là gì", "trong tieng anh la gi",
            "tiếng anh có nghĩa là gì", "tieng anh co nghia la gi",
            "có nghĩa là gì trong tiếng anh", "co nghia la gi trong tieng anh",
            "nghĩa là gì trong tiếng anh", "nghia la gi trong tieng anh",
            "là gì trong tiếng anh", "la gi trong tieng anh",
            "trong tiếng anh", "sang tiếng anh",
        ]
        if any(m in clean_lower for m in trans_markers):
            return None

        # Nếu câu hỏi là dạng "X là gì?", "X có nghĩa là gì?", "X trong tiếng Anh có nghĩa là gì?"
        m_vie = re.match(
            r"^(?:từ\s+|từ vựng\s+|nghĩa của từ\s+|nghĩa từ\s+|nghĩa của\s+)?(.+?)\s*(?:trong\s+tiếng\s+anh)?\s*(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì|nghĩa\s+sao)\s*(?:trong\s+tiếng\s+anh)?\s*\??$",
            clean_lower,
        )
        if m_vie:
            cand = m_vie.group(1).strip().lower()
            cand_clean = re.sub(r"^[^\w]+|[^\w]+$", "", cand)
            if self.is_known_vietnamese_meaning(cand_clean) or self.is_known_vietnamese_meaning(cand):
                return None
            if bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", cand)):
                return None

        has_vietnamese_accent = bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", clean_lower))

        # 1. Ưu tiên từ nằm trong dấu ngoặc kép hoặc ngoặc đơn: "word", 'word', “word”, ‘word’
        quote_match = re.search(r"[\"'\u201c\u2018]([a-zA-Z\s\-]{2,})[\"'\u201d\u2019]", clean)
        if quote_match:
            candidate = quote_match.group(1).strip().lower()
            if candidate not in VIETNAMESE_STOPWORDS and len(candidate) >= 2:
                return candidate

        # 2. Kiểm tra các mẫu câu định nghĩa phổ biến (kể cả từ chưa có trong kho dữ liệu)
        # Hỗ trợ tùy chọn khoảng trắng và dấu hỏi: \s*\?*
        def_patterns = [
            r"^(?:từ\s+|từ vựng\s+)?([a-zA-Z\s\-]{2,})\s+(?:có\s+nghĩa\s+là\s+gì|nghĩa\s+là\s+gì|là\s+gì|nghĩa\s+sao)\s*\??$",
            r"^(?:nghĩa của từ|nghĩa từ|nghĩa của)\s+(?:từ\s+|chữ\s+)?([a-zA-Z\s\-]{2,})\s*\??$",
            r"^(?:tra từ|giải thích từ)\s+([a-zA-Z\s\-]{2,})\s*\??$",
            r"^(?:what\s+does\s+)([a-zA-Z\s\-]{2,})\s+mean(?:\s+in\s+vietnamese)?\s*\??$",
            r"^(?:what\s+is\s+the\s+meaning\s+of\s+|meaning\s+of\s+)([a-zA-Z\s\-]{2,})\s*\??$",
        ]
        for pat in def_patterns:
            m = re.match(pat, clean, re.IGNORECASE)
            if m:
                cand = m.group(1).strip().lower()
                cand_clean = re.sub(r"^[^\w]+|[^\w]+$", "", cand)
                if cand_clean and cand_clean not in VIETNAMESE_STOPWORDS and len(cand_clean) >= 2:
                    return cand_clean

        # 3. Kiểm tra với tập từ vựng tiếng Anh chuẩn trong Dataset (vocab_words)
        # Sắp xếp theo độ dài giảm dần để ưu tiên từ ghép như 'hard-working', 'give up'
        if self.vocab_words:
            sorted_vocab = sorted(self.vocab_words, key=len, reverse=True)
            for kw in sorted_vocab:
                if has_vietnamese_accent and len(kw) <= 2:
                    continue
                pattern = r"(?:\b|\W)" + re.escape(kw) + r"(?:\b|\W)"
                if re.search(pattern, f" {clean_lower} "):
                    return kw

        # 4. Phân rã theo khoảng trắng và kiểm tra token thuần tiếng Anh (re.fullmatch)
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

        # 5. Nếu toàn bộ câu hỏi chỉ là 1 từ hoặc cụm 2-3 từ tiếng Anh thuần túy
        valid_en_tokens = [t.lower() for t in cleaned_tokens if re.fullmatch(r"[a-zA-Z0-9_\-]{2,}", t) and t.lower() not in VIETNAMESE_STOPWORDS]
        if len(cleaned_tokens) <= 3 and len(valid_en_tokens) == len(cleaned_tokens) and not has_vietnamese_accent:
            return " ".join(valid_en_tokens)

        # 6. Token tiếng Anh hợp lệ đầu tiên nếu dài >= 3 ký tự và không phải stopword
        if not has_vietnamese_accent:
            if self.vocab_words:
                for t in valid_en_tokens:
                    if t in self.vocab_words:
                        return t
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

                # Nếu câu hỏi quá ngắn (ví dụ: "còn ví dụ?", "còn danh từ?"), bổ sung chủ ngữ nếu chưa có
                if (resolved.lower().startswith("còn ") or resolved.lower().startswith("thế còn ")) and f"từ {self.active_word}" not in resolved.lower():
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

        # Trường hợp 4: Câu hỏi tra cứu tiếng Việt sang tiếng Anh (ví dụ: "căn phòng trong tiếng Anh có nghĩa là gì?")
        trans_cues = ["từ nào", "nghĩa là", "có nghĩa", "dịch", "trong tiếng anh", "tiếng anh là gì", "tiếng anh của", "sang tiếng anh"]
        if any(c in clean_query.lower() for c in trans_cues):
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
