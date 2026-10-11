"""Module cấu hình trung tâm cho Chatbox 2.0.

Không hardcode bất kỳ giá trị cấu hình nào trong mã nguồn logic.
Mọi đường dẫn, tham số mô hình và ngưỡng tương đồng đều được định nghĩa tại đây.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Nạp biến môi trường từ .env nếu có
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    pass


def _resolve_raw_excel_path() -> Path:
    """Tự động phát hiện đường dẫn tệp Excel thô hợp lệ trong thư mục data/raw/."""
    raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    custom_name = os.getenv("RAW_EXCEL_FILENAME", "datahotrohoctuvungtienganhtuA1-B2fix.xlsx")
    preferred = raw_dir / custom_name
    if preferred.exists():
        return preferred
    # Fallback sang tệp v3 chuẩn hóa thực tế
    fallback_v3 = raw_dir / "du_lieu_tu_vung_RAG_chuan_hoa_v3.xlsx"
    if fallback_v3.exists():
        return fallback_v3
    # Fallback sang tệp .xlsx bất kỳ trong data/raw/
    for p in raw_dir.glob("*.xlsx"):
        return p
    return preferred


@dataclass(frozen=True)
class Settings:
    """Các thiết lập cấu hình tĩnh của hệ thống Chatbox 2.0 (Master Architecture)."""

    # Đường dẫn thư mục gốc và dữ liệu
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    CHROMA_DIR: Path = BASE_DIR / "chroma_db"

    # Tệp dữ liệu đầu vào và tệp xử lý trung gian
    RAW_EXCEL_FILENAME: str = field(default_factory=lambda: os.getenv("RAW_EXCEL_FILENAME", "datahotrohoctuvungtienganhtuA1-B2fix.xlsx"))
    RAW_EXCEL_PATH: Path = field(default_factory=_resolve_raw_excel_path)
    PROCESSED_JSONL_PATH: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "processed" / "qa_records.jsonl")
    SOURCES_MANIFEST_PATH: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "processed" / "sources_manifest.json")
    EXCEPTION_INTENTS_PATH: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "config" / "exception_intent.json")
    EMBEDDINGS_PATH: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "processed" / "embeddings.npy")

    # Cấu hình ChromaDB
    CHROMA_COLLECTION_NAME: str = field(default_factory=lambda: os.getenv("CHROMA_COLLECTION_NAME", "english_vocab_master"))

    # Cấu hình Model BGE-M3 (Semantic Retrieval - Embedding chính)
    BGE_M3_MODEL_NAME: str = field(default_factory=lambda: os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3"))
    BGE_EMBEDDING_DIM: int = 1024

    # Cấu hình Model PhoBERT-base-v2 (Query Understanding & Intent Matching)
    PHOBERT_MODEL_NAME: str = field(default_factory=lambda: os.getenv("PHOBERT_MODEL_NAME", "vinai/phobert-base-v2"))

    # Cấu hình Ollama Cục bộ (Localhost)
    OLLAMA_BASE_URL: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    OLLAMA_MODEL: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
    OLLAMA_TIMEOUT_SECONDS: float = field(default_factory=lambda: float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0")))
    LLM_TEMPERATURE: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))

    # Cấu hình Hybrid Retrieval & Reciprocal Rank Fusion (RRF)
    RRF_K: int = field(default_factory=lambda: int(os.getenv("RRF_K", "60")))
    BM25_TOP_K: int = 15                # Số ứng viên lấy từ BM25
    BGE_TOP_K: int = 15                 # Số ứng viên lấy từ BGE-M3
    FINAL_TOP_K: int = 3                # Số ứng viên cuối cùng gửi tới RAG / Gate
    TOP_K_RETRIEVAL: int = field(default_factory=lambda: int(os.getenv("TOP_K_RETRIEVAL", "3")))
    FALLBACK_RRF_THRESHOLD: float = field(default_factory=lambda: float(os.getenv("FALLBACK_RRF_THRESHOLD", "0.005")))

    # Ngưỡng RRF Relevance Gate (Initial Hypotheses phục vụ benchmark)
    DIRECT_MATCH_RRF_THRESHOLD: float = 0.033   # Đòi hỏi top 1 ở cả BM25 & BGE -> Trả lời gốc
    RAG_RRF_THRESHOLD: float = 0.012            # Khớp tốt -> Đưa vào Qwen diễn đạt
    CLARIFICATION_SIMILARITY_MIN: float = 0.40  # Dưới ngưỡng này khi thiếu topic -> Hỏi lại


    # Thuộc tính tương thích ngược cho unit tests cũ
    DIRECT_MATCH_THRESHOLD: float = 0.88
    RAG_THRESHOLD: float = 0.60
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"



    # Câu phản hồi chuẩn khi ngoài phạm vi tri thức hoặc lỗi
    OUT_OF_SCOPE_RESPONSE: str = (
        "Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ."
    )
    EMPTY_KB_RESPONSE: str = (
        "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này. "
        "Vui lòng nạp thêm tài liệu vào hệ thống."
    )
    CLARIFICATION_PROMPT: str = (
        "Bạn đang muốn tra từ tiếng Anh nào? Hãy gửi từ hoặc nội dung bạn muốn tra cứu nhé."
    )
    OLLAMA_OFFLINE_RESPONSE: str = (
        "⚠️ Lỗi kết nối: Dịch vụ Ollama chưa được khởi động trên máy tính! "
        "Vui lòng bật Ollama và thử lại."
    )


# Khởi tạo singleton settings để sử dụng xuyên suốt ứng dụng
settings = Settings()
