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
     CHATBOX 2.0 - CÔNG CỤ NẠP VÀ CẬP NHẬT TRI THỨC EXCEL (RAG)
===================================================================
    """
    print(banner)


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Công cụ nạp và lập chỉ mục dữ liệu Excel cho Chatbot Tra Cứu Từ Vựng Tiếng Anh"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=str(settings.RAW_EXCEL_PATH),
        help=f"Đường dẫn tới tệp Excel (.xlsx). Mặc định: {settings.RAW_EXCEL_PATH}"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["append", "replace"],
        default="append",
        help="Chế độ nạp: 'append' (bổ sung từ mới, khuyên dùng) hoặc 'replace' (xóa làm mới toàn bộ)"
    )

    args = parser.parse_args()
    excel_path = Path(args.file)

    print(f"[*] Tệp đầu vào:  {excel_path.resolve()}")
    print(f"[*] Chế độ nạp:   {'Bổ sung từ mới (APPEND)' if args.mode == 'append' else 'Làm mới toàn bộ (REPLACE)'}")
    print("-" * 67)

    manager = IngestionManager()

    # 1. Kiểm tra sơ bộ tệp Excel
    inspect_info = manager.inspect_excel(excel_path)
    if not inspect_info.get("valid"):
        print(f"[!] LỖI: {inspect_info.get('error')}")
        sys.exit(1)

    print(f"[+] Tệp hợp lệ ({inspect_info['file_size_kb']} KB)")
    print("[+] Các sheet phát hiện:")
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
        excel_path=excel_path,
        mode=args.mode,
        progress_callback=progress_callback
    )
    print("\n" + "=" * 67)

    if res.status == "SUCCESS":
        print("🎉 CẬP NHẬT KHO TRI THỨC THÀNH CÔNG!")
        print(f"  • Tổng bản ghi đọc từ Excel:    {res.total_incoming:,}")
        print(f"  • Số bản ghi mới được nạp:      {res.newly_added:,}")
        print(f"  • Số bản ghi trùng lặp bỏ qua:  {res.duplicates_skipped:,}")
        print(f"  • Tổng bản ghi hiện có trong DB: {res.total_active:,}")
        print(f"  • Thời gian xử lý:              {res.elapsed_seconds:.2f} giây")

        if res.sample_words:
            print(f"  • Một số từ vựng mới:           {', '.join(res.sample_words[:8])}")

        print("\n[✔] Bây giờ bạn có thể mở Streamlit hoặc chạy Chatbox để tra cứu ngay!")
        print("===================================================================")
    else:
        print(f"[❌] THẤT BẠI: {res.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
