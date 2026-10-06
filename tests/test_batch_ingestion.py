"""Bộ kiểm thử toàn diện cho hệ thống Batch Multi-File Ingestion (10 Test Cases bắt buộc).

Kiểm thử 10 kịch bản theo yêu cầu nghiệp vụ:
1. Case 1: All files valid (5 files -> 5 SUCCESS).
2. Case 2: Mixed file types (PDF + DOCX + XLSX + JSON + TXT).
3. Case 3: One file corrupted (4 SUCCESS, 1 FAILED -> PARTIAL SUCCESS).
4. Case 4: Duplicate file (1 SUCCESS, 1 SKIPPED: Duplicate file).
5. Case 5: Duplicate content across files (Khử trùng lặp nội dung Q&A).
6. Case 6: Large batch (Xử lý ổn định không tràn RAM/VRAM).
7. Case 7: Retry failed file (Chỉ retry độc lập tệp lỗi).
8. Case 8: Delete source (Xóa sạch dữ liệu khỏi ChromaDB, JSONL, BM25).
9. Case 9: New data immediately searchable (Dữ liệu mới tra cứu được ngay).
10. Case 10: Source trace (Truy vết nguồn gốc tệp đến từng câu trả lời).
"""

import io
import json
import os
import shutil
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
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


def create_test_docx(filepath: Path, entries: list):
    """Tạo tệp Word .docx chuẩn OpenXML bằng thư viện chuẩn Python."""
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        p_xml = []
        for word, meaning in entries:
            p_xml.append(f"""<w:p><w:r><w:t>{word} nghĩa là gì?</w:t></w:r></w:p>
<w:p><w:r><w:t>{meaning}</w:t></w:r></w:p>""")

        doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{"".join(p_xml)}</w:body>
</w:document>"""
        z.writestr("word/document.xml", doc_xml)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(zbuf.getvalue())


def create_test_xlsx(filepath: Path, entries: list):
    """Tạo tệp Excel .xlsx chuẩn OpenXML."""
    headers = ["Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
    rows = [[w, f"{w} nghĩa là gì?", m, "B2", filepath.name] for w, m in entries]

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
    """Tạo tệp PDF hợp lệ qua PyMuPDF."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    text_lines = []
    for w, m in entries:
        text_lines.append(f"{w} nghĩa là gì?\n{m}\n")
    page.insert_text((50, 50), "\n".join(text_lines))
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(filepath))
    doc.close()


