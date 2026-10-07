"""Script tải trước các mô hình Hugging Face vào Local Cache cho máy mới.

Mô hình bao gồm:
1. vinai/phobert-base-v2: Phục vụ Query Understanding / Intent Matching
2. BAAI/bge-m3: Phục vụ Vector Embedding / Semantic Retrieval

Chạy script này khi thiết lập môi trường lần đầu trên máy mới:
    python scripts/download_models.py
"""

import os
import sys
import warnings
from pathlib import Path

# Đảm bảo in tiếng Việt có dấu không bị lỗi UnicodeEncodeError trên Windows (cp1252 / Code Runner / CMD)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Vô hiệu hóa cảnh báo Symlink trên Windows và tắt log thừa từ Hugging Face / Transformers
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
warnings.filterwarnings("ignore")

import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

# Đảm bảo đường dẫn gốc được nhận diện
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings


def is_model_cached(model_name: str) -> bool:
    """Kiểm tra xem mô hình đã tồn tại trong local cache của Hugging Face chưa."""
    try:
        from huggingface_hub import constants
        hub_cache = Path(constants.HF_HUB_CACHE)
    except Exception:
        hub_cache = Path.home() / ".cache" / "huggingface" / "hub"

    folder_name = "models--" + model_name.replace("/", "--")
    model_folder = hub_cache / folder_name
    snapshots_dir = model_folder / "snapshots"
    if snapshots_dir.exists():
        try:
            return any(snapshots_dir.iterdir())
        except Exception:
            return False
    return False


def download_phobert():
    """Tải và kiểm tra mô hình PhoBERT-base-v2."""
    model_name = settings.PHOBERT_MODEL_NAME
    print(f"\n[1/2] Kiểm tra mô hình PhoBERT ({model_name})...")
    
    if is_model_cached(model_name):
        print(f"  [IF] -> Mô hình PhoBERT đã tồn tại sẵn trong Local Cache máy tính.")
        print(f"  -> Đang kiểm tra tải nhanh từ bộ nhớ đệm...")
    else:
        print(f"  [IF] -> Chưa phát hiện PhoBERT trong máy. Bắt đầu tải về (khoảng ~540 MB)...")
        print(f"  -> Đang kết nối tải Tokenizer và Model weights...")

    try:
        from transformers import AutoModel, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        print(f"  [V] PhoBERT-base-v2 đã sẵn sàng trong local cache!")
    except Exception as exc:
        print(f"  [X] Lỗi khi tải PhoBERT: {exc}")
        raise exc


def download_bge_m3():
    """Tải và kiểm tra mô hình BGE-M3."""
    model_name = settings.BGE_M3_MODEL_NAME
    print(f"\n[2/2] Kiểm tra mô hình BGE-M3 ({model_name})...")

    if is_model_cached(model_name):
        print(f"  [IF] -> Mô hình BGE-M3 đã tồn tại sẵn trong Local Cache máy tính.")
        print(f"  -> Đang kiểm tra tải nhanh từ bộ nhớ đệm...")
    else:
        print(f"  [IF] -> Chưa phát hiện BGE-M3 trong máy. Bắt đầu tải về (khoảng ~2.2 GB)...")
        print(f"  -> Đang kết nối tải SentenceTransformer (BGE-M3)...")

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name, device="cpu")
        print(f"  [V] BGE-M3 đã sẵn sàng trong local cache!")
    except Exception as exc:
        print(f"  [X] Lỗi khi tải BGE-M3: {exc}")
        raise exc


def main():
    print("=" * 65)
    print("   CHATBOX 2.0 — CÔNG CỤ TẢI MÔ HÌNH HUGGING FACE LẦN ĐẦU")
    print("=" * 65)
    print("Quá trình này cần kết nối Internet nếu tải mô hình lần đầu về cache.")
    print("Sau khi hoàn tất, hệ thống sẽ chạy 100% OFFLINE mà không cần Internet.")

    try:
        download_phobert()
        download_bge_m3()
        print("\n" + "=" * 65)
        print("🎉 TẤT CẢ MÔ HÌNH NLP ĐÃ ĐƯỢC CACHE THÀNH CÔNG VÀ SẴN SÀNG!")
        print("=" * 65)
    except Exception as e:
        print(f"\n[!] Thao tác tải mô hình gặp sự cố: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
