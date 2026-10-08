"""Module xử lý hội thoại thông thường và xã giao (Small Talk Handler).

Chịu trách nhiệm nhận diện và phản hồi các câu giao tiếp thông thường:
- GREETING: "Xin chào", "Hello", "Hi", "Chào bạn"...
- THANKS: "Cảm ơn", "Thank you", "Thanks"...
- GOODBYE: "Tạm biệt", "Bye", "Goodbye", "Hẹn gặp lại"...
- CASUAL_CHAT: "Bạn khỏe không?", "Dạo này thế nào?", "How are you"...
- SIMPLE_ACKNOWLEDGEMENT: "Ok", "Được rồi", "oke", "dạ", "vâng", "rõ rồi", "ừ"...
- CHATBOT_IDENTITY: "Bạn là ai?", "Bạn tên gì?"...
- CHATBOT_CAPABILITIES: "Bạn có thể làm gì?", "Bạn hỗ trợ gì?"...
- UNCLEAR_INPUT: "????", "asdfgh", "123456"...

ĐẶC TẢ:
- Không đưa Small Talk vào Hybrid Retrieval.
- Phản hồi siêu tốc (< 1ms) qua template cố định hoặc tùy chọn qua Qwen2.5:7B với prompt riêng.
- Tuyệt đối không dùng Small Talk để thêm vào Knowledge Base hay coi là dữ liệu RAG.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from src.data.loader import normalize_vietnamese_text
from src.llm.client import OllamaClient

logger = logging.getLogger(__name__)


class SmallTalkHandler:
    """Bộ xử lý hội thoại thông thường và xã giao (Small Talk Handler)."""

    HANDLED_INTENTS = {
        "greeting",
        "thanks",
        "goodbye",
        "casual_chat",
        "simple_acknowledgement",
        "chatbot_identity",
        "chatbot_capabilities",
        "unclear_input",
    }

    SMALL_TALK_SYSTEM_PROMPT = (
        "Bạn là trợ lý AI học từ vựng tiếng Anh. Người dùng đang trò chuyện xã giao hoặc gửi tin nhắn ngắn. "
        "Hãy phản hồi một cách ngắn gọn, tự nhiên, lịch sự (dưới 2 câu) và gợi ý người dùng tiếp tục tra cứu từ vựng tiếng Anh. "
        "Tuyệt đối không giải thích sai lệch hoặc tự bịa đặt định nghĩa từ điển."
    )

    def __init__(self, json_path: Optional[Path] = None):
        self.json_path = json_path or settings.EXCEPTION_INTENTS_PATH
        self.intent_rules: List[Dict] = []
        self.lookup_map: Dict[str, Tuple[str, str]] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        """Nạp dữ liệu mẫu câu Small Talk từ file JSON."""
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
                    raw_norm = ex.strip().lower()
                    no_punct = re.sub(r"[^\w\s]", "", raw_norm).strip()
                    vn_norm = normalize_vietnamese_text(no_punct)

                    if no_punct:
                        self.lookup_map[no_punct] = (intent, response)
                    if vn_norm:
                        self.lookup_map[vn_norm] = (intent, response)

            logger.info("SmallTalkHandler đã nạp %d mẫu câu Small Talk.", len(self.lookup_map))
        except Exception as exc:
            logger.error("Lỗi khi đọc file cấu hình Small Talk: %s", exc)

    def match(self, query: str) -> Optional[Tuple[str, str]]:
        """So khớp câu hỏi với các mẫu Small Talk.

        Returns:
            Optional[Tuple[str, str]]: (intent_name, template_response) hoặc None nếu không khớp.
        """
        clean_q = query.strip().lower()
        if not clean_q:
            return None

        # 1. Ký tự vô nghĩa / dấu câu / số ngẫu nhiên (UNCLEAR_INPUT)
        if (
            re.fullmatch(r"[\?\.\,\!\@\#\$\%\^\&\*\-\_\=\+\s]+", clean_q)
            or re.fullmatch(r"[0-9\s]{4,}", clean_q)
            or (len(clean_q) >= 5 and re.fullmatch(r"[a-z0-9]+", clean_q) and not any(c in "aeiou" for c in clean_q))
        ):
            for item in self.intent_rules:
                if item.get("intent") == "unclear_input":
                    return "unclear_input", item.get("response", "Vui lòng nhập câu hỏi từ vựng cụ thể.")

        no_punct = re.sub(r"[^\w\s]", "", clean_q).strip()
        vn_norm = normalize_vietnamese_text(no_punct)

        # 2. Khớp trực tiếp trong từ điển lookup map
        if no_punct in self.lookup_map:
            return self.lookup_map[no_punct]
        if vn_norm in self.lookup_map:
            return self.lookup_map[vn_norm]

        # 3. So khớp linh hoạt theo nhóm ý định Small Talk

        # 3.1. GREETING
        greeting_words = {"xin chao", "xin chao ban", "chao", "chao ban", "hello", "hi", "hey", "alo"}
        if vn_norm in greeting_words or vn_norm.startswith("xin chao") or vn_norm.startswith("chao ban"):
            for item in self.intent_rules:
                if item.get("intent") == "greeting":
                    return "greeting", item.get("response") or "Xin chào! Tôi là chatbot hỗ trợ bạn học và tra cứu từ vựng tiếng Anh."
            return "greeting", "Xin chào! Tôi là chatbot hỗ trợ bạn học và tra cứu từ vựng tiếng Anh."

        # 3.2. THANKS
        if vn_norm in ["cam on", "cam on ban", "thank you", "thanks", "thank", "cam on nhieu"]:
            for item in self.intent_rules:
                if item.get("intent") == "thanks":
                    return "thanks", item.get("response")

        # 3.3. GOODBYE
        if vn_norm in ["tam biet", "bye", "goodbye", "hen gap lai", "chao nhe", "bye bye"]:
            for item in self.intent_rules:
                if item.get("intent") == "goodbye":
                    return "goodbye", item.get("response")

        # 3.4. CASUAL_CHAT (Hỏi thăm sức khỏe, trò chuyện xã giao)
        casual_patterns = [
            "ban khoe khong",
            "khoe khong",
            "khoe ko",
            "co khoe khong",
            "ban co khoe khong",
            "dao nay the nao",
            "the nao roi",
            "how are you",
            "how are you doing",
            "how is it going",
        ]
        if vn_norm in casual_patterns or any(vn_norm == p for p in casual_patterns):
            for item in self.intent_rules:
                if item.get("intent") == "casual_chat":
                    return "casual_chat", item.get("response")

        # 3.5. SIMPLE_ACKNOWLEDGEMENT (Đồng thuận, xác nhận ngắn)
        ack_tokens = [
            "ok", "oke", "oki", "okey", "okay", "alright", "duoc roi", "duoc roi ban",
            "da", "da vang", "vang", "vang a", "ro roi", "hieu roi", "uh", "uhm", "u",
            "yes", "yeah", "yep", "chinh xac", "dung roi"
        ]
        if vn_norm in ack_tokens:
            for item in self.intent_rules:
                if item.get("intent") == "simple_acknowledgement":
                    return "simple_acknowledgement", item.get("response")

        # 3.6. CHATBOT_IDENTITY
        if any(vn_norm == p for p in ["ban la ai", "ban ten gi", "ai la ban", "ban la ai vay", "may la ai"]):
            for item in self.intent_rules:
                if item.get("intent") == "chatbot_identity":
                    return "chatbot_identity", item.get("response")

        # 3.7. CHATBOT_CAPABILITIES
        if any(vn_norm == p for p in ["ban co the lam gi", "ban ho tro gi", "ban giup duoc gi", "ban lam duoc gi"]):
            for item in self.intent_rules:
                if item.get("intent") == "chatbot_capabilities":
                    return "chatbot_capabilities", item.get("response")

        return None

    def handle(
        self,
        query: str,
        intent: str,
        template_response: Optional[str] = None,
        use_llm: bool = False,
        llm_client: Optional[OllamaClient] = None,
    ) -> str:
        """Sinh phản hồi cho câu Small Talk.

        Args:
            query: Câu hỏi người dùng.
            intent: Tên ý định Small Talk.
            template_response: Mẫu phản hồi định sẵn.
            use_llm: True nếu muốn Qwen2.5:7B sinh phản hồi tự nhiên (với prompt riêng).
            llm_client: Ollama client (chỉ dùng nếu use_llm=True).

        Returns:
            str: Nội dung phản hồi.
        """
        # Nếu dùng Qwen cho câu trả lời tự nhiên (không đưa vào RAG/Knowledge base)
        if use_llm and llm_client is not None:
            try:
                prompt = (
                    f"{self.SMALL_TALK_SYSTEM_PROMPT}\n\n"
                    f"Người dùng: {query}\n"
                    f"Trợ lý:"
                )
                answer = llm_client.generate(prompt=prompt, stream=False)
                if answer and answer.strip():
                    return answer.strip()
            except Exception as err:
                logger.warning("Không thể sinh phản hồi Small Talk qua Qwen, fallback về template: %s", err)

        # Mặc định sử dụng template phản hồi (< 1ms, độ tin cậy tuyệt đối)
        if template_response:
            return template_response

        # Fallback từ điển
        for item in self.intent_rules:
            if item.get("intent") == intent.lower():
                return item.get("response", "Xin chào! Tôi có thể giúp gì cho bạn về từ vựng tiếng Anh?")

        return "Xin chào! Hãy cho tôi biết từ tiếng Anh bạn muốn tra cứu nhé."