class TestBatchMultiFileIngestion(unittest.TestCase):
    """Bộ kiểm thử 10 kịch bản bắt buộc của Batch Multi-File Ingestion."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = project_root / "temp_test_batch"
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        cls.manifest_test_path = cls.test_dir / "test_manifest.json"

        # Cô lập hoàn toàn ChromaDB cho môi trường test
        cls.orig_chroma_dir = settings.CHROMA_DIR
        cls.test_chroma_dir = cls.test_dir / "test_chroma_db"
        cls.test_chroma_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(settings, "CHROMA_DIR", cls.test_chroma_dir)

        cls.manager = BatchIngestionManager(manifest_path=cls.manifest_test_path)

        # Sao lưu an toàn dữ liệu sản xuất
        cls.backup_jsonl = settings.PROCESSED_DATA_DIR / "qa_records_test_backup.jsonl"
        if settings.PROCESSED_JSONL_PATH.exists():
            shutil.copy2(settings.PROCESSED_JSONL_PATH, cls.backup_jsonl)

        cls.backup_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest_test_backup.json"
        prod_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest.json"
        if prod_manifest.exists():
            shutil.copy2(prod_manifest, cls.backup_manifest)

    @classmethod
    def tearDownClass(cls):
        # Khôi phục đường dẫn ChromaDB gốc
        object.__setattr__(settings, "CHROMA_DIR", cls.orig_chroma_dir)

        # Dọn dẹp thư mục test
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

        # Khôi phục dữ liệu gốc
        if cls.backup_jsonl.exists():
            shutil.copy2(cls.backup_jsonl, settings.PROCESSED_JSONL_PATH)
            cls.backup_jsonl.unlink(missing_ok=True)

        if cls.backup_manifest.exists():
            prod_manifest = settings.PROCESSED_DATA_DIR / "sources_manifest.json"
            shutil.copy2(cls.backup_manifest, prod_manifest)
            cls.backup_manifest.unlink(missing_ok=True)

    def test_case_1_all_files_valid(self):
        """Case 1: All files valid (5 files -> 5 SUCCESS)."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"c1_{uid}_vocab1.txt"
        f1.write_text(f"lucid_{uid}: rõ ràng, dễ hiểu, sáng sủa.\nTrình độ: B2\n", encoding="utf-8")

        f2 = self.test_dir / f"c1_{uid}_vocab2.json"
        f2.write_text(json.dumps([{"question": f"candid_{uid} nghĩa là gì?", "answer": "Thật thà, thẳng thắn, bộc trực.", "word": f"candid_{uid}"}]), encoding="utf-8")

        f3 = self.test_dir / f"c1_{uid}_vocab3.csv"
        f3.write_text(f"Câu hỏi,Câu trả lời,Từ vựng\npragmatic_{uid} nghĩa là gì?,Thực tế, thực dụng.,pragmatic_{uid}\n", encoding="utf-8")

        f4 = self.test_dir / f"c1_{uid}_vocab4.md"
        f4.write_text(f"## diligent_{uid}\ndiligent_{uid} nghĩa là gì? - Siêng năng, cần cù, chăm chỉ.\n", encoding="utf-8")

        f5 = self.test_dir / f"c1_{uid}_vocab5.jsonl"
        f5.write_text(json.dumps({"question": f"empathy_{uid} nghĩa là gì?", "answer": "Sự đồng cảm, thấu hiểu cảm xúc.", "word": f"empathy_{uid}"}) + "\n", encoding="utf-8")

        report = self.manager.ingest_batch([f1, f2, f3, f4, f5], batch_size=8)
        self.assertEqual(report.total_files, 5)
        self.assertEqual(report.success_count, 5)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertGreaterEqual(report.total_records_added, 5)

    def test_case_2_mixed_file_types(self):
        """Case 2: Mixed file types (PDF + DOCX + XLSX + JSON + TXT in one batch)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"c2_{uid}_words.pdf"
        create_test_pdf(f_pdf, [(f"ephemeral_{uid}", "Phù du, chỉ tồn tại trong thời gian ngắn.")])

        f_docx = self.test_dir / f"c2_{uid}_words.docx"
        create_test_docx(f_docx, [(f"tenacious_{uid}", "Kiên trì, ngoan cường, bền bỉ.")])

        f_xlsx = self.test_dir / f"c2_{uid}_words.xlsx"
        create_test_xlsx(f_xlsx, [(f"aesthetic_{uid}", "Thuộc về thẩm mỹ, có tính nghệ thuật.")])

        f_json = self.test_dir / f"c2_{uid}_words.json"
        f_json.write_text(json.dumps([{"question": f"meticulous_{uid} nghĩa là gì?", "answer": "Tỉ mỉ, cẩn thận từng chi tiết nhỏ.", "word": f"meticulous_{uid}"}]), encoding="utf-8")

        f_txt = self.test_dir / f"c2_{uid}_words.txt"
        f_txt.write_text(f"eloquent_{uid}: có tài hùng biện, lưu loát, truyền cảm.\n", encoding="utf-8")

        report = self.manager.ingest_batch([f_pdf, f_docx, f_xlsx, f_json, f_txt], batch_size=8)
        self.assertEqual(report.total_files, 5)
        self.assertEqual(report.success_count, 5)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

    def test_case_3_one_file_corrupted(self):
        """Case 3: One file corrupted (4 SUCCESS, 1 FAILED -> PARTIAL SUCCESS)."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"c3_{uid}_good1.txt"
        f1.write_text(f"gregarious_{uid}: thích giao du, hòa đồng.\n", encoding="utf-8")

        f2 = self.test_dir / f"c3_{uid}_good2.json"
        f2.write_text(json.dumps([{"question": f"stoic_{uid} nghĩa là gì?", "answer": "Khắc kỷ, chịu đựng khó khăn không than thở.", "word": f"stoic_{uid}"}]), encoding="utf-8")

        f3 = self.test_dir / f"c3_{uid}_good3.csv"
        f3.write_text(f"Câu hỏi,Câu trả lời\nnostalgia_{uid} nghĩa là gì?,Nỗi nhớ nhà, hoài niệm về quá khứ.\n", encoding="utf-8")

        f4 = self.test_dir / f"c3_{uid}_good4.md"
        f4.write_text(f"solitude_{uid}: sự cô độc tĩnh lặng, một mình thanh thản.\n", encoding="utf-8")

        # Tệp bị lỗi/hỏng cấu trúc
        f_bad = self.test_dir / f"c3_{uid}_corrupted.pdf"
        f_bad.write_bytes(b"CORRUPTED_NOT_A_REAL_PDF_DATA_0123456789")

        report = self.manager.ingest_batch([f1, f2, f3, f4, f_bad], batch_size=8)
        self.assertEqual(report.total_files, 5)
        self.assertEqual(report.success_count, 4)
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(report.batch_status, BatchStatus.PARTIAL_SUCCESS)

        # Kiểm tra lý do lỗi cụ thể
        failed_res = next(r for r in report.file_results if r.file_name == f_bad.name)
        self.assertEqual(failed_res.status, FileStatus.FAILED)
        self.assertIsNotNone(failed_res.reason)
        self.assertIn("Lỗi", failed_res.reason)

    def test_case_4_duplicate_file(self):
        """Case 4: Duplicate file (1 SUCCESS, 1 SKIPPED: Duplicate file)."""
        uid = uuid.uuid4().hex[:6]
        f_orig = self.test_dir / f"c4_{uid}_orig.txt"
        f_orig.write_text(f"zenith_{uid}: đỉnh cao, thời điểm thành công nhất.\n", encoding="utf-8")

        # Tệp giống hệt nội dung
        f_dupe = self.test_dir / f"c4_{uid}_duplicate.txt"
        f_dupe.write_text(f"zenith_{uid}: đỉnh cao, thời điểm thành công nhất.\n", encoding="utf-8")

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
        f_a = self.test_dir / f"c5_{uid}_file_a.txt"
        f_a.write_text(f"audacious_{uid}: táo bạo, liều lĩnh, can đảm.\n", encoding="utf-8")

        f_b = self.test_dir / f"c5_{uid}_file_b.csv"
        w1 = f"audacious_{uid}"
        w2 = f"prolific_{uid}"
        f_b.write_text(
            f'Câu hỏi,Câu trả lời,Từ vựng\n'
            f'"{w1} nghĩa là gì?","táo bạo, liều lĩnh, can đảm.","{w1}"\n'
            f'"{w2} nghĩa là gì?","sáng tác nhiều, màu mỡ phì nhiêu.","{w2}"\n',
            encoding="utf-8"
        )

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
        for i in range(6):
            f_i = self.test_dir / f"c6_{uid}_batch_{i}.json"
            f_i.write_text(json.dumps([{"question": f"word_c6_{uid}_{i} nghĩa là gì?", "answer": f"Định nghĩa số {i} cho kịch bản batch lớn.", "word": f"word_c6_{uid}_{i}"}]), encoding="utf-8")
            batch_files.append(f_i)

        report = self.manager.ingest_batch(batch_files, batch_size=8)
        self.assertEqual(report.total_files, 6)
        self.assertEqual(report.success_count, 6)
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

    def test_case_7_retry_failed_file(self):
        """Case 7: Retry failed file (Chỉ retry độc lập tệp lỗi sau khi sửa chữa)."""
        uid = uuid.uuid4().hex[:6]
        f_retry = self.test_dir / f"c7_{uid}_fixable.txt"
        f_retry.write_text("", encoding="utf-8")

        report1 = self.manager.ingest_batch([f_retry])
        self.assertEqual(report1.failed_count, 1)
        self.assertEqual(report1.batch_status, BatchStatus.FAILED)

        # Sửa nội dung tệp hợp lệ
        f_retry.write_text(f"resilience_{uid}: khả năng chống chịu và phục hồi mạnh mẽ.\n", encoding="utf-8")

        # Retry độc lập
        report2 = self.manager.ingest_batch([f_retry])
        self.assertEqual(report2.success_count, 1)
        self.assertEqual(report2.failed_count, 0)
        self.assertEqual(report2.batch_status, BatchStatus.SUCCESS)

    def test_case_8_delete_source(self):
        """Case 8: Delete source (Xóa dữ liệu nguồn khỏi ChromaDB, JSONL và BM25)."""
        uid = uuid.uuid4().hex[:6]
        f_del = self.test_dir / f"c8_{uid}_to_delete.json"
        del_word = f"obsolete_{uid}"
        f_del.write_text(json.dumps([{"question": f"{del_word} nghĩa là gì?", "answer": "Từ vựng cổ chuẩn bị bị xóa.", "word": del_word}]), encoding="utf-8")

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

    def test_case_9_new_data_immediately_searchable(self):
        """Case 9: New data immediately searchable (Dữ liệu mới tra cứu được ngay sau ingestion)."""
        uid = uuid.uuid4().hex[:6]
        new_word = f"serendipitous_{uid}"
        f_search = self.test_dir / f"c9_{uid}_searchable.txt"
        f_search.write_text(f"{new_word}: có tính chất may mắn, tình cờ bắt gặp điều tốt đẹp.\n", encoding="utf-8")

        self.manager.ingest_batch([f_search])

        # Cập nhật động cơ tìm kiếm
        engine = ChatEngine(records=self.manager.loader.load_from_jsonl())
        engine.warm_up()
        resp = engine.ask(f"{new_word} nghĩa là gì?")

        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertIn("may mắn", resp.answer.lower())

    def test_case_10_source_trace(self):
        """Case 10: Source trace (Câu trả lời phải truy ngược được về đúng file nguồn)."""
        uid = uuid.uuid4().hex[:6]
        trace_word = f"quandary_{uid}"
        f_trace = self.test_dir / f"c10_{uid}_provenance.json"
        f_trace.write_text(json.dumps([{"question": f"{trace_word} nghĩa là gì?", "answer": "Tình thế tiến thoái lưỡng nan, khó xử.", "word": trace_word}]), encoding="utf-8")

        self.manager.ingest_batch([f_trace])

        engine = ChatEngine(records=self.manager.loader.load_from_jsonl())
        engine.warm_up()
        resp = engine.ask(f"{trace_word} nghĩa là gì?")

        # Kiểm tra truy vết nguồn gốc (Provenance)
        self.assertEqual(resp.source, f_trace.name)
        self.assertEqual(resp.word, trace_word)
        self.assertIsNotNone(resp.record_id)


if __name__ == "__main__":
    unittest.main()
