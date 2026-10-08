"""Module phân tích ý định người dùng (Query Understanding) sử dụng PhoBERT-base-v2.

Triển khai phương pháp: Prototype-based Intent Classification using PhoBERT Representations.
So khớp độ tương đồng ngữ nghĩa (Cosine Similarity) giữa biểu diễn vector ngữ cảnh của PhoBERT
với tập hợp các Intent Prototypes chuẩn hóa tiếng Việt, không tự ý train classifier head giả lập.
"""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import torch
from transformers import AutoModel, AutoTokenizer

from config.settings import settings
from src.chat.topic_tracker import TopicTracker
from src.core.models import IntentResult, IntentType


logger = logging.getLogger(__name__)

# Khóa chế độ offline cho HuggingFace
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Danh mục các Intent và Prototype Examples mẫu tiếng Việt
INTENT_PROTOTYPES: Dict[IntentType, List[str]] = {
    "DEFINE_VOCAB": [
        "Tra cứu nghĩa của một từ tiếng Anh",
        "Giải thích từ này có nghĩa gì",
        "Cho tôi biết ý nghĩa của từ vựng này",
        "Từ này nghĩa là gì vậy bạn",
        "Giải thích nghĩa và phát âm của từ"
    ],
    "GET_EXAMPLE": [
        "Cho tôi câu ví dụ của từ này",
        "Ví dụ sử dụng từ này trong câu",
        "Đặt một câu ví dụ với từ vựng trên",
        "Từ này dùng trong ngữ cảnh nào cho ví dụ"
    ],
    "GET_LEVEL_LIST": [
        "Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A1",
        "Danh sách từ vựng tiếng Anh theo cấp độ B2",
        "Liệt kê các từ trong trình độ B1 hoặc A2",
        "Các từ vựng tiếng Anh thuộc trình độ A2"
    ],
    "TRANSLATE_VIE_TO_ENG": [
        "Từ nào có nghĩa là từ bỏ",
        "Từ này trong tiếng Anh là gì",
        "Dịch từ tiếng Việt này sang tiếng Anh",
        "Tiếng Anh của từ này viết thế nào",
        "Nghĩa tiếng Anh của từ là gì",
        "Tìm từ tiếng Anh mang nghĩa này"
    ],

    "FOLLOW_UP": [
        "Còn cách dùng thì sao",
        "Còn dạng danh từ của từ này thì sao",
        "Còn câu ví dụ thì thế nào",
        "Dạng tính từ hoặc trạng từ của từ đó là gì",
        "Thế còn trình độ của nó"
    ],
    "OUT_OF_SCOPE": [
        "Thời tiết tại Hà Nội hôm nay thế nào",
        "Thủ đô của nước Pháp là gì",
        "Giải phương trình toán học bậc hai",
        "Ai là người đầu tiên đặt chân lên mặt trăng",
        "Giá tiền Bitcoin và tiền mã hóa hôm nay"
    ]
}


