"""Module xử lý các ý định ngoại lệ, chào hỏi và giao tiếp xã giao (Exception & Chitchat Handler).

Tải các quy tắc từ `config/exception_intent.json` để phản hồi tức thì với độ trễ < 1ms:
- Chào hỏi: greeting ("xin chào", "hello", "hi"...)
- Cảm ơn: thanks ("cảm ơn", "thank you"...)
- Tạm biệt: goodbye ("tạm biệt", "bye"...)
- Danh tính bot: chatbot_identity ("bạn là ai?", "bạn tên gì?"...)
- Khả năng bot: chatbot_capabilities ("bạn có thể làm gì?"...)
- Đầu vào vô nghĩa: unclear_input ("asdfgh", "123456", "????"...)
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from src.data.loader import normalize_vietnamese_text

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """Bộ xử lý các ý định ngoại lệ và giao tiếp xã giao."""

    # Các nhóm ý định xử lý trực tiếp phản hồi chitchat / ngoại lệ
    HANDLED_INTENTS = {
        "greeting",
        "thanks",
        "goodbye",
        "chatbot_identity",
        "chatbot_capabilities",
        "unclear_input"
    }

    def __init__(self, json_path: Optional[Path] = None):
        self.json_path = json_path or settings.EXCEPTION_INTENTS_PATH
        self.intent_rules: List[Dict] = []
        self.lookup_map: Dict[str, Tuple[str, str]] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        """Nạp dữ liệu ý định ngoại lệ từ file JSON."""
        if not self.json_path.exists():
            logger.warning("Không tìm thấy tệp ý định ngoại lệ tại: %s", self.json_path)
            return

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.intent_rules = data.get("intents", [])

            for item in self.intent_rules:
                intent = item.get("intent", "")
                response = item.get("response", "")
                examples = item.get("examples", [])

                if intent not in self.HANDLED_INTENTS:
                    continue

                for ex in examples:
                    # Chuẩn hóa cả dạng có dấu và không dấu
                    raw_norm = ex.strip().lower()
                    no_punct = re.sub(r"[^\w\s]", "", raw_norm).strip()
                    vn_norm = normalize_vietnamese_text(no_punct)

                    if no_punct:
                        self.lookup_map[no_punct] = (intent, response)
                    if vn_norm:
                        self.lookup_map[vn_norm] = (intent, response)

            logger.info("ExceptionHandler đã nạp %d mẫu câu ngoại lệ.", len(self.lookup_map))
        except Exception as exc:
            logger.error("Lỗi khi đọc file exception_intent.json: %s", exc)

    def match(self, query: str) -> Optional[Tuple[str, str]]:
        """So khớp câu hỏi với các ý định ngoại lệ.

        Returns:
            Optional[Tuple[str, str]]: (intent_name, response_text) hoặc None nếu không khớp.
        """
        clean_q = query.strip().lower()
        if not clean_q:
            return None

        # 1. Kiểm tra chuỗi vô nghĩa dạng ký tự lặp / chỉ toàn dấu câu / số ngẫu nhiên (unclear_input)
        if re.fullmatch(r"[\?\.\,\!\@\#\$\%\^\&\*\-\_\=\+\s]+", clean_q) or \
           re.fullmatch(r"[0-9\s]{4,}", clean_q) or \
           (len(clean_q) >= 5 and re.fullmatch(r"[a-z0-9]+", clean_q) and not any(c in "aeiou" for c in clean_q)):
            # Tìm response của unclear_input
            for item in self.intent_rules:
                if item.get("intent") == "unclear_input":
                    return "unclear_input", item.get("response", "Vui lòng nhập câu hỏi từ vựng cụ thể.")

        # 2. Chuẩn hóa chuỗi để tra cứu trong lookup map
        no_punct = re.sub(r"[^\w\s]", "", clean_q).strip()
        vn_norm = normalize_vietnamese_text(no_punct)

        if no_punct in self.lookup_map:
            return self.lookup_map[no_punct]
        if vn_norm in self.lookup_map:
            return self.lookup_map[vn_norm]

        # 3. So khớp linh hoạt cho các mẫu chào hỏi / cảm ơn ngắn phổ biến
        if vn_norm in ["xin chao", "chao", "chao ban", "hello", "hi", "hey"]:
            for item in self.intent_rules:
                if item.get("intent") == "greeting":
                    return "greeting", item.get("response")

        if vn_norm in ["cam on", "cam on ban", "thank you", "thanks"]:
            for item in self.intent_rules:
                if item.get("intent") == "thanks":
                    return "thanks", item.get("response")

        if vn_norm in ["tam biet", "bye", "goodbye", "hen gap lai"]:
            for item in self.intent_rules:
                if item.get("intent") == "goodbye":
                    return "goodbye", item.get("response")

        if any(vn_norm == p for p in ["ban la ai", "ban ten gi", "ai la ban", "ban la ai vay"]):
            for item in self.intent_rules:
                if item.get("intent") == "chatbot_identity":
                    return "chatbot_identity", item.get("response")

        if any(vn_norm == p for p in ["ban co the lam gi", "ban ho tro gi", "ban giup duoc gi", "ban lam duoc gi"]):
            for item in self.intent_rules:
                if item.get("intent") == "chatbot_capabilities":
                    return "chatbot_capabilities", item.get("response")

        return None
