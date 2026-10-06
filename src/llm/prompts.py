"""Module định nghĩa các mẫu Prompt nghiêm ngặt cho mô hình Qwen2.5:7B.

Khóa hoàn toàn kiến thức suy diễn của LLM, chỉ cho phép diễn đạt dựa trên ngữ cảnh trích xuất.
"""

from typing import List

from config.settings import settings
from src.core.models import RetrievalResult

SYSTEM_PROMPT = """Bạn là trợ lý giải đáp và diễn đạt thông tin tra cứu từ vựng tiếng Anh cho người Việt.

QUY TẮC CỐT LÕI (BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI):
1. BẠN CHỈ ĐƯỢC PHÉP TRẢ LỜI DỰA TRÊN [NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP].
2. TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài ngữ cảnh để suy đoán, tự bịa hoặc bổ sung thông tin.
3. Không trả lời các câu hỏi ngoài phạm vi tài liệu (địa lý, lịch sử, toán học, thời sự, đời sống...).
4. Nếu thông tin trong ngữ cảnh không đủ để trả lời câu hỏi của người dùng, BẮT BUỘC trả lời đúng câu mẫu sau:
"{out_of_scope_message}"
5. QUY TẮC NGÔN NGỮ:
   - Sử dụng 100% tiếng Việt chuẩn (chữ Quốc ngữ Latinh) và tiếng Anh trong ví dụ.
   - TUYỆT ĐỐI KHÔNG xuất hiện bất kỳ chữ Hán / ký tự tiếng Trung Quốc nào trong câu trả lời.
6. Diễn đạt ngắn gọn, rõ ràng, lịch sự và chính xác đúng theo ngữ cảnh.
""".format(out_of_scope_message=settings.OUT_OF_SCOPE_RESPONSE)

# Bí danh tương thích cho giao diện cấu hình
PROMPT_TEMPLATE = SYSTEM_PROMPT


from langchain_core.prompts import ChatPromptTemplate


def build_context_string(contexts: List[RetrievalResult]) -> str:
    """Ghép nối nội dung các bản ghi trích xuất thành chuỗi ngữ cảnh rõ ràng."""
    context_text_pieces = []
    for idx, c in enumerate(contexts, 1):
        level_info = f", Trình độ: {c.record.level}" if c.record.level else ""
        word_info = f", Từ vựng: {c.record.word}" if c.record.word else ""
        context_text_pieces.append(
            f"--- BẢN GHI DỮ LIỆU #{idx} (Mã: {c.record.id}{word_info}{level_info}, Nguồn: {c.record.source}) ---\n"
            f"Câu hỏi gốc: {c.record.question}\n"
            f"Câu trả lời trong dữ liệu:\n{c.record.answer}\n"
        )
    return "\n".join(context_text_pieces)


def build_rag_prompt(query: str, contexts: List[RetrievalResult]) -> List[dict]:
    """Tạo cấu trúc tin nhắn chuẩn gửi tới Ollama Chat API."""
    joined_context = build_context_string(contexts)

    user_content = (
        f"[NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP]:\n"
        f"{joined_context}\n"
        f"-----------------------------------------\n"
        f"[CÂU HỎI CỦA NGƯỜI DÙNG]: {query}\n\n"
        f"Hãy trả lời câu hỏi của người dùng CHỈ DỰA VÀO các thông tin có trong ngữ cảnh trên."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]


def get_langchain_prompt_template() -> ChatPromptTemplate:
    """Trả về LangChain ChatPromptTemplate chuẩn hóa cho RAG chain."""
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", (
            "[NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP]:\n"
            "{context}\n"
            "-----------------------------------------\n"
            "[CÂU HỎI CỦA NGƯỜI DÙNG]: {question}\n\n"
            "Hãy trả lời câu hỏi của người dùng CHỈ DỰA VÀO các thông tin có trong ngữ cảnh trên."
        ))
    ])

