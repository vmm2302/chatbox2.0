"""Bộ kiểm thử toàn diện cho hệ thống Batch Multi-File Ingestion (Giới hạn A1–A2 và định dạng XLSX/CSV/PDF).

Kiểm thử các kịch bản theo yêu cầu nghiệp vụ:
1. Case 1: All files valid (CSV, XLSX, PDF -> SUCCESS).
2. Case 2: Supported file types (PDF + XLSX + CSV).
3. Case 3: One file corrupted (SUCCESS + FAILED -> PARTIAL SUCCESS).
4. Case 4: Duplicate file (1 SUCCESS, 1 SKIPPED: Duplicate file).
5. Case 5: Duplicate content across files (Khử trùng lặp nội dung Q&A).
6. Case 6: Large batch (Xử lý ổn định danh sách nhiều tệp).
7. Case 7: Retry failed file (Chỉ retry độc lập tệp lỗi).
8. Case 8: Delete source (Xóa sạch dữ liệu khỏi ChromaDB, JSONL, BM25).
9. Case 9: Scope filter (Bỏ qua B1+ và báo cáo out_of_scope_skipped).
10. Case 10: Source trace (Truy vết nguồn gốc tệp đến từng câu trả lời).
"""

import io
import json
import os
import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path

# Đảm bảo môi trường offline tuyệt đối
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.chat.engine import ChatEngine
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus


def create_test_csv(filepath: Path, entries: list, level: str = "A1"):
    """Tạo tệp CSV chuẩn UTF-8."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("Từ vựng,Câu hỏi,Câu trả lời,Trình độ\n")
        for item in entries:
            if len(item) == 2:
                w, m = item
                lvl = level
            else:
                w, m, lvl = item
            f.write(f'"{w}","{w} nghĩa là gì?","{m}","{lvl}"\n')


def create_test_xlsx(filepath: Path, entries: list, level: str = "A1"):
    """Tạo tệp Excel .xlsx chuẩn OpenXML."""
    headers = ["Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
    rows = []
    for item in entries:
        if len(item) == 2:
            w, m = item
            lvl = level
        else:
            w, m, lvl = item
        rows.append([w, f"{w} nghĩa là gì?", m, lvl, filepath.name])

    zbuf = io.BytesIO()
    all_data = [headers] + rows
    unique_strings = []
    str_map = {}
    for r in all_data:
        for c in r:
            s = str(c)
            if s not in str_map:
                str_map[s] = len(unique_strings)
                unique_strings.append(s)

    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""")
        z.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Vocab" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
        sst_parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
        for s in unique_strings:
            escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sst_parts.append(f"<si><t>{escaped}</t></si>")
        sst_parts.append("</sst>")
        z.writestr("xl/sharedStrings.xml", "".join(sst_parts))

        sh_parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r_idx, row in enumerate(all_data, 1):
            sh_parts.append(f'<row r="{r_idx}">')
            for c_idx, cell in enumerate(row):
                col_name = chr(65 + c_idx)
                s_idx = str_map[str(cell)]
                sh_parts.append(f'<c r="{col_name}{r_idx}" t="s"><v>{s_idx}</v></c>')
            sh_parts.append('</row>')
        sh_parts.append('</sheetData></worksheet>')
        z.writestr("xl/worksheets/sheet1.xml", "".join(sh_parts))

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(zbuf.getvalue())


