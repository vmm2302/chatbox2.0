"""Kịch bản đồng bộ từ vựng Oxford 3000 và tra cứu từ điển dictionary_en_vi.db.

Chức năng:
1. Đọc và lọc sạch các bản ghi lỗi cũ trong qa_records.jsonl.
2. Trích xuất toàn bộ từ vựng Oxford 3000 từ The_Oxford_3000_by_CEFR_level.pdf.
3. Tự động dịch nghĩa, tra phiên âm IPA và ví dụ từ dictionary_en_vi.db.
4. Hợp nhất (Merge) an toàn với dữ liệu Excel hiện có.
5. Lưu trữ lại vào qa_records.jsonl và cập nhật sources_manifest.json.

Sử dụng:
    python scripts/sync_oxford_knowledge.py
"""

import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Đảm bảo in UTF-8 không lỗi trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo đường dẫn gốc
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.core.models import QARecord
from src.data.dictionary_db import DictionaryDBService
from src.data.loader import QALoader
from src.data.loaders.oxford_pdf_loader import OxfordPDFParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync_oxford")


def compute_sha256(file_path: Path) -> str:
    """Tính toán mã băm sha256 của tệp."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sync_oxford_records():
    print("=" * 70)
    print("  CHATBOX 2.0 - ĐỒNG BỘ TỪ VỰNG OXFORD 3000 & TỪ ĐIỂN ANH-VIỆT SQLITE")
    print("=" * 70)

    start_time = time.perf_counter()
    pdf_path = settings.OXFORD_PDF_PATH
    db_path = settings.DICTIONARY_DB_PATH
    jsonl_path = settings.PROCESSED_JSONL_PATH
    manifest_path = settings.SOURCES_MANIFEST_PATH

    print(f"[*] Tệp Oxford PDF:  {pdf_path}")
    print(f"[*] Tệp Database:    {db_path}")
    print(f"[*] Tệp QA JSONL:    {jsonl_path}")
    print("-" * 70)

    if not pdf_path.exists():
        print(f"[!] LỖI: Không tìm thấy tệp Oxford PDF tại {pdf_path}")
        sys.exit(1)
    if not db_path.exists():
        print(f"[!] LỖI: Không tìm thấy tệp từ điển DB tại {db_path}")
        sys.exit(1)

    loader = QALoader(processed_jsonl_path=jsonl_path)

    # 1. Tải danh sách hiện tại và loại bỏ bản ghi PDF bị lỗi trước đây
    existing_records: list[QARecord] = []
    cleaned_records: list[QARecord] = []
    corrupted_count = 0

    if jsonl_path.exists():
        existing_records = loader.load_from_jsonl()
        for r in existing_records:
            # Phát hiện các bản ghi rác từ parser PDF cũ (word rỗng hoặc question dạng trang sách)
            is_corrupted = (
                not r.word.strip()
                or "Nội dung từ The_Oxford" in r.question
                or (r.source == "The_Oxford_3000_by_CEFR_level.pdf" and "Oxford University Press" in r.answer)
            )
            if is_corrupted:
                corrupted_count += 1
            else:
                cleaned_records.append(r)

    print(f"[+] Bản ghi hiện có trong JSONL:    {len(existing_records):,}")
    print(f"[+] Số bản ghi lỗi cũ bị loại bỏ:   {corrupted_count:,}")
    print(f"[+] Bản ghi gốc hợp lệ giữ lại:    {len(cleaned_records):,}")
    print("-" * 70)

    # 2. Khởi tạo dịch vụ tra cứu DB và bóc tách PDF Oxford
    print("[*] Đang đọc tệp The_Oxford_3000_by_CEFR_level.pdf và tra cứu DB...")
    dict_service = DictionaryDBService(db_path=db_path)
    pdf_parser = OxfordPDFParser(dict_service=dict_service)

    try:
        oxford_records = pdf_parser.load(pdf_path)
    finally:
        dict_service.close()

    print(f"[✔] Đã bóc tách thành công {len(oxford_records):,} mục từ vựng từ PDF Oxford 3000.")

    level_stats: dict[str, int] = {}
    for r in oxford_records:
        level_stats[r.level] = level_stats.get(r.level, 0) + 1
    print("    Phân bố cấp độ Oxford:")
    for lvl, count in sorted(level_stats.items()):
        print(f"      • Cấp độ {lvl}: {count:,} từ")
    print("-" * 70)

    # 3. Hợp nhất (Merge) an toàn: Giữ các bản ghi từ Excel chuẩn hóa, thêm các từ Oxford mới
    print("[*] Đang tiến hành hợp nhất dữ liệu...")
    merged_records, added_count, updated_count, dup_count = QALoader.merge_records(
        existing_records=cleaned_records,
        incoming_records=oxford_records,
        return_updated=True,
    )

    print(f"[✔] Kết quả hợp nhất:")
    print(f"    • Thêm mới (Add):      {added_count:,} từ vựng")
    print(f"    • Cập nhật (Update):   {updated_count:,} bản ghi")
    print(f"    • Trùng lặp (Skip):    {dup_count:,} bản ghi")
    print(f"    • Tổng bản ghi sau đó: {len(merged_records):,} bản ghi")
    print("-" * 70)

    # 4. Lưu lại vào qa_records.jsonl
    print(f"[*] Đang ghi {len(merged_records):,} bản ghi vào {jsonl_path}...")
    loader.save_to_jsonl(merged_records)

    # 5. Cập nhật sources_manifest.json
    manifest_data = {"sources": {}}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            manifest_data = {"sources": {}}

    # Lấy danh sách ID thuộc file PDF
    oxford_file_name = pdf_path.name
    oxford_record_ids = [r.record_id for r in merged_records if r.source == oxford_file_name]
    oxford_hash = compute_sha256(pdf_path)
    oxford_source_id = f"SRC_{oxford_hash[:12]}"

    # Xóa key cũ nếu có
    sources_dict = manifest_data.get("sources", {})
    keys_to_delete = [
        k for k, v in sources_dict.items()
        if v.get("file_name") == oxford_file_name
    ]
    for k in keys_to_delete:
        del sources_dict[k]

    # Ghi lại metadata chính xác
    sources_dict[oxford_source_id] = {
        "source_id": oxford_source_id,
        "file_name": oxford_file_name,
        "file_path": str(pdf_path.resolve()),
        "file_hash": oxford_hash,
        "file_type": "pdf",
        "file_size_bytes": pdf_path.stat().st_size,
        "record_count": len(oxford_record_ids),
        "record_ids": oxford_record_ids,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
    }
    manifest_data["sources"] = sources_dict

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    elapsed = time.perf_counter() - start_time
    print(f"[✔] Cập nhật sources_manifest.json thành công ({len(oxford_record_ids):,} ID cho Oxford PDF).")
    print("=" * 70)
    print(f"🎉 HOÀN THÀNH ĐỒNG BỘ DỮ LIỆU TRONG {elapsed:.2f} GIÂY!")
    print(f"   Kho tri thức qa_records.jsonl hiện có {len(merged_records):,} bản ghi chuẩn mực.")
    print("=" * 70)


if __name__ == "__main__":
    sync_oxford_records()