class PhoBERTIntentClassifier:
    """Lớp phân loại ý định dựa trên biểu diễn vector ngữ nghĩa của PhoBERT-base-v2."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.PHOBERT_MODEL_NAME
        self.tokenizer = None
        self.model = None
        self.prototype_embeddings: Dict[IntentType, torch.Tensor] = {}
        self._is_ready = False

    def initialize(self) -> None:
        """Nạp mô hình PhoBERT offline và tính sẵn vector cho các intent prototypes."""
        if self._is_ready:
            return

        logger.info("Đang nạp mô hình PhoBERT-base-v2 từ local cache...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
            self.model = AutoModel.from_pretrained(self.model_name, local_files_only=True)
        except Exception as exc:
            logger.info("Chưa có cache cục bộ cho PhoBERT (%s), đang tải từ Hugging Face...", exc)
            old_hf = os.environ.pop("HF_HUB_OFFLINE", None)
            old_tr = os.environ.pop("TRANSFORMERS_OFFLINE", None)
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=False)
                self.model = AutoModel.from_pretrained(self.model_name, local_files_only=False)
            finally:
                if old_hf:
                    os.environ["HF_HUB_OFFLINE"] = old_hf
                if old_tr:
                    os.environ["TRANSFORMERS_OFFLINE"] = old_tr
        self.model.eval()

        logger.info("Bắt đầu tính toán biểu diễn vector cho các Intent Prototypes...")
        with torch.no_grad():
            for intent, examples in INTENT_PROTOTYPES.items():
                vectors = []
                for ex in examples:
                    v = self._encode_sentence(ex)
                    vectors.append(v)
                # Tính vector trung bình (centroid) đại diện cho Intent và chuẩn hóa đơn vị
                stacked = torch.stack(vectors)
                centroid = torch.mean(stacked, dim=0)
                centroid = centroid / torch.norm(centroid, dim=-1, keepdim=True)
                self.prototype_embeddings[intent] = centroid

        self._is_ready = True
        logger.info("PhoBERT Intent Classifier đã sẵn sàng với %d nhóm ý định.", len(self.prototype_embeddings))

    def _encode_sentence(self, text: str) -> torch.Tensor:
        """Mã hóa một câu văn thành vector 768 chiều qua mean pooling của PhoBERT."""
        with torch.no_grad():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=128,
                padding=True
            )
            outputs = self.model(**inputs)
            # Mean pooling có xét đến attention_mask
            last_hidden = outputs.last_hidden_state  # shape: (1, seq_len, 768)
            mask = inputs["attention_mask"].unsqueeze(-1).expand(last_hidden.size()).float()
            sum_embeddings = torch.sum(last_hidden * mask, dim=1)
            sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask
            # Chuẩn hóa L2
            normalized = mean_pooled / torch.norm(mean_pooled, dim=-1, keepdim=True)
            return normalized.squeeze(0)


    def classify_intent(
        self,
        query: str,
        has_active_topic: bool = False,
        tracker: Optional[TopicTracker] = None
    ) -> IntentResult:
        """Phân loại ý định câu hỏi người dùng bằng PhoBERT representation similarity.

        Args:
            query: Câu hỏi thô từ người dùng.
            has_active_topic: Phiên hội thoại hiện tại có từ vựng đang được nói đến hay không.
            tracker: Đối tượng TopicTracker để hỗ trợ trích xuất thực thể chuẩn xác.

        Returns:
            IntentResult chứa Intent, điểm Confidence và các Slot trích xuất.
        """
        if not self._is_ready:
            self.initialize()

        clean_query = query.strip()
        if not clean_query:
            return IntentResult(
                intent="AMBIGUOUS",
                confidence=0.0,
                is_ambiguous=True,
                raw_query=""
            )

        # 1. Trích xuất Slot từ vựng tiếng Anh và Level
        active_tracker = tracker or TopicTracker()
        target_word = active_tracker.extract_target_word(clean_query)
        target_level = active_tracker.extract_target_level(clean_query)


        # 2. Quy tắc phát hiện câu hỏi nối tiếp (Follow-up heuristics)
        follow_up_cues = ["còn", "thế còn", "vậy còn", "dạng từ", "dạng danh từ", "dạng tính từ", "ví dụ nữa"]
        is_follow_up_cue = any(clean_query.lower().startswith(cue) or f" {cue} " in clean_query.lower() for cue in follow_up_cues)

        # 3. Tính toán vector câu hỏi qua PhoBERT (chuẩn hóa chữ thường để đồng nhất biểu diễn)
        query_vector = self._encode_sentence(clean_query.lower())

        # 4. So sánh cosine similarity với tất cả các Intent Prototype Centroids
        best_intent: IntentType = "OUT_OF_SCOPE"
        best_score = -1.0

        for intent, centroid in self.prototype_embeddings.items():
            sim = float(torch.dot(query_vector, centroid))
            if sim > best_score:
                best_score = sim
                best_intent = intent

        # Heuristic phát hiện câu hỏi dịch tiếng Việt sang tiếng Anh
        translate_cues = ["từ nào", "dịch từ", "sang tiếng anh", "trong tiếng anh", "tiếng anh là gì", "nghĩa tiếng anh", "tìm từ"]
        if any(c in clean_query.lower() for c in translate_cues):
            best_intent = "TRANSLATE_VIE_TO_ENG"

        # Nếu có từ tiếng Anh mục tiêu và hỏi giải nghĩa từ ("nghĩa là gì", "có nghĩa là gì", "nghĩa của", "what does ... mean")
        q_lower = clean_query.lower()
        def_cues = ["nghĩa là gì", "có nghĩa là gì", "nghĩa của", "nghĩa từ", "nghĩa sao", "là gì", "mean in vietnamese", "what does", "meaning of", "mean?"]
        if target_word and any(k in q_lower for k in def_cues):
            best_intent = "DEFINE_VOCAB"

        # Heuristic phát hiện câu hỏi danh sách theo cấp độ
        if target_level and ("danh sách" in clean_query.lower() or "trình độ" in clean_query.lower() or "cấp độ" in clean_query.lower()):
            best_intent = "GET_LEVEL_LIST"

        # Điều chỉnh intent nếu phát hiện dấu hiệu follow-up kết hợp với trạng thái hội thoại
        if is_follow_up_cue and has_active_topic:
            best_intent = "FOLLOW_UP"

        # 5. Phát hiện câu hỏi mơ hồ (Ambiguous Query)
        # Chỉ áp dụng khi câu hỏi không phải là dịch thuật, danh sách cấp độ, hoặc ngoài phạm vi
        is_ambiguous = False
        if best_intent not in ("TRANSLATE_VIE_TO_ENG", "GET_LEVEL_LIST", "OUT_OF_SCOPE"):
            ambiguous_cues = ["từ này", "tu nay", "từ đó", "tu do", "từ trên", "tu tren"]
            if any(c in clean_query.lower() for c in ambiguous_cues) and not target_word and not has_active_topic:
                is_ambiguous = True
                best_intent = "AMBIGUOUS"

            # Nếu hỏi "nghĩa là gì" mà không có từ vựng và không có topic
            if not target_word and not has_active_topic and best_intent == "DEFINE_VOCAB":
                is_ambiguous = True
                best_intent = "AMBIGUOUS"

        return IntentResult(
            intent=best_intent,
            confidence=round(max(0.0, best_score), 4),
            target_word=target_word,
            target_level=target_level,
            is_follow_up=(best_intent == "FOLLOW_UP"),
            is_ambiguous=is_ambiguous,
            raw_query=clean_query
        )