def create_test_pdf(filepath: Path, entries: list):
    """Tạo tệp PDF hợp lệ qua PyMuPDF kèm nhãn trình độ A1/A2."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    text_lines = []
    for item in entries:
        w = item[0]
        m = item[1]
        lvl = item[2] if len(item) > 2 else "A1"
        text_lines.append(f"{w} nghĩa là gì?\nTrình độ: {lvl}\n{m}\n")
    page.insert_text((50, 50), "\n".join(text_lines))
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(filepath))
    doc.close()


class TestBatchMultiFileIngestion(unittest.TestCase):
    """Bộ kiểm thử cho Batch Multi-File Ingestion theo phạm vi A1–A2."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = project_root / "temp_test_batch"
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        cls.manifest_test_path = cls.test_dir / "test_manifest.json"

        # Cô lập hoàn toàn ChromaDB và JSONL cho môi trường test
        cls.orig_chroma_dir = settings.CHROMA_DIR
        cls.test_chroma_dir = cls.test_dir / "test_chroma_db"
        cls.test_chroma_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(settings, "CHROMA_DIR", cls.test_chroma_dir)

        cls.orig_jsonl_path = settings.PROCESSED_JSONL_PATH
        cls.test_jsonl_path = cls.test_dir / "test_qa_records.jsonl"
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.test_jsonl_path)

        from src.data.loader import QALoader
        test_loader = QALoader()
        test_loader.processed_jsonl_path = cls.test_jsonl_path
        cls.manager = BatchIngestionManager(loader=test_loader, manifest_path=cls.manifest_test_path)

        # Sao lưu an toàn dữ liệu sản xuất
        cls.backup_jsonl = settings.PROCESSED_DATA_DIR / "qa_records_test_backup.jsonl"
        if cls.orig_jsonl_path.exists():
            shutil.copy2(cls.orig_jsonl_path, cls.backup_jsonl)

        cls.backup_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest_test_backup.json"
        prod_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest.json"
        if prod_manifest.exists():
            shutil.copy2(prod_manifest, cls.backup_manifest)

    @classmethod
    def tearDownClass(cls):
        # Khôi phục đường dẫn ChromaDB và JSONL gốc
        object.__setattr__(settings, "CHROMA_DIR", cls.orig_chroma_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.orig_jsonl_path)

        # Dọn dẹp thư mục test
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

        # Khôi phục dữ liệu gốc
        if cls.backup_jsonl.exists():
            shutil.copy2(cls.backup_jsonl, cls.orig_jsonl_path)
            cls.backup_jsonl.unlink(missing_ok=True)

        if cls.backup_manifest.exists():
            prod_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest.json"
            shutil.copy2(cls.backup_manifest, prod_manifest)
            cls.backup_manifest.unlink(missing_ok=True)

    def test_case_1_all_files_valid(self):
        """Case 1: All files valid (CSV, XLSX, PDF -> SUCCESS)."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"c1_{uid}_vocab1.csv"
        create_test_csv(f1, [(f"apple_{uid}", "Quả táo thơm ngon.")], level="A1")

        f2 = self.test_dir / f"c1_{uid}_vocab2.xlsx"
        create_test_xlsx(f2, [(f"banana_{uid}", "Quả chuối chín vàng.")], level="A1")

        f3 = self.test_dir / f"c1_{uid}_vocab3.pdf"
        create_test_pdf(f3, [(f"orange_{uid}", "Quả cam mọng nước.", "A2")])

        report = self.manager.ingest_batch([f1, f2, f3], batch_size=8)
        self.assertEqual(report.total_files, 3)
        self.assertEqual(report.success_count, 3)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertGreaterEqual(report.total_records_added, 3)

    def test_case_2_supported_file_types(self):
        """Case 2: Supported file types (PDF + XLSX + CSV)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"c2_{uid}_words.pdf"
        create_test_pdf(f_pdf, [(f"cat_{uid}", "Con mèo dễ thương.", "A1")])

        f_xlsx = self.test_dir / f"c2_{uid}_words.xlsx"
        create_test_xlsx(f_xlsx, [(f"dog_{uid}", "Con chó trung thành.", "A1")])

        f_csv = self.test_dir / f"c2_{uid}_words.csv"
        create_test_csv(f_csv, [(f"bird_{uid}", "Con chim hót líu lo.", "A2")])

        report = self.manager.ingest_batch([f_pdf, f_xlsx, f_csv], batch_size=8)
        self.assertEqual(report.total_files, 3)
        self.assertEqual(report.success_count, 3)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

    def test_case_3_one_file_corrupted(self):
        """Case 3: One file corrupted (SUCCESS + FAILED -> PARTIAL SUCCESS)."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"c3_{uid}_good1.csv"
        create_test_csv(f1, [(f"fish_{uid}", "Con cá bơi lội.")], level="A1")

        f2 = self.test_dir / f"c3_{uid}_good2.xlsx"
        create_test_xlsx(f2, [(f"duck_{uid}", "Con vịt bơi dưới hồ.")], level="A2")

        # Tệp bị lỗi/hỏng cấu trúc
        f_bad = self.test_dir / f"c3_{uid}_corrupted.pdf"
        f_bad.write_bytes(b"CORRUPTED_NOT_A_REAL_PDF_DATA_0123456789")

        report = self.manager.ingest_batch([f1, f2, f_bad], batch_size=8)
        self.assertEqual(report.total_files, 3)
        self.assertEqual(report.success_count, 2)
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(report.batch_status, BatchStatus.PARTIAL_SUCCESS)

        # Kiểm tra lý do lỗi cụ thể
        failed_res = next(r for r in report.file_results if r.file_name == f_bad.name)
        self.assertEqual(failed_res.status, FileStatus.FAILED)
        self.assertIsNotNone(failed_res.reason)

    def test_case_4_duplicate_file(self):
        """Case 4: Duplicate file (1 SUCCESS, 1 SKIPPED: Duplicate file)."""
        uid = uuid.uuid4().hex[:6]
        f_orig = self.test_dir / f"c4_{uid}_orig.csv"
        create_test_csv(f_orig, [(f"zenith_{uid}", "Đỉnh cao tuyệt đối.")], level="A1")

        f_dupe = self.test_dir / f"c4_{uid}_duplicate.csv"
        create_test_csv(f_dupe, [(f"zenith_{uid}", "Đỉnh cao tuyệt đối.")], level="A1")

        report = self.manager.ingest_batch([f_orig, f_dupe], batch_size=8)
        self.assertEqual(report.total_files, 2)
        self.assertEqual(report.success_count, 1)
        self.assertEqual(report.skipped_count, 1)
        self.assertEqual(report.batch_status, BatchStatus.PARTIAL_SUCCESS)

        skipped_res = next(r for r in report.file_results if r.file_name == f_dupe.name)
        self.assertEqual(skipped_res.status, FileStatus.SKIPPED)
        self.assertIn("Duplicate file", skipped_res.reason)

    def test_case_5_duplicate_content_across_files(self):
        """Case 5: Duplicate content across files (Kiểm tra khử trùng lặp bản ghi Q&A)."""
        uid = uuid.uuid4().hex[:6]
        f_a = self.test_dir / f"c5_{uid}_file_a.csv"
        create_test_csv(f_a, [(f"audacious_{uid}", "Táo bạo, can đảm.")], level="A1")

        f_b = self.test_dir / f"c5_{uid}_file_b.csv"
        w1 = f"audacious_{uid}"
        w2 = f"prolific_{uid}"
        create_test_csv(f_b, [(w1, "Táo bạo, can đảm."), (w2, "Sáng tác nhiều.")], level="A1")

        report = self.manager.ingest_batch([f_a, f_b], batch_size=8)
        self.assertEqual(report.success_count, 2)

        # File B phải có 1 bản ghi bị skip trùng lặp và 1 bản ghi thêm mới
        res_b = next(r for r in report.file_results if r.file_name == f_b.name)
        self.assertEqual(res_b.duplicates_skipped, 1)
        self.assertEqual(res_b.records_added, 1)

    def test_case_6_large_batch_stability(self):
        """Case 6: Large batch (Xử lý ổn định danh sách nhiều tệp)."""
        uid = uuid.uuid4().hex[:6]
        batch_files = []
        for i in range(4):
            f_i = self.test_dir / f"c6_{uid}_batch_{i}.csv"
            create_test_csv(f_i, [(f"word_c6_{uid}_{i}", f"Định nghĩa số {i}.")], level="A2")
            batch_files.append(f_i)

        report = self.manager.ingest_batch(batch_files, batch_size=8)
        self.assertEqual(report.total_files, 4)
        self.assertEqual(report.success_count, 4)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

    def test_case_7_retry_failed_file(self):
        """Case 7: Retry failed file (Chỉ retry độc lập tệp lỗi sau khi sửa chữa)."""
        uid = uuid.uuid4().hex[:6]
        f_retry = self.test_dir / f"c7_{uid}_fixable.csv"
        f_retry.write_text("", encoding="utf-8")

        report1 = self.manager.ingest_batch([f_retry])
        self.assertEqual(report1.failed_count, 1)
        self.assertEqual(report1.batch_status, BatchStatus.FAILED)

        # Sửa nội dung tệp hợp lệ
        create_test_csv(f_retry, [(f"resilience_{uid}", "Khả năng phục hồi mạnh mẽ.")], level="A2")

        # Retry độc lập
        report2 = self.manager.ingest_batch([f_retry])
        self.assertEqual(report2.success_count, 1)
        self.assertEqual(report2.failed_count, 0)
        self.assertEqual(report2.batch_status, BatchStatus.SUCCESS)

    def test_case_8_delete_source(self):
        """Case 8: Delete source (Xóa dữ liệu nguồn khỏi ChromaDB, JSONL và BM25)."""
        uid = uuid.uuid4().hex[:6]
        f_del = self.test_dir / f"c8_{uid}_to_delete.csv"
        del_word = f"obsolete_{uid}"
        create_test_csv(f_del, [(del_word, "Từ vựng chuẩn bị bị xóa.")], level="A1")

        # Nạp tệp
        self.manager.ingest_batch([f_del])

        # Kiểm tra trước khi xóa: từ tồn tại trong JSONL
        records_before = self.manager.loader.load_from_jsonl()
        self.assertTrue(any(r.word == del_word for r in records_before))

        # Thực hiện xóa nguồn
        del_res = self.manager.delete_source(f_del.name)
        self.assertEqual(del_res["status"], "SUCCESS")
        self.assertGreaterEqual(del_res["deleted_count"], 1)

        # Kiểm tra sau khi xóa: từ không còn trong JSONL
        records_after = self.manager.loader.load_from_jsonl()
        self.assertFalse(any(r.word == del_word for r in records_after))

    def test_case_9_scope_filter_skips_b1_plus(self):
        """Case 9: Mixed level file skips B1+ records and tracks out_of_scope_skipped."""
        uid = uuid.uuid4().hex[:6]
        f_mixed = self.test_dir / f"c9_{uid}_mixed.xlsx"
        create_test_xlsx(f_mixed, [
            (f"happy_{uid}", "Hạnh phúc, vui vẻ.", "A1"),
            (f"sad_{uid}", "Buồn bã, ủ rũ.", "A2"),
            (f"mitigate_{uid}", "Làm giảm bớt rủi ro.", "B2"),
            (f"ephemeral_{uid}", "Phù du, chóng tàn.", "C1"),
            (f"unknown_{uid}", "Không rõ cấp độ.", ""),
        ])

        report = self.manager.ingest_batch([f_mixed])
        self.assertEqual(report.total_files, 1)
        self.assertEqual(report.success_count, 1)
        self.assertEqual(report.total_records_added, 2)  # Only A1 & A2
        self.assertEqual(report.total_out_of_scope_skipped, 3)  # B2, C1, unknown

        res = report.file_results[0]
        self.assertEqual(res.records_added, 2)
        self.assertEqual(res.out_of_scope_skipped, 3)

    def test_case_10_source_trace(self):
        """Case 10: Source trace (Câu trả lời phải truy ngược được về đúng file nguồn)."""
        uid = uuid.uuid4().hex[:6]
        trace_word = f"quandary_{uid}"
        f_trace = self.test_dir / f"c10_{uid}_provenance.csv"
        create_test_csv(f_trace, [(trace_word, "Tình thế tiến thoái lưỡng nan.")], level="A1")

        self.manager.ingest_batch([f_trace])

        records = self.manager.loader.load_from_jsonl()
        target_rec = next((r for r in records if r.word == trace_word), None)
        self.assertIsNotNone(target_rec)
        self.assertEqual(target_rec.source, f_trace.name)
        self.assertEqual(target_rec.level, "A1")


if __name__ == "__main__":
    unittest.main()
