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
        """Nạp các mẫu ngoài phạm vi (out_of_scope) từ exception_intent.json."""
        if not self.json_path.exists():
            return

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("intents", []):
                    if item.get("intent") == "out_of_scope":
                        for ex in item.get("examples", []):
                            norm = normalize_vietnamese_text(re.sub(r"[^\w\s]", "", ex.strip().lower()))
                            if norm:
                                self.out_of_scope_patterns.append(norm)

            # Bổ sung các chủ đề ngoài phạm vi thông dụng (thời tiết, chứng khoán, tiền ảo, giá vàng...)
            extra_patterns = [
                "bitcoin", "btc", "ethereum", "crypto", "tien ao",
                "gia vang", "gia xang", "chung khoan", "co phieu",
                "thoi tiet", "du bao thoi tiet", "nhiet do",
                "nau an", "cong thuc nau an", "mon an",
                "giai phuong trinh", "toan hoc", "giai toan",
                "viet code", "viet code python", "lap trinh",
                "choi co", "ke chuyen", "ke chuyen cuoi", "ke chuyen co tich",
                "hat mot bai", "tin tuc hom nay", "bong da", "ket qua so xo"
            ]
            for ep in extra_patterns:
                norm_ep = normalize_vietnamese_text(ep)
                if norm_ep not in self.out_of_scope_patterns:
                    self.out_of_scope_patterns.append(norm_ep)

            logger.info("QueryRouter đã nạp %d mẫu câu nhận diện OUT_OF_SCOPE.", len(self.out_of_scope_patterns))
        except Exception as exc:
            logger.error("Lỗi khi nạp mẫu out-of-scope trong QueryRouter: %s", exc)

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
        # NHÁNH 2: OUT OF SCOPE (Chủ đề hoàn toàn ngoài phạm vi tra từ)
        # -------------------------------------------------------------
        # Chỉ coi là OUT_OF_SCOPE nếu:
        # 1. Không có active_word trong tracker từ lượt trước
        # 2. Không chứa từ tiếng Anh nào có trong từ điển
        has_active_topic = bool(tracker and tracker.active_word)
        known_words: Set[str] = tracker.known_words if tracker else set()

        # Kiểm tra xem có từ tiếng Anh nào xuất hiện trong câu hỏi không
        tokens = [re.sub(r"^[^\w]+|[^\w]+$", "", t.lower()) for t in clean_q.split()]
        tokens = [t for t in tokens if t]
        has_known_word = any(t in known_words for t in tokens)

        if not has_active_topic and not has_known_word:
            # Kiểm tra xem câu hỏi có trùng hoặc chứa các mẫu ngoài phạm vi không
            is_explicit_oos = False
            for pat in self.out_of_scope_patterns:
                if pat in vn_norm or vn_norm == pat:
                    is_explicit_oos = True
                    break

            if is_explicit_oos:
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
