"""Script tải và đóng gói mô hình Kokoro TTS (int8) cùng giọng af_heart vào thư mục data/models/kokoro/.

Đảm bảo sau khi tải:
1. Ứng dụng hoạt động 100% offline, không cần Internet.
2. Không tải lại nếu tệp đã tồn tại đầy đủ và dung lượng hợp lệ.
"""

import os
import sys
from pathlib import Path
import urllib.request
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "kokoro"

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

MODEL_FILE = MODEL_DIR / "kokoro-v1.0.int8.onnx"
VOICES_FILE = MODEL_DIR / "voices-v1.0.bin"

# Expected minimum file sizes in bytes to verify complete download
MIN_MODEL_SIZE = 80 * 1024 * 1024   # ~88-92 MB
MIN_VOICES_SIZE = 20 * 1024 * 1024  # ~28 MB


class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_file(url: str, dest: Path, min_size: int, desc: str):
    if dest.exists() and dest.stat().st_size >= min_size:
        print(f"✅ {desc} đã tồn tại ({dest.stat().st_size / (1024*1024):.1f} MB). Bỏ qua bước tải.")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_suffix(dest.suffix + ".tmp")

    print(f"📥 Đang tải {desc} từ:\n   {url}")
    with DownloadProgressBar(unit="B", unit_scale=True, miniters=1, desc=dest.name) as t:
        urllib.request.urlretrieve(url, filename=tmp_dest, reporthook=t.update_to)

    if tmp_dest.stat().st_size < min_size:
        raise RuntimeError(f"Tệp tải về quá nhỏ ({tmp_dest.stat().st_size} bytes). Có thể bị lỗi kết nối.")

    if dest.exists():
        dest.unlink()
    tmp_dest.rename(dest)
    print(f"✅ Đã tải và lưu thành công: {dest.name} ({dest.stat().st_size / (1024*1024):.1f} MB)")


def main():
    print("=" * 70)
    print("THIẾT LẬP VÀ ĐÓNG GÓI MÔ HÌNH KOKORO TTS CỤC BỘ (100% OFFLINE)")
    print("=" * 70)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        download_file(MODEL_URL, MODEL_FILE, MIN_MODEL_SIZE, "Mô hình Kokoro-v1.0 (int8)")
        download_file(VOICES_URL, VOICES_FILE, MIN_VOICES_SIZE, "Dữ liệu Giọng đọc Kokoro Voices (v1.0)")
        print("\n🎉 Hoàn tất! Tất cả tệp mô hình đã sẵn sàng trong:", MODEL_DIR)
    except Exception as e:
        print(f"\n❌ Lỗi khi tải mô hình Kokoro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
