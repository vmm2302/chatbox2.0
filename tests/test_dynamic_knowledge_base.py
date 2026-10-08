"""Bộ kiểm thử 10 kịch bản Acceptance Test bắt buộc cho CHATBOX 2.0 — DYNAMIC KNOWLEDGE BASE.

Kiểm thử toàn diện 10 yêu cầu cốt lõi:
Test 1: Clone project trên máy mới. Không có sample data. Chatbot phải chạy.
Test 2: Knowledge Base = 0. Không crash, không hallucinate, thông báo chưa có dữ liệu.
Test 3: Upload data A. Data A xuất hiện trong Knowledge Base.
Test 4: Upload data B với ADD. Knowledge Base chứa A + B.
Test 5: Upload record có cùng ID với A. A được UPDATE bằng dữ liệu mới, không duplicate.
Test 6: REPLACE bằng data C. Knowledge Base chỉ còn C.
Test 7: Query sau khi update. Retrieval sử dụng dữ liệu mới chính xác.
Test 8: Xóa record. Source JSONL + BM25 + ChromaDB đồng bộ tuyệt đối.
Test 9: Restart ứng dụng. Knowledge Base vẫn tồn tại nguyên vẹn.
Test 10: Không có sample data (3,725 Q&A) nhưng toàn bộ 8 định dạng tệp vẫn hoạt động hoàn hảo.
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.chat.engine import ChatEngine
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever


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
            p_xml.append(f"""<w:p><w:r><w:t>{word}: {meaning}</w:t></w:r></w:p>""")

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
    headers = ["ID", "Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
    rows = [[f"ID_{w.upper()}", w, f"{w} nghĩa là gì?", m, "B2", filepath.name] for w, m in entries]

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


class TestDynamicKnowledgeBase(unittest.TestCase):
    """Bộ kiểm thử 10 kịch bản Acceptance Test của CHATBOX 2.0 Dynamic Knowledge Base."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo môi trường kiểm thử cách ly hoàn toàn với dữ liệu thực tế."""
        cls.test_dir = PROJECT_ROOT / "temp_test_acceptance_dynamic_kb"
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        cls.test_raw_dir = cls.test_dir / "raw"
        cls.test_processed_dir = cls.test_dir / "processed"
        cls.test_chroma_dir = cls.test_dir / "chroma_db"
        cls.test_raw_dir.mkdir(parents=True, exist_ok=True)
        cls.test_processed_dir.mkdir(parents=True, exist_ok=True)
        cls.test_chroma_dir.mkdir(parents=True, exist_ok=True)

        # Lưu cấu hình gốc
        cls.orig_raw_dir = settings.RAW_DATA_DIR
        cls.orig_raw_excel = settings.RAW_EXCEL_PATH
        cls.orig_processed_dir = settings.PROCESSED_DATA_DIR
        cls.orig_processed_jsonl = settings.PROCESSED_JSONL_PATH
        cls.orig_chroma_dir = settings.CHROMA_DIR
        cls.orig_manifest_path = settings.SOURCES_MANIFEST_PATH

        # Cấu hình chuyển hướng sang môi trường test hoàn toàn rỗng
        cls.test_jsonl_path = cls.test_processed_dir / "qa_records.jsonl"
        cls.test_manifest_path = cls.test_processed_dir / "sources_manifest.json"
        cls.test_raw_excel = cls.test_raw_dir / "empty.xlsx"

        object.__setattr__(settings, "RAW_DATA_DIR", cls.test_raw_dir)
        object.__setattr__(settings, "RAW_EXCEL_PATH", cls.test_raw_excel)
        object.__setattr__(settings, "PROCESSED_DATA_DIR", cls.test_processed_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.test_jsonl_path)
        object.__setattr__(settings, "CHROMA_DIR", cls.test_chroma_dir)
        object.__setattr__(settings, "SOURCES_MANIFEST_PATH", cls.test_manifest_path)

        cls.batch_manager = BatchIngestionManager(manifest_path=cls.test_manifest_path)

    @classmethod
    def tearDownClass(cls):
        """Khôi phục môi trường và dọn dẹp tài nguyên."""
        object.__setattr__(settings, "RAW_DATA_DIR", cls.orig_raw_dir)
        object.__setattr__(settings, "RAW_EXCEL_PATH", cls.orig_raw_excel)
        object.__setattr__(settings, "PROCESSED_DATA_DIR", cls.orig_processed_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.orig_processed_jsonl)
        object.__setattr__(settings, "CHROMA_DIR", cls.orig_chroma_dir)
        object.__setattr__(settings, "SOURCES_MANIFEST_PATH", cls.orig_manifest_path)

        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_clean_start_empty_kb_no_sample_data(self):
        """Test 1: Clone project trên máy mới, không có sample data -> Chatbot phải chạy bình thường."""
        # Đảm bảo môi trường hoàn toàn rỗng (0 file dữ liệu, 0 jsonl, 0 vector)
        if self.test_jsonl_path.exists():
            self.test_jsonl_path.unlink()

        loader = QALoader()
        records = loader.load_from_jsonl()
        self.assertEqual(len(records), 0, "Môi trường test mới phải có 0 bản ghi")

        # Khởi tạo ChatEngine từ trạng thái rỗng
        engine = ChatEngine()
        self.assertIsNotNone(engine, "ChatEngine phải khởi tạo thành công không lỗi")
        self.assertEqual(len(engine.records), 0, "Knowledge Base trong ChatEngine phải rỗng = 0")
        self.assertIsNone(engine.retriever.bm25_retriever.bm25, "BM25 index phải là None khi không có dữ liệu")
        coll_count = engine.retriever.bge_retriever.collection.count() if engine.retriever.bge_retriever.collection else 0
        self.assertEqual(coll_count, 0, "ChromaDB vector count phải là 0")

    def test_02_empty_knowledge_base_query_no_crash_no_hallucination(self):
        """Test 2: Knowledge Base = 0 -> Không crash, không hallucinate, thông báo KB chưa có dữ liệu."""
        engine = ChatEngine()
        self.assertEqual(len(engine.records), 0)

        # 1. Truy vấn từ vựng khi KB rỗng
        resp = engine.ask("từ vựng resilience nghĩa là gì?")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.mode, "NO_MATCH")
        # Phải thông báo rằng Knowledge Base chưa có dữ liệu, không được tự tạo dữ liệu bịa đặt
        self.assertIn(settings.EMPTY_KB_RESPONSE, resp.answer)

        # 2. Truy vấn streaming khi KB rỗng
        stream_chunks = list(engine.ask_stream("từ vựng ephemeral nghĩa là gì?"))
        full_stream_ans = "".join(chunk for chunk, _ in stream_chunks)
        self.assertIn(settings.EMPTY_KB_RESPONSE, full_stream_ans)

        # 3. Chào hỏi thông thường (Small talk) vẫn lịch sự, mượt mà và không crash
        st_resp = engine.ask("xin chào bạn")
        self.assertIsNotNone(st_resp)
        self.assertEqual(st_resp.mode, "SMALL_TALK")
        self.assertTrue(len(st_resp.answer) > 0)

    def test_03_upload_data_a_appears_in_kb(self):
        """Test 3: Upload data A -> Data A xuất hiện trong Knowledge Base."""
        data_a_file = self.test_dir / "data_a.json"
        data_a_content = [
            {
                "id": "REC_A_001",
                "word": "serendipity",
                "question": "serendipity nghĩa là gì?",
                "answer": "sự tình cờ phát hiện ra những điều bất ngờ thú vị và may mắn",
                "difficulty": "C1",
                "source": "data_a.json"
            }
        ]
        data_a_file.write_text(json.dumps(data_a_content, ensure_ascii=False), encoding="utf-8")

        # Nạp Data A với mode="add"
        report = self.batch_manager.ingest_batch([data_a_file], mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(report.total_records_added, 1)

        # Kiểm tra tính đồng bộ
        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"], "Dữ liệu Source, BM25 và ChromaDB phải đồng bộ")
        self.assertEqual(sync_res["source_data_count"], 1)
        self.assertEqual(sync_res["chromadb_count"], 1)
        self.assertEqual(sync_res["bm25_count"], 1)

        # Cập nhật Knowledge Base vào ChatEngine
        engine = ChatEngine()
        self.assertEqual(len(engine.records), 1)
        self.assertEqual(engine.records[0].record_id, "REC_A_001")
        self.assertEqual(engine.records[0].word, "serendipity")

    def test_04_upload_data_b_with_add_mode_union(self):
        """Test 4: Upload data B với ADD -> KB chứa đồng thời A + B."""
        data_b_file = self.test_dir / "data_b.txt"
        data_b_content = (
            "[id: REC_B_001]\n"
            "ephemeral: phù du, ngắn ngủi, sớm nở tối tàn.\n"
            "Trình độ: C1\n"
        )
        data_b_file.write_text(data_b_content, encoding="utf-8")

        report = self.batch_manager.ingest_batch([data_b_file], mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(report.total_records_added, 1)

        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"])
        self.assertEqual(sync_res["source_data_count"], 2)
        self.assertEqual(sync_res["chromadb_count"], 2)
        self.assertEqual(sync_res["bm25_count"], 2)

        # Kiểm tra sự tồn tại của cả A và B
        records = self.batch_manager.loader.load_from_jsonl()
        record_ids = {r.record_id for r in records}
        self.assertIn("REC_A_001", record_ids)
        self.assertIn("REC_B_001", record_ids)

    def test_05_upload_same_id_as_a_updates_without_duplicates(self):
        """Test 5: Upload record có cùng ID với A -> A được UPDATE bằng dữ liệu mới, không tạo duplicate."""
        data_a_updated_file = self.test_dir / "data_a_update.json"
        updated_answer = "sự may mắn tình cờ (ĐÃ ĐƯỢC CẬP NHẬT PHIÊN BẢN MỚI NHẤT)"
        data_a_updated_content = [
            {
                "id": "REC_A_001",  # CÙNG ID VỚI A
                "word": "serendipity",
                "question": "serendipity nghĩa là gì?",
                "answer": updated_answer,
                "difficulty": "C2",
                "source": "data_a_update.json"
            }
        ]
        data_a_updated_file.write_text(json.dumps(data_a_updated_content, ensure_ascii=False), encoding="utf-8")

        # Nạp với mode="add" (yêu cầu update/overwrite nếu trùng ID)
        report = self.batch_manager.ingest_batch([data_a_updated_file], mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

        # Kiểm tra tổng số bản ghi vẫn là 2 (A và B), KHÔNG bị tăng lên 3
        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"])
        self.assertEqual(sync_res["source_data_count"], 2, "Tổng số bản ghi phải giữ nguyên 2 (không bị trùng lặp)")
        self.assertEqual(sync_res["chromadb_count"], 2)
        self.assertEqual(sync_res["bm25_count"], 2)

        # Kiểm tra nội dung REC_A_001 đã được cập nhật chính xác
        records = self.batch_manager.loader.load_from_jsonl()
        rec_a = next(r for r in records if r.record_id == "REC_A_001")
        self.assertEqual(rec_a.answer, updated_answer)
        self.assertEqual(rec_a.difficulty, "C2")

    def test_06_replace_with_data_c_wipes_old_and_keeps_only_c(self):
        """Test 6: REPLACE bằng data C -> Toàn bộ A và B bị xóa, chỉ còn lại C."""
        data_c_file = self.test_dir / "data_c.csv"
        data_c_content = "id,word,question,answer,difficulty,source\nREC_C_001,eloquent,eloquent nghĩa là gì?,hùng biện, có tài ăn nói lưu loát,B2,data_c.csv\n"
        data_c_file.write_text(data_c_content, encoding="utf-8")

        # Nạp với mode="replace"
        report = self.batch_manager.ingest_batch([data_c_file], mode="replace")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)

        # Xác thực Knowledge Base CHỈ CÒN C (1 bản ghi)
        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"])
        self.assertEqual(sync_res["source_data_count"], 1)
        self.assertEqual(sync_res["chromadb_count"], 1)
        self.assertEqual(sync_res["bm25_count"], 1)

        records = self.batch_manager.loader.load_from_jsonl()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].record_id, "REC_C_001")
        self.assertEqual(records[0].word, "eloquent")

    def test_07_retrieval_after_update_uses_new_data(self):
        """Test 7: Query sau khi update -> Retrieval sử dụng dữ liệu mới ngay lập tức."""
        engine = ChatEngine()
        engine.update_knowledge_base(self.batch_manager.loader.load_from_jsonl())

        # 1. Truy vấn dữ liệu mới C ("eloquent")
        mode, best_c, candidates = engine.retriever.retrieve("eloquent nghĩa là gì?", top_k=3)
        self.assertIsNotNone(best_c, "Phải tìm thấy ứng viên cho dữ liệu mới")
        self.assertEqual(best_c.record.record_id, "REC_C_001")
        self.assertEqual(best_c.record.word, "eloquent")
        self.assertIn("hùng biện", best_c.record.answer)

        # 2. Truy vấn dữ liệu cũ A ("serendipity") đã bị replace -> Không còn tìm thấy
        mode_old, best_old, _ = engine.retriever.retrieve("serendipity nghĩa là gì?", top_k=3)
        if best_old is not None:
            self.assertNotEqual(best_old.record.record_id, "REC_A_001", "Dữ liệu cũ A không được phép xuất hiện")

        # 3. Kiểm tra qua engine.ask()
        resp = engine.ask("eloquent nghĩa là gì?")
        self.assertEqual(resp.record_id, "REC_C_001")
        self.assertIn("hùng biện", resp.answer)

    def test_08_delete_record_synchronizes_source_bm25_chromadb(self):
        """Test 8: Xóa record -> Source JSONL + BM25 + ChromaDB đồng bộ tuyệt đối về 0."""
        # Hiện tại đang có REC_C_001, thực hiện xóa
        del_res = self.batch_manager.delete_record("REC_C_001")
        self.assertTrue(del_res["deleted"])
        self.assertEqual(del_res["remaining_count"], 0)

        # Kiểm tra đồng bộ tuyệt đối
        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"])
        self.assertEqual(sync_res["source_data_count"], 0)
        self.assertEqual(sync_res["chromadb_count"], 0)
        self.assertEqual(sync_res["bm25_count"], 0)

        # Cập nhật engine và kiểm tra truy vấn trở về trạng thái empty KB an toàn
        engine = ChatEngine()
        engine.update_knowledge_base([])
        self.assertEqual(len(engine.records), 0)

        resp = engine.ask("eloquent nghĩa là gì?")
        self.assertIn(settings.EMPTY_KB_RESPONSE, resp.answer)

    def test_09_restart_app_preserves_knowledge_base(self):
        """Test 9: Restart ứng dụng -> Knowledge Base vẫn tồn tại nguyên vẹn."""
        # 1. Nạp dữ liệu bền vững Data D
        data_d_file = self.test_dir / "data_d.jsonl"
        record_d = {
            "id": "REC_D_PERSIST_001",
            "word": "resilience",
            "question": "resilience nghĩa là gì?",
            "answer": "khả năng phục hồi, kiên cường vượt qua khó khăn",
            "difficulty": "B2",
            "source": "data_d.jsonl"
        }
        data_d_file.write_text(json.dumps(record_d, ensure_ascii=False) + "\n", encoding="utf-8")
        self.batch_manager.ingest_batch([data_d_file], mode="add")

        sync_before = self.batch_manager.verify_sync()
        self.assertTrue(sync_before["synced"])
        self.assertEqual(sync_before["source_data_count"], 1)

        # 2. Giả lập khởi động lại ứng dụng (Tạo mới hoàn toàn thể hiện ChatEngine)
        restarted_engine = ChatEngine()
        restarted_engine.warm_up()

        # 3. Kiểm tra Knowledge Base tự động được phục hồi từ ổ đĩa
        self.assertEqual(len(restarted_engine.records), 1)
        self.assertEqual(restarted_engine.records[0].record_id, "REC_D_PERSIST_001")
        self.assertEqual(restarted_engine.records[0].word, "resilience")
        self.assertEqual(restarted_engine.retriever.bge_retriever.collection.count(), 1)
        self.assertIsNotNone(restarted_engine.retriever.bm25_retriever.bm25)

        # 4. Truy vấn ngay sau khi restart
        resp = restarted_engine.ask("resilience nghĩa là gì?")
        self.assertEqual(resp.record_id, "REC_D_PERSIST_001")
        self.assertIn("khả năng phục hồi", resp.answer)

    def test_10_full_system_operates_without_sample_data(self):
        """Test 10: Không có sample data (3,725 Q&A) nhưng toàn bộ 8 định dạng tệp vẫn nạp và hoạt động bình thường."""
        # Xóa sạch KB để bắt đầu từ con số 0 hoàn toàn
        self.batch_manager.delete_record("REC_D_PERSIST_001")
        self.assertEqual(self.batch_manager.verify_sync()["source_data_count"], 0)

        # Tạo mẫu 8 định dạng tài liệu độc lập
        batch_files = []

        # 1. TXT
        f_txt = self.test_dir / "t10_vocab.txt"
        f_txt.write_text("[id: REC_FMT_TXT]\nlucid: rõ ràng, minh bạch, dễ hiểu.\n", encoding="utf-8")
        batch_files.append(f_txt)

        # 2. JSON
        f_json = self.test_dir / "t10_vocab.json"
        f_json.write_text(json.dumps([{
            "id": "REC_FMT_JSON",
            "word": "candid",
            "question": "candid nghĩa là gì?",
            "answer": "thật thà, thẳng thắn, bộc trực"
        }], ensure_ascii=False), encoding="utf-8")
        batch_files.append(f_json)

        # 3. JSONL
        f_jsonl = self.test_dir / "t10_vocab.jsonl"
        f_jsonl.write_text(json.dumps({
            "id": "REC_FMT_JSONL",
            "word": "pragmatic",
            "question": "pragmatic nghĩa là gì?",
            "answer": "thực dụng, thực tế"
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        batch_files.append(f_jsonl)

        # 4. CSV
        f_csv = self.test_dir / "t10_vocab.csv"
        f_csv.write_text("id,word,question,answer\nREC_FMT_CSV,diligent,diligent nghĩa là gì?,siêng năng, cần cù\n", encoding="utf-8")
        batch_files.append(f_csv)

        # 5. MD
        f_md = self.test_dir / "t10_vocab.md"
        f_md.write_text("# Vocabulary\n[id: REC_FMT_MD]\nmeticulous: tỉ mỉ, kỹ lưỡng, cẩn thận từng chi tiết.\n", encoding="utf-8")
        batch_files.append(f_md)

        # 6. DOCX
        f_docx = self.test_dir / "t10_vocab.docx"
        create_test_docx(f_docx, [("tenacious", "kiên trì, bền bỉ, không bỏ cuộc")])
        batch_files.append(f_docx)

        # 7. XLSX
        f_xlsx = self.test_dir / "t10_vocab.xlsx"
        create_test_xlsx(f_xlsx, [("ubiquitous", "phổ biến, có mặt ở khắp mọi nơi")])
        batch_files.append(f_xlsx)

        # 8. PDF
        f_pdf = self.test_dir / "t10_vocab.pdf"
        create_test_pdf(f_pdf, [("resilient", "kiên cường, nhanh chóng hồi phục")])
        batch_files.append(f_pdf)

        # Nạp đồng thời cả 8 định dạng vào hệ thống đang rỗng
        report = self.batch_manager.ingest_batch(batch_files, mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS, "Nạp 8 định dạng phải SUCCESS toàn bộ")
        self.assertEqual(report.success_count, 8)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.total_records_added, 8)

        # Kiểm tra tính toàn vẹn và đồng bộ
        sync_res = self.batch_manager.verify_sync()
        self.assertTrue(sync_res["synced"])
        self.assertEqual(sync_res["source_data_count"], 8)
        self.assertEqual(sync_res["chromadb_count"], 8)
        self.assertEqual(sync_res["bm25_count"], 8)

        # Khởi tạo engine và thực hiện truy vấn
        engine = ChatEngine()
        self.assertEqual(len(engine.records), 8)

        # Thử nghiệm truy vấn từ vựng đại diện từ các định dạng khác nhau:
        # Từ DOCX: "tenacious"
        resp_docx = engine.ask("tenacious nghĩa là gì?")
        self.assertIn("kiên trì", resp_docx.answer)

        # Từ MD: "meticulous"
        resp_md = engine.ask("meticulous nghĩa là gì?")
        self.assertIn("tỉ mỉ", resp_md.answer)

        # Từ CSV: "diligent"
        resp_csv = engine.ask("diligent nghĩa là gì?")
        self.assertIn("siêng năng", resp_csv.answer)


if __name__ == "__main__":
    unittest.main()
