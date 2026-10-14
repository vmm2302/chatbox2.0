"""Kịch bản thu gọn và cắt giảm dung lượng file dictionary_en_vi.db.

Chức năng:
1. Thu thập toàn bộ danh sách từ vựng thuộc trình độ A1 đến B2 (từ Oxford 3000 và qa_records.jsonl).
2. Tự động sao lưu bản gốc dictionary_en_vi.db sang dictionary_en_vi.db.backup.
3. Tạo cơ sở dữ liệu mới chỉ chứa các từ vựng thuộc phạm vi A1-B2 kèm đầy đủ phiên âm,
   phân loại từ loại, giải nghĩa tiếng Việt và ví dụ minh họa.
4. Tối ưu hóa lưu trữ với VACUUM và tạo lại chỉ mục tìm kiếm (Indexes).
5. Kiểm tra toàn vẹn cấu trúc (Integrity Check) trước khi áp dụng.

Sử dụng:
    python scripts/prune_dictionary_db.py
"""

import json
import logging
import os
import shutil
import sqlite3
import sys
import time
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
from src.data.loaders.oxford_pdf_loader import OxfordPDFParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("prune_db")


def collect_target_words() -> set[str]:
    """Thu thập toàn bộ từ vựng A1 - B2 từ Oxford 3000 và qa_records.jsonl."""
    target_words: set[str] = set()

    # 1. Từ qa_records.jsonl
    jsonl_path = settings.PROCESSED_JSONL_PATH
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    w = data.get("word", "").strip().lower()
                    if w:
                        target_words.add(w)
                        if "/" in w:
                            target_words.add(w.split("/")[0].strip())
                        if "," in w:
                            target_words.add(w.split(",")[0].strip())
                        if " " in w:
                            target_words.add(w.replace(" ", "-"))
                        if "-" in w:
                            target_words.add(w.replace("-", " "))
                except Exception:
                    pass

    # 2. Từ The_Oxford_3000_by_CEFR_level.pdf
    pdf_path = settings.OXFORD_PDF_PATH
    if pdf_path.exists():
        try:
            entries = OxfordPDFParser.parse_oxford_entries(pdf_path)
            for e in entries:
                clean_w = e.get("clean_word", "").strip().lower()
                base_w = e.get("base_word", "").strip().lower()
                if clean_w:
                    target_words.add(clean_w)
                    if " " in clean_w:
                        target_words.add(clean_w.replace(" ", "-"))
                    if "-" in clean_w:
                        target_words.add(clean_w.replace("-", " "))
                if base_w:
                    target_words.add(base_w)
                    if " " in base_w:
                        target_words.add(base_w.replace(" ", "-"))
                    if "-" in base_w:
                        target_words.add(base_w.replace("-", " "))
        except Exception as err:
            logger.warning("Không thể đọc thêm từ Oxford PDF: %s", err)

    return target_words


