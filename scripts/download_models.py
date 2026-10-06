"""Script tải trước các mô hình Hugging Face vào Local Cache cho máy mới.

Mô hình bao gồm:
1. vinai/phobert-base-v2: Phục vụ Query Understanding / Intent Matching
2. BAAI/bge-m3: Phục vụ Vector Embedding / Semantic Retrieval

Chạy script này khi thiết lập môi trường lần đầu trên máy mới:
    python scripts/download_models.py
"""

import os
import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc được nhận diện
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings


def download_phobert():
    """Tải và kiểm tra mô hình PhoBERT-base-v2."""
    model_name = settings.PHOBERT_MODEL_NAME
    print(f"\n[1/2] Đang kiểm tra / tải mô hình PhoBERT ({model_name})...")
    try:
        from transformers import AutoModel, AutoTokenizer

        print("  -> Đang tải Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print("  -> Đang tải Model weights...")
        model = AutoModel.from_pretrained(model_name)
        print(f"  [V] PhoBERT-base-v2 đã sẵn sàng trong local cache!")
    except Exception as exc:
        print(f"  [X] Lỗi khi tải PhoBERT: {exc}")
        raise exc


def download_bge_m3():
    """Tải và kiểm tra mô hình BGE-M3."""
    model_name = settings.BGE_M3_MODEL_NAME
    print(f"\n[2/2] Đang kiểm tra / tải mô hình BGE-M3 ({model_name})...")
    try:
        from sentence_transformers import SentenceTransformer

        print("  -> Đang tải SentenceTransformer (BGE-M3)...")
        model = SentenceTransformer(model_name, device="cpu")
        print(f"  [V] BGE-M3 đã sẵn sàng trong local cache!")
    except Exception as exc:
        print(f"  [X] Lỗi khi tải BGE-M3: {exc}")
        raise exc


def main():
    print("=" * 65)
    print("   CHATBOX 2.0 — CÔNG CỤ TẢI MÔ HÌNH HUGGING FACE LẦN ĐẦU")
    print("=" * 65)
    print("Quá trình này cần kết nối Internet để tải mô hình về cache.")
    print("Sau khi hoàn tất, hệ thống sẽ chạy 100% OFFLINE mà không cần Internet.")

    # Cho phép kết nối HuggingFace trong quá trình download ban đầu
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"

    try:
        download_phobert()
        download_bge_m3()
        print("\n" + "=" * 65)
        print("🎉 TẤT CẢ MÔ HÌNH NLP ĐÃ ĐƯỢC TẢI XUỐNG VÀ CACHE THÀNH CÔNG!")
        print("=" * 65)
    except Exception as e:
        print(f"\n[!] Thao tác tải mô hình gặp sự cố: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
