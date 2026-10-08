"""Kịch bản dòng lệnh nạp và cập nhật dữ liệu tri thức từ Excel cho Chatbox 2.0.

Sử dụng:
    python ingest_data.py
    python ingest_data.py --file "data/raw/du_lieu_moi.xlsx" --mode append
    python ingest_data.py --file "data/raw/du_lieu_moi.xlsx" --mode replace
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Đảm bảo in tiếng Việt có dấu không bị lỗi UnicodeEncodeError trên Windows (cp1252 / Code Runner / CMD)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo môi trường offline tuyệt đối
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Đảm bảo đường dẫn gốc được nhận diện
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.data.ingestion_manager import IngestionManager


def print_banner():
    banner = r"""
===================================================================
     CHATBOX 2.0 - CÔNG CỤ NẠP VÀ CẬP NHẬT TRI THỨC (DYNAMIC RAG)
  Hỗ trợ 8 định dạng: TXT, PDF, CSV, XLSX, DOCX, JSON, JSONL, MD
===================================================================
    """
    print(banner)


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Công cụ nạp và lập chỉ mục dữ liệu động cho Chatbox 2.0 (Dynamic Knowledge Base)"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=str(settings.RAW_EXCEL_PATH),
        help=f"Đường dẫn tới tệp dữ liệu (TXT, PDF, CSV, XLSX, DOCX, JSON, JSONL, MD). Mặc định: {settings.RAW_EXCEL_PATH}"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["add", "append", "replace"],
        default="add",
        help="Chế độ nạp: 'add'/'append' (bổ sung / cập nhật theo ID) hoặc 'replace' (xóa làm mới toàn bộ)"
    )

    args = parser.parse_args()
    data_path = Path(args.file)

    mode_label = "Làm mới toàn bộ (REPLACE)" if args.mode == "replace" else "Bổ sung / Cập nhật (ADD)"
    print(f"[*] Tệp đầu vào:  {data_path.resolve()}")
    print(f"[*] Chế độ nạp:   {mode_label}")
    print("-" * 67)

    manager = IngestionManager()

    # 1. Kiểm tra sơ bộ tệp
    inspect_info = manager.inspect_file(data_path)
    if not inspect_info.get("valid"):
        print(f"[!] LỖI: {inspect_info.get('error')}")
        sys.exit(1)

    print(f"[+] Tệp hợp lệ ({inspect_info.get('file_size_kb', 0)} KB)")
    if "sheets" in inspect_info:
        print("[+] Các sheet/mục phát hiện:")
        for s_name, rows_count in inspect_info["sheets"].items():
            print(f"    - {s_name}: {rows_count} dòng")
    print("-" * 67)

    # 2. Tiến hành nạp dữ liệu kèm thanh tiến trình
    def progress_callback(pct: float, msg: str):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {int(pct * 100):3d}% | {msg[:35]:<35}")
        sys.stdout.flush()

    print("[*] Bắt đầu quá trình nạp và lập chỉ mục...")
    res = manager.ingest(
        file_path=data_path,
        mode=args.mode,
        progress_callback=progress_callback
    )
    print("\n" + "=" * 67)

    if res.status == "SUCCESS":
        print("🎉 CẬP NHẬT KHO TRI THỨC THÀNH CÔNG!")
        print(f"  • Tổng bản ghi đọc từ tệp:     {res.total_incoming:,}")
        print(f"  • Số bản ghi nạp mới/cập nhật: {res.newly_added:,}")
        print(f"  • Số bản ghi trùng lặp bỏ qua: {res.duplicates_skipped:,}")
        print(f"  • Tổng bản ghi hiện có trong DB:{res.total_active:,}")
        print(f"  • Thời gian xử lý:             {res.elapsed_seconds:.2f} giây")

        if res.sample_words:
            print(f"  • Một số từ vựng/nội dung:     {', '.join(res.sample_words[:8])}")

        print("\n[✔] Kho tri thức đã đồng bộ (Source JSONL = BM25 = ChromaDB). Sẵn sàng tra cứu!")
        print("===================================================================")
    else:
        print(f"[❌] THẤT BẠI: {res.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
