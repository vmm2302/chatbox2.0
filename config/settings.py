"""Module cấu hình trung tâm cho Chatbox 2.0.

Không hardcode bất kỳ giá trị cấu hình nào trong mã nguồn logic.
Mọi đường dẫn, tham số mô hình và ngưỡng tương đồng đều được định nghĩa tại đây.
"""

from dataclasses import dataclass
from pathlib import Path


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
    RAW_EXCEL_FILENAME: str = "datahotrohoctuvungtienganhtuA1-B2fix.xlsx"
    RAW_EXCEL_PATH: Path = RAW_DATA_DIR / RAW_EXCEL_FILENAME
    PROCESSED_JSONL_PATH: Path = PROCESSED_DATA_DIR / "qa_records.jsonl"

    # Cấu hình ChromaDB
    CHROMA_COLLECTION_NAME: str = "english_vocab_master"

    # Cấu hình Model BGE-M3 (Semantic Retrieval - Embedding chính)
    BGE_M3_MODEL_NAME: str = "BAAI/bge-m3"
    BGE_EMBEDDING_DIM: int = 1024

    # Cấu hình Model PhoBERT-base-v2 (Query Understanding & Intent Matching)
    PHOBERT_MODEL_NAME: str = "vinai/phobert-base-v2"

    # Cấu hình Ollama Cục bộ (Localhost)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0
    LLM_TEMPERATURE: float = 0.1  # Thấp để bám sát tri thức dataset

    # Cấu hình Hybrid Retrieval & Reciprocal Rank Fusion (RRF)
    RRF_K: int = 60                     # Tham số điều hòa chuẩn trong RRF
    BM25_TOP_K: int = 15                # Số ứng viên lấy từ BM25
    BGE_TOP_K: int = 15                 # Số ứng viên lấy từ BGE-M3
    FINAL_TOP_K: int = 3                # Số ứng viên cuối cùng gửi tới RAG / Gate
    TOP_K_RETRIEVAL: int = 3            # Alias số ứng viên truy xuất RRF
    FALLBACK_RRF_THRESHOLD: float = 0.005 # Ngưỡng tối thiểu chấp nhận ứng viên RRF

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
    CLARIFICATION_PROMPT: str = (
        "Bạn đang muốn tra từ tiếng Anh nào? Hãy gửi từ hoặc nội dung bạn muốn tra cứu nhé."
    )
    OLLAMA_OFFLINE_RESPONSE: str = (
        "⚠️ Lỗi kết nối: Dịch vụ Ollama chưa được khởi động trên máy tính! "
        "Vui lòng bật Ollama và thử lại."
    )


# Khởi tạo singleton settings để sử dụng xuyên suốt ứng dụng
settings = Settings()
