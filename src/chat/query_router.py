"""Module Query Router điều phối câu hỏi người dùng (Query Routing Architecture).

Thực hiện phân luồng 3 nhánh cố định theo Architecture Lock:
                         USER
                           ↓
                     Query Router
                           ↓
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
        SMALL TALK     VOCAB QUERY    OUT OF SCOPE
             ↓             ↓
        Small Talk      PhoBERT
        Handler            ↓
                       BM25 + BGE-M3
                            ↓
                         RRF
                            ↓
                     Relevance Gate
                       /        \
                      ↓          ↓
                   Context    Clarify
                      ↓
                 Qwen2.5:7B
                      ↓
                    Answer
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from config.settings import settings
from src.chat.small_talk_handler import SmallTalkHandler
from src.chat.topic_tracker import TopicTracker
from src.core.models import RouteType
from src.data.loader import normalize_vietnamese_text

logger = logging.getLogger(__name__)


DEFAULT_OUT_OF_SCOPE_TOPICS: Tuple[str, ...] = (
    "bitcoin", "btc", "ethereum", "crypto", "tien ao",
    "gia vang", "gia xang", "chung khoan", "co phieu",
    "thoi tiet", "du bao thoi tiet", "nhiet do",
    "nau an", "cong thuc nau an", "mon an",
    "giai phuong trinh", "toan hoc", "giai toan",
    "viet code", "viet code python", "lap trinh",
    "choi co", "ke chuyen", "ke chuyen cuoi", "ke chuyen co tich",
    "hat mot bai", "tin tuc hom nay", "bong da", "ket qua so xo",
    "thu do", "dia ly", "lich su", "nuoc phap", "chinh tri", "tong thong",
)


@dataclass
class RoutingDecision:
    """Quyết định phân luồng từ Query Router."""
    route_type: RouteType  # "SMALL_TALK" | "VOCAB_QUERY" | "OUT_OF_SCOPE"
    intent: str
    template_response: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


class QueryRouter:
    """Bộ định tuyến câu hỏi (Query Router)."""

    def __init__(
        self,
        small_talk_handler: Optional[SmallTalkHandler] = None,
        json_path: Optional[Path] = None,
    ):
        self.small_talk_handler = small_talk_handler or SmallTalkHandler(json_path=json_path)
        self.json_path = json_path or settings.EXCEPTION_INTENTS_PATH
        self.out_of_scope_patterns: List[str] = []
        self._load_out_of_scope_rules()

    def _load_out_of_scope_rules(self) -> None:
        """Nạp các mẫu ngoài phạm vi (out_of_scope) từ exception_intent.json và danh mục mở rộng."""
        patterns: Set[str] = set()

        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("intents", []):
                        if item.get("intent") == "out_of_scope":
                            for ex in item.get("examples", []):
                                norm = normalize_vietnamese_text(re.sub(r"[^\w\s]", "", ex.strip().lower()))
                                if norm:
                                    patterns.add(norm)
            except Exception as exc:
                logger.error("Lỗi khi nạp mẫu out-of-scope trong QueryRouter: %s", exc)

        for ep in DEFAULT_OUT_OF_SCOPE_TOPICS:
            norm_ep = normalize_vietnamese_text(ep)
            if norm_ep:
                patterns.add(norm_ep)

        self.out_of_scope_patterns = sorted(patterns, key=len, reverse=True)
        logger.info("QueryRouter đã nạp %d mẫu câu nhận diện OUT_OF_SCOPE.", len(self.out_of_scope_patterns))

    def route(
        self,
        query: str,
        tracker: Optional[TopicTracker] = None
    ) -> RoutingDecision:
        """Phân luồng câu hỏi thành: SMALL_TALK, OUT_OF_SCOPE, hoặc VOCAB_QUERY.

        Args:
            query: Câu hỏi người dùng.
            tracker: TopicTracker theo dõi ngữ cảnh hiện tại.

        Returns:
            RoutingDecision: Quyết định phân luồng.
        """
        clean_q = query.strip()
        if not clean_q:
            return RoutingDecision(
                route_type="SMALL_TALK",
                intent="UNCLEAR_INPUT",
                template_response="Vui lòng nhập câu hỏi.",
                confidence=1.0,
                reason="Empty query"
            )

        # -------------------------------------------------------------
        # NHÁNH 1: SMALL TALK (Giao tiếp xã giao, chào hỏi, xác nhận)
        # -------------------------------------------------------------
        small_talk_match = self.small_talk_handler.match(clean_q)
        if small_talk_match:
            intent_name, resp_text = small_talk_match
            return RoutingDecision(
                route_type="SMALL_TALK",
                intent=intent_name.upper(),
                template_response=resp_text,
                confidence=1.0,
                reason=f"Matched small talk intent '{intent_name}'"
            )

        # Chuẩn hóa để kiểm tra out-of-scope
        no_punct = re.sub(r"[^\w\s]", "", clean_q.lower()).strip()
        vn_norm = normalize_vietnamese_text(no_punct)

        # -------------------------------------------------------------
        # NHÁNH 2: OUT OF SCOPE (Chủ đề hoàn toàn ngoài phạm vi tra từ hoặc cấp độ ngoài A1-A2)
        # -------------------------------------------------------------
        # Kiểm tra yêu cầu về các cấp độ nằm ngoài phạm vi A1–A2 (B1, B2, C1, C2)
        non_a1_a2_match = re.search(r"\b(b1|b2|c1|c2)\b", clean_q, re.IGNORECASE)
        if non_a1_a2_match:
            return RoutingDecision(
                route_type="OUT_OF_SCOPE",
                intent="OUT_OF_SCOPE",
                template_response=settings.OUT_OF_SCOPE_RESPONSE,
                confidence=1.0,
                reason=f"Requested non A1-A2 CEFR level: {non_a1_a2_match.group(1).upper()}"
            )

        # Chỉ coi là OUT_OF_SCOPE nếu:
        # 1. Không có active_word trong tracker từ lượt trước
        # 2. Không chứa từ tiếng Anh nào có trong từ điển (hoặc không trích xuất được từ mục tiêu)
        has_active_topic = bool(tracker and tracker.active_word)
        target_word = tracker.extract_target_word(clean_q) if tracker else None
        vocab_words: Set[str] = getattr(tracker, "vocab_words", set()) if tracker else set()

        # Kiểm tra xem có từ tiếng Anh nào xuất hiện trong câu hỏi không
        tokens = [re.sub(r"^[^\w]+|[^\w]+$", "", t.lower()) for t in clean_q.split()]
        tokens = [t for t in tokens if t]
        has_known_word = bool(target_word) or any(t in vocab_words for t in tokens)

        is_follow_up_or_referential = bool(
            tracker and (tracker.is_referential_query(clean_q) or tracker.is_follow_up_cues(clean_q))
        )
        active_word_in_query = bool(
            tracker and tracker.active_word and
            re.search(r"\b" + re.escape(tracker.active_word.lower()) + r"\b", clean_q.lower())
        )

        if not has_known_word and not is_follow_up_or_referential and not active_word_in_query:
            if any(pat in vn_norm for pat in self.out_of_scope_patterns):
                return RoutingDecision(
                    route_type="OUT_OF_SCOPE",
                    intent="OUT_OF_SCOPE",
                    template_response=settings.OUT_OF_SCOPE_RESPONSE,
                    confidence=0.95,
                    reason="Explicit out-of-scope domain query"
                )

        # -------------------------------------------------------------
        # NHÁNH 3: VOCAB QUERY (Đi vào pipeline: PhoBERT -> Retrieval -> RRF -> Qwen)
        # -------------------------------------------------------------
        return RoutingDecision(
            route_type="VOCAB_QUERY",
            intent="VOCAB_QUERY",
            template_response=None,
            confidence=1.0,
            reason="Vocabulary query routed to PhoBERT + Retrieval pipeline"
        )
