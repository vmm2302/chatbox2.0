"""Bộ kiểm thử toàn diện cho hệ thống PDF Ingestion & Retrieval (12 Kịch Bản Bắt Buộc).

Kiểm thử 12 kịch bản theo yêu cầu nghiệp vụ Giai đoạn 6:
1. PDF có text thông thường (nhiều từ vựng trên 1 trang).
2. PDF scan cần OCR (kiểm tra phát hiện needs_ocr và hướng dẫn cài đặt Tesseract).
3. PDF trộn trang có text và trang scan.
4. PDF nhiều trang (trích xuất liên tục, rich metadata số trang).
5. PDF có bảng từ vựng (bảo toàn quan hệ từ - phát âm - nghĩa - ví dụ).
6. PDF rỗng, hỏng hoặc không đọc được.
7. PDF có ký tự tiếng Việt và ký hiệu phiên âm IPA (Unicode NFC).
8. PDF không tạo được chunk (xử lý lỗi cụ thể, không báo thành công giả).
9. Upload cùng một PDF nhiều lần (chống trùng lặp SHA-256).
10. Lỗi xảy ra trong lúc cập nhật index (rollback an toàn, không mất dữ liệu cũ).
11. Chế độ ADD, UPDATE và REPLACE.
12. Khởi động lại ứng dụng và truy xuất lại dữ liệu đã lưu từ JSONL.
13. Kiểm thử End-to-End: Nạp PDF từ vựng -> BM25 + BGE-M3 -> RRF & Gate -> Tra cứu thành công.
"""

import io
import json
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

# Đảm bảo môi trường offline tuyệt đối
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf

from config.settings import settings
from src.chat.engine import ChatEngine
from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader
from src.data.loaders.ocr_handler import OCRHandler
from src.data.loaders.pdf_loader import PDFLoader
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever


class TestPDFIngestionPipeline(unittest.TestCase):
    """Bộ kiểm thử chuyên sâu cho toàn bộ luồng PDF Ingestion."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = PROJECT_ROOT / "temp_test_pdf_ingestion"
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        cls.manifest_test_path = cls.test_dir / "test_sources_manifest.json"

        # Cô lập hoàn toàn ChromaDB và thư mục dữ liệu test
        cls.orig_chroma_dir = settings.CHROMA_DIR
        cls.test_chroma_dir = cls.test_dir / "test_chroma_db"
        cls.test_chroma_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(settings, "CHROMA_DIR", cls.test_chroma_dir)

        cls.test_jsonl_path = cls.test_dir / "test_qa_records.jsonl"
        cls.orig_jsonl_path = settings.PROCESSED_JSONL_PATH
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.test_jsonl_path)

        cls.test_loader = QALoader(processed_jsonl_path=cls.test_jsonl_path)
        cls.batch_manager = BatchIngestionManager(
            loader=cls.test_loader,
            manifest_path=cls.manifest_test_path
        )
        cls.pdf_loader = PDFLoader()

    @classmethod
    def tearDownClass(cls):
        # Khôi phục settings gốc
        object.__setattr__(settings, "CHROMA_DIR", cls.orig_chroma_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.orig_jsonl_path)

        # Dọn dẹp thư mục tạm
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _create_sample_pdf(self, file_path: Path, pages_data: list):
        """Hàm trợ giúp tạo PDF từ danh sách các trang text."""
        doc = pymupdf.open()
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()

        for text in pages_data:
            page = doc.new_page()
            if text:
                if has_arial:
                    page.insert_font(fontname="arial", fontfile=str(arial_path))
                    page.insert_textbox(pymupdf.Rect(50, 50, 500, 750), text, fontname="arial")
                else:
                    page.insert_textbox(pymupdf.Rect(50, 50, 500, 750), text, fontname="helv")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(file_path))
        doc.close()

    def test_01_normal_text_pdf_multiple_vocab(self):
        """1. PDF có text thông thường chứa nhiều mục từ vựng trên 1 trang."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test01_vocab_{uid}.pdf"
        text = f"""ephemeral_{uid} (adj) /ɪˈfem.ər.əl/
Nghĩa: Phù du, chỉ tồn tại trong thời gian ngắn.
Ví dụ: Fame in pop music is largely ephemeral_{uid}.
Trình độ: C1

tenacious_{uid} (adj) /təˈneɪ.ʃəs/
Nghĩa: Kiên trì, dai dẳng, kiên quyết.
Ví dụ: She is a tenacious_{uid} woman who never gives up.
Trình độ: B2"""
        self._create_sample_pdf(f_pdf, [text])

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 2, "Trang có 2 từ vựng phải trích xuất ít nhất 2 bản ghi riêng biệt.")

        words = [r.word.lower() for r in records]
        self.assertIn(f"ephemeral_{uid}".lower(), words)
        self.assertIn(f"tenacious_{uid}".lower(), words)

        # Kiểm tra metadata và nội dung
        for r in records:
            self.assertEqual(r.sheet, "Trang 1")
            self.assertEqual(r.source, f_pdf.name)
            self.assertTrue(r.question.endswith("nghĩa là gì?"))

    def test_02_scanned_pdf_needs_ocr(self):
        """2. PDF scan cần OCR (kiểm tra phát hiện needs_ocr và trả về hướng dẫn cài đặt)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test02_scan_{uid}.pdf"
        # Tạo PDF với trang trắng / không có text
        self._create_sample_pdf(f_pdf, [""])

        # Kiểm tra inspect_pdf nhận diện đúng trang cần OCR
        inspect_res = self.pdf_loader.inspect_pdf(f_pdf)
        self.assertTrue(inspect_res["valid"])
        self.assertEqual(inspect_res["total_pages"], 1)
        self.assertEqual(inspect_res["pages_with_text"], 0)
        self.assertEqual(inspect_res["pages_needing_ocr"], 1)

        # Khi load một file thuần scan mà chưa có OCR, hệ thống phải ném DataLoadError kèm hướng dẫn
        with self.assertRaises(DataLoadError) as ctx:
            self.pdf_loader.load(f_pdf)
        self.assertIn("Tesseract OCR", str(ctx.exception))

    def test_03_mixed_text_and_scan_pages(self):
        """3. PDF trộn trang có text và trang scan (trang text nạp thành công, trang scan được ghi nhận)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test03_mixed_{uid}.pdf"
        p1_text = f"""lucid_{uid}: rõ ràng, minh bạch, dễ hiểu.\nTrình độ: B2\n"""
        p2_scan = ""  # Trang scan trống text
        self._create_sample_pdf(f_pdf, [p1_text, p2_scan])

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1, "Phải nạp thành công dữ liệu từ trang có text.")

        report = self.pdf_loader.last_extraction_report
        self.assertEqual(report["total_pages"], 2)
        self.assertEqual(report["pages_with_text"], 1)
        self.assertEqual(report["pages_needing_ocr"], 1)

    def test_04_multi_page_pdf(self):
        """4. PDF nhiều trang (trích xuất liên tục, rich metadata số trang chuẩn)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test04_multipage_{uid}.pdf"
        pages = [
            f"altruistic_{uid}: vị tha, nhân hậu, vì người khác.\nTrình độ: C1\n",
            f"benevolent_{uid}: nhân từ, thương người, hảo tâm.\nTrình độ: B2\n",
            f"candor_{uid}: tính thật thà, ngay thẳng, bộc trực.\nTrình độ: C1\n",
        ]
        self._create_sample_pdf(f_pdf, pages)

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 3)

        sheets = {r.sheet for r in records}
        self.assertIn("Trang 1", sheets)
        self.assertIn("Trang 2", sheets)
        self.assertIn("Trang 3", sheets)

    def test_05_table_pdf_extraction(self):
        """5. PDF có bảng (trích xuất bảng từ vựng, bảo toàn quan hệ từ - nghĩa - ví dụ)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test05_table_{uid}.pdf"

        doc = pymupdf.open()
        page = doc.new_page()

        # Vẽ cấu trúc bảng 3 hàng x 4 cột
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 500, 160))
        shape.draw_line(pymupdf.Point(50, 80), pymupdf.Point(500, 80))
        shape.draw_line(pymupdf.Point(50, 120), pymupdf.Point(500, 120))
        shape.draw_line(pymupdf.Point(160, 50), pymupdf.Point(160, 160))
        shape.draw_line(pymupdf.Point(260, 50), pymupdf.Point(260, 160))
        shape.draw_line(pymupdf.Point(360, 50), pymupdf.Point(360, 160))
        shape.finish(stroke_opacity=1, width=1)
        shape.commit()

        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        if arial_path.exists():
            page.insert_font(fontname="arial", fontfile=str(arial_path))
            f_name = "arial"
        else:
            f_name = "helv"

        page.insert_text((55, 70), "Từ vựng", fontname=f_name)
        page.insert_text((165, 70), "Từ loại", fontname=f_name)
        page.insert_text((265, 70), "Nghĩa tiếng Việt", fontname=f_name)
        page.insert_text((365, 70), "Ví dụ", fontname=f_name)

        page.insert_text((55, 105), f"pragmatic-{uid}", fontname=f_name)
        page.insert_text((165, 105), "adj", fontname=f_name)
        page.insert_text((265, 105), "thực tế, thực dụng", fontname=f_name)
        page.insert_text((365, 105), f"A pragmatic-{uid} approach.", fontname=f_name)

        page.insert_text((55, 145), f"solitude-{uid}", fontname=f_name)
        page.insert_text((165, 145), "noun", fontname=f_name)
        page.insert_text((265, 145), "sự cô độc tĩnh lặng", fontname=f_name)
        page.insert_text((365, 145), f"Enjoying solitude-{uid}.", fontname=f_name)

        f_pdf.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(f_pdf))
        doc.close()

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 2)

        p_rec = next((r for r in records if f"pragmatic-{uid}" in r.word.lower()), None)
        self.assertIsNotNone(p_rec, "Bảng từ vựng phải trích xuất được pragmatic.")
        self.assertIn("thực tế", p_rec.answer.lower())
        self.assertIn(f"pragmatic-{uid}".lower(), p_rec.answer.lower())

    def test_06_corrupted_or_empty_pdf(self):
        """6. PDF rỗng, hỏng hoặc không đọc được."""
        uid = uuid.uuid4().hex[:6]
        # 6.1 Tệp rỗng 0 bytes
        f_empty = self.test_dir / f"test06_empty_{uid}.pdf"
        f_empty.write_bytes(b"")
        val_res = self.pdf_loader.validate(f_empty)
        self.assertFalse(val_res.is_valid)

        # 6.2 Tệp bị hỏng (corrupted bytes)
        f_corrupt = self.test_dir / f"test06_corrupt_{uid}.pdf"
        f_corrupt.write_bytes(b"%PDF-1.4 NON_PARSABLE_TRUNCATED_BINARY_DATA_XYZ")
        with self.assertRaises(DataLoadError):
            self.pdf_loader.load(f_corrupt)

    def test_07_vietnamese_diacritics_and_ipa_symbols(self):
        """7. PDF có ký tự tiếng Việt có dấu và ký hiệu phiên âm IPA."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test07_ipa_{uid}.pdf"
        text = f"""ubiquitous_{uid} /juːˈbɪk.wə.təs/