def prune_dictionary_database():
    print("=" * 70)
    print("  CHATBOX 2.0 - THU GỌN CƠ SỞ DỮ LIỆU TỪ ĐIỂN dictionary_en_vi.db")
    print("  (Giảm dung lượng từ 42 MB xuống ~3.4 MB theo danh mục từ A1 đến B2)")
    print("=" * 70)

    start_time = time.perf_counter()
    db_path = settings.DICTIONARY_DB_PATH
    backup_path = db_path.with_name("dictionary_en_vi.db.backup")
    temp_db_path = db_path.with_name("dictionary_en_vi_pruned_temp.db")

    if not db_path.exists():
        print(f"[!] LỖI: Không tìm thấy tệp cơ sở dữ liệu tại {db_path}")
        sys.exit(1)

    original_size = db_path.stat().st_size
    print(f"[*] Tệp nguồn:       {db_path}")
    print(f"[*] Kích thước gốc:  {original_size / (1024 * 1024):.2f} MB ({original_size:,} bytes)")
    print(f"[*] Tệp sao lưu:     {backup_path}")
    print("-" * 70)

    # 1. Sao lưu file gốc
    print("[*] Đang sao lưu file gốc sang dictionary_en_vi.db.backup...")
    shutil.copy2(db_path, backup_path)
    print(f"[✔] Đã sao lưu thành công ({backup_path.stat().st_size:,} bytes).")
    print("-" * 70)

    # 2. Thu thập danh sách từ vựng mục tiêu
    print("[*] Đang thu thập danh sách từ vựng mục tiêu A1 - B2...")
    target_words = collect_target_words()
    print(f"[✔] Đã thu thập {len(target_words):,} từ vựng mục tiêu (kèm các biến thể).")
    print("-" * 70)

    # 3. Kết nối DB nguồn và tạo DB tạm
    if temp_db_path.exists():
        temp_db_path.unlink()

    src_conn = sqlite3.connect(str(db_path))
    src_c = src_conn.cursor()

    dst_conn = sqlite3.connect(str(temp_db_path))
    dst_c = dst_conn.cursor()

    # Tạo bảng theo DDL gốc
    print("[*] Đang tạo cấu trúc bảng trên cơ sở dữ liệu mới...")
    src_c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ('words', 'pronunciations', 'word_definitions', 'definitions');")
    tables_ddl = src_c.fetchall()
    for t_name, sql in tables_ddl:
        if sql:
            dst_c.execute(sql)

    # 4. Sao chép bảng words (chỉ lấy các từ thuộc target_words)
    print("[*] Đang lọc và sao chép bảng 'words'...")
    src_c.execute("SELECT id, word, lang_code FROM words;")
    all_words = src_c.fetchall()

    kept_words = []
    kept_word_ids: set[int] = set()

    for wid, w, lang in all_words:
        if w:
            w_lower = w.lower().strip()
            if w_lower in target_words or w_lower.replace("-", " ") in target_words or w_lower.replace(" ", "-") in target_words:
                kept_words.append((wid, w, lang))
                kept_word_ids.add(wid)

    dst_c.executemany("INSERT INTO words (id, word, lang_code) VALUES (?, ?, ?);", kept_words)
    print(f"[✔] Đã giữ lại {len(kept_words):,} / {len(all_words):,} từ vựng.")

    # 5. Sao chép bảng pronunciations
    print("[*] Đang sao chép phiên âm 'pronunciations'...")
    src_c.execute("SELECT id, word_id, ipa, region FROM pronunciations;")
    all_prons = src_c.fetchall()
    kept_prons = [r for r in all_prons if r[1] in kept_word_ids]
    dst_c.executemany("INSERT INTO pronunciations (id, word_id, ipa, region) VALUES (?, ?, ?, ?);", kept_prons)
    print(f"[✔] Đã giữ lại {len(kept_prons):,} / {len(all_prons):,} phiên âm.")

    # 6. Sao chép bảng word_definitions
    print("[*] Đang sao chép liên kết 'word_definitions'...")
    src_c.execute("SELECT id, word_id, definition_id, example FROM word_definitions;")
    all_wd = src_c.fetchall()
    kept_wd = [r for r in all_wd if r[1] in kept_word_ids]
    dst_c.executemany("INSERT INTO word_definitions (id, word_id, definition_id, example) VALUES (?, ?, ?, ?);", kept_wd)
    print(f"[✔] Đã giữ lại {len(kept_wd):,} / {len(all_wd):,} liên kết từ - định nghĩa.")

    kept_def_ids = set(r[2] for r in kept_wd)

    # 7. Sao chép bảng definitions
    print("[*] Đang sao chép định nghĩa 'definitions'...")
    src_c.execute("SELECT id, definition, pos, sub_pos, definition_lang FROM definitions;")
    all_defs = src_c.fetchall()
    kept_defs = [r for r in all_defs if r[0] in kept_def_ids]
    dst_c.executemany("INSERT INTO definitions (id, definition, pos, sub_pos, definition_lang) VALUES (?, ?, ?, ?, ?);", kept_defs)
    print(f"[✔] Đã giữ lại {len(kept_defs):,} / {len(all_defs):,} định nghĩa tiếng Việt.")

    # 8. Tạo lại các Index
    print("[*] Đang tạo lại các chỉ mục tìm kiếm (Indexes)...")
    src_c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
    for idx_sql in src_c.fetchall():
        if idx_sql and idx_sql[0]:
            try:
                dst_c.execute(idx_sql[0])
            except Exception as e:
                logger.debug("Bỏ qua tạo index lỗi: %s", e)

    dst_conn.commit()

    # 9. Kiểm tra toàn vẹn và VACUUM
    print("[*] Đang kiểm tra tính toàn vẹn (Integrity Check) và tối ưu hóa (VACUUM)...")
    integrity = dst_c.execute("PRAGMA integrity_check;").fetchall()
    if integrity != [("ok",)]:
        print(f"[!] LỖI TOÀN VẸN CƠ SỞ DỮ LIỆU: {integrity}")
        dst_conn.close()
        temp_db_path.unlink()
        sys.exit(1)

    dst_c.execute("ANALYZE;")
    dst_c.execute("VACUUM;")
    dst_conn.close()
    src_conn.close()

    # 10. Hoán đổi file an toàn
    pruned_size = temp_db_path.stat().st_size
    temp_db_path.replace(db_path)

    elapsed = time.perf_counter() - start_time
    space_saved = original_size - pruned_size
    reduction_pct = (space_saved / original_size) * 100

    print("=" * 70)
    print("🎉 HOÀN TẤT THU GỌN CƠ SỞ DỮ LIỆU THÀNH CÔNG!")
    print(f"  • Dung lượng ban đầu: {original_size / (1024 * 1024):.2f} MB ({original_size:,} bytes)")
    print(f"  • Dung lượng mới:     {pruned_size / (1024 * 1024):.2f} MB ({pruned_size:,} bytes)")
    print(f"  • Dung lượng giảm:    {space_saved / (1024 * 1024):.2f} MB ({reduction_pct:.1f}% không gian được giải phóng)")
    print(f"  • Thời gian xử lý:    {elapsed:.2f} giây")
    print(f"  • Bản sao lưu an toàn: {backup_path.name}")
    print("=" * 70)


if __name__ == "__main__":
    prune_dictionary_database()
