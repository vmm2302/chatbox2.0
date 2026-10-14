"""Định nghĩa các mô hình dữ liệu (Data Transfer Objects) trong hệ thống Master Architecture."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

ResponseMode = Literal["DIRECT_MATCH", "RAG_GENERATION", "CLARIFICATION", "NO_MATCH", "EXCEPTION_MATCH", "SMALL_TALK"]
RouteType = Literal["SMALL_TALK", "VOCAB_QUERY", "OUT_OF_SCOPE"]
IntentType = Literal[
    "DEFINE_VOCAB",
    "GET_EXAMPLE",
    "GET_LEVEL_LIST",
    "TRANSLATE_VIE_TO_ENG",
    "FOLLOW_UP",
    "OUT_OF_SCOPE",
    "AMBIGUOUS",
    "SMALL_TALK",
    "GREETING",
    "THANKS",
    "GOODBYE",
    "CASUAL_CHAT",
    "SIMPLE_ACKNOWLEDGEMENT",
    "CHATBOT_IDENTITY",
    "CHATBOT_CAPABILITIES"
]


@dataclass
class QARecord:
    """Đại diện cho một bản ghi tri thức Q&A chuẩn hóa kèm rich metadata."""
    record_id: str = ""
    word: str = ""
    sheet: str = ""
    source: str = ""
    level: str = ""
    question: str = ""
    answer: str = ""
    normalized_question: str = ""

    def __init__(
        self,
        record_id: Optional[str] = None,
        word: str = "",
        sheet: str = "",
        source: str = "",
        level: str = "",
        question: str = "",
        answer: str = "",
        normalized_question: str = "",
        id: Optional[str] = None
    ):
        self.record_id = record_id or id or ""
        self.word = word
        self.sheet = sheet
        self.source = source
        self.level = level
        self.question = question
        self.answer = answer
        self.normalized_question = normalized_question

    # Hỗ trợ backward compatibility với code cũ (id = record_id, difficulty = level)
    @property
    def id(self) -> str:
        return self.record_id

    @property
    def difficulty(self) -> str:
        return self.level


    def to_dict(self) -> Dict[str, str]:
        """Chuyển đổi thành từ điển lưu trữ JSONL và ChromaDB metadata."""
        return {
            "record_id": self.record_id,
            "id": self.record_id,
            "word": self.word,
            "sheet": self.sheet,
            "source": self.source,
            "level": self.level,
            "question": self.question,
            "answer": self.answer,
            "normalized_question": self.normalized_question,
        }


    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "QARecord":
        """Khôi phục đối tượng QARecord từ từ điển."""
        rec_id = data.get("record_id") or data.get("id") or ""
        return cls(
            record_id=rec_id,
            word=data.get("word", ""),
            sheet=data.get("sheet", ""),
            source=data.get("source", ""),
            level=data.get("level", ""),
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            normalized_question=data.get("normalized_question", ""),
        )


@dataclass
class IntentResult:
    """Kết quả phân tích ý định từ PhoBERT Query Understanding."""
    intent: IntentType
    confidence: float
    target_word: Optional[str] = None
    target_level: Optional[str] = None
    is_follow_up: bool = False
    is_ambiguous: bool = False
    raw_query: str = ""
    reformulated_query: str = ""


@dataclass
class RetrievalCandidate:
    """Kết quả chi tiết của từng ứng viên sau khi truy xuất và hợp nhất RRF."""
    record: QARecord
    bm25_score: float = 0.0
    bm25_rank: Optional[int] = None
    bge_score: float = 0.0
    bge_rank: Optional[int] = None
    rrf_score: float = 0.0
    score: float = 0.0
    method: str = "HYBRID_RRF"



# Alias cho backward compatibility với các bài test
RetrievalResult = RetrievalCandidate


@dataclass
class ChatResponse:
    """Kết quả phản hồi người dùng kèm toàn bộ thông số provenance phục vụ audit."""
    answer: str
    mode: ResponseMode
    record_id: Optional[str] = None
    word: Optional[str] = None
    source: Optional[str] = None
    bm25_score: float = 0.0
    bge_score: float = 0.0
    rrf_score: float = 0.0
    intent: Optional[str] = None
    latency_ms: float = 0.0
    candidates: List[RetrievalCandidate] = field(default_factory=list)

    # Thuộc tính tương thích backward với code cũ
    @property
    def confidence_score(self) -> float:
        return self.rrf_score

    @property
    def processing_time_ms(self) -> float:
        return self.latency_ms

    @property
    def matched_record_id(self) -> Optional[str]:
        return self.record_id

    @property
    def matched_question(self) -> Optional[str]:
        if self.candidates:
            return self.candidates[0].record.question
        return None

    @property
    def retrieved_contexts(self) -> List[RetrievalCandidate]:
        return self.candidates