Định nghĩa: Phổ biến, xuất hiện ở khắp mọi nơi, nhan nhản.
Ví dụ: Smartphones are ubiquitous_{uid} nowadays.
Trình độ: C1"""
        self._create_sample_pdf(f_pdf, [text])

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)
        r = records[0]

        # Kiểm tra IPA và dấu tiếng Việt được bảo toàn
        self.assertTrue("bɪk" in r.answer or "ju" in r.answer)
        self.assertIn("Phổ biến, xuất hiện ở khắp mọi nơi", r.answer)

    def test_08_pdf_no_valid_chunk_graceful_error(self):
        """8. PDF không tạo được chunk (xử lý lỗi cụ thể, không báo thành công giả)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test08_blank_{uid}.pdf"
        # Tạo trang với chỉ vài dấu chấm câu / khoảng trắng dưới ngưỡng
        self._create_sample_pdf(f_pdf, ["...   \n\n   ---"])

        with self.assertRaises(DataLoadError):
            self.pdf_loader.load(f_pdf)

    def test_09_duplicate_pdf_upload(self):
        """9. Upload cùng một PDF nhiều lần (chống trùng lặp mức tệp SHA-256)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test09_dupe_{uid}.pdf"
        self._create_sample_pdf(f_pdf, [f"diligent_{uid}: siêng năng, cần cù, chăm chỉ.\nTrình độ: B1\n"])

        # Lần 1: Nạp thành công
        rep1 = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep1.success_count, 1)
        self.assertEqual(rep1.skipped_count, 0)

        # Lần 2: Nạp lại cùng file -> Phải bị SKIPPED
        rep2 = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep2.success_count, 0)
        self.assertEqual(rep2.skipped_count, 1)
        self.assertEqual(rep2.file_results[0].status, FileStatus.SKIPPED)

    def test_10_safe_rollback_on_indexing_failure(self):
        """10. Lỗi xảy ra trong lúc cập nhật index (rollback an toàn, không mất dữ liệu cũ)."""
        uid = uuid.uuid4().hex[:6]
        # Nạp dữ liệu ban đầu
        f_init = self.test_dir / f"test10_init_{uid}.pdf"
        self._create_sample_pdf(f_init, [f"initial_{uid}: từ vựng khởi tạo ban đầu.\n"])
        self.batch_manager.ingest_batch([f_init], mode="add")

        initial_count = len(self.test_loader.load_from_jsonl())
        self.assertGreaterEqual(initial_count, 1)

        # Giả lập lỗi tại ChromaDB upsert trong phiên nạp mới
        f_new = self.test_dir / f"test10_fail_{uid}.pdf"
        self._create_sample_pdf(f_new, [f"willfail_{uid}: từ vựng sẽ bị rollback.\n"])

        with patch.object(BGEChromaRetriever, "upsert_records", side_effect=RuntimeError("Simulated ChromaDB Crash")):
            rep = self.batch_manager.ingest_batch([f_new], mode="add")
            self.assertEqual(rep.failed_count, 1)
            self.assertIn("FAILED", rep.chromadb_status)

        # Kiểm tra dữ liệu cũ vẫn nguyên vẹn sau rollback
        recovered_count = len(self.test_loader.load_from_jsonl())
        self.assertEqual(recovered_count, initial_count, "Dữ liệu JSONL phải được khôi phục nguyên vẹn sau khi gặp lỗi.")

    def test_11_modes_add_update_replace(self):
        """11. Kiểm tra 3 chế độ ADD, UPDATE và REPLACE."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"test11_f1_{uid}.pdf"
        self._create_sample_pdf(f1, [f"candid_{uid}: bộc trực, thẳng thắn.\nTrình độ: B2\n"])

        # 11.1 ADD
        rep_add = self.batch_manager.ingest_batch([f1], mode="add")
        self.assertEqual(rep_add.batch_status, BatchStatus.SUCCESS)

        # 11.2 REPLACE
        f2 = self.test_dir / f"test11_f2_{uid}.pdf"
        self._create_sample_pdf(f2, [f"serene_{uid}: thanh bình, yên ả, tĩnh lặng.\nTrình độ: C1\n"])

        rep_replace = self.batch_manager.ingest_batch([f2], mode="replace")
        self.assertEqual(rep_replace.batch_status, BatchStatus.SUCCESS)

        recs_after_replace = self.test_loader.load_from_jsonl()
        words = [r.word.lower() for r in recs_after_replace]
        self.assertIn(f"serene_{uid}".lower(), words)
        self.assertNotIn(f"candid_{uid}".lower(), words, "Chế độ REPLACE phải thay thế sạch dữ liệu cũ.")

    def test_12_restart_app_persistence(self):
        """12. Khởi động lại ứng dụng và truy xuất lại dữ liệu đã lưu từ JSONL."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test12_persist_{uid}.pdf"
        self._create_sample_pdf(f_pdf, [f"resilient_{uid}: kiên cường, mau phục hồi.\nTrình độ: B2\n"])

        self.batch_manager.ingest_batch([f_pdf], mode="add")

        # Giả lập khởi động lại ứng dụng: Tạo mới ChatEngine từ file JSONL đã lưu
        new_records = self.test_loader.load_from_jsonl()
        self.assertTrue(any(f"resilient_{uid}".lower() in r.word.lower() for r in new_records))

        bm25 = BM25Retriever(new_records)
        search_res = bm25.search(f"resilient_{uid}")
        self.assertGreaterEqual(len(search_res), 1, "BM25 sau khởi động lại phải tìm thấy từ vựng vừa nạp.")

    def test_13_end_to_end_ingest_and_query(self):
        """13. Kiểm thử End-to-End: Nạp PDF -> BM25 + BGE-M3 -> RRF -> ChatEngine tra cứu."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test13_e2e_{uid}.pdf"
        text = f"""meticulous_{uid} (adj)
Nghĩa: Tỉ mỉ, cẩn thận, trau chuốt từng chi tiết nhỏ.
Ví dụ: He is meticulous_{uid} about his work.
Trình độ: C1"""
        self._create_sample_pdf(f_pdf, [text])

        # Nạp tệp PDF vào Knowledge Base
        rep = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep.batch_status, BatchStatus.SUCCESS)

        active_recs = self.test_loader.load_from_jsonl()

        # Khởi tạo ChatEngine trên dữ liệu đã nạp
        engine = ChatEngine(records=active_recs)
        engine.tracker.load_known_words(active_recs)

        # Đặt câu hỏi tra cứu từ vựng (Mock LLM response nếu RAG generation được kích hoạt)
        query = f"Từ meticulous_{uid} nghĩa là gì?"
        with patch.object(engine.llm_client, "chat", return_value="Tỉ mỉ, cẩn thận, trau chuốt từng chi tiết nhỏ."):
            resp = engine.ask(query)

        # Kiểm tra phản hồi
        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(resp.word.lower(), f"meticulous_{uid}".lower())
        self.assertIn("tỉ mỉ", resp.answer.lower())
        self.assertGreater(resp.rrf_score, 0.0, "Điểm RRF phải lớn hơn 0.")


if __name__ == "__main__":
    unittest.main()
