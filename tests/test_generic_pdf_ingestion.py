"""Bộ kiểm thử toàn diện cho hệ thống Generic PDF Ingestion & Retrieval (14 Kịch Bản Tổng Quát).

Kiểm thử 14 kịch bản theo yêu cầu nghiệp vụ:
1. test_01_single_column_general_narrative_article: PDF bài viết 1 cột thông thường.
2. test_02_two_column_reading_order: PDF bố cục 2 cột bảo toàn thứ tự đọc cột 1 -> cột 2.
3. test_03_multi_column_oxford_fixture: PDF từ vựng 4 cột (The Oxford 5000) trích xuất từng từ.
4. test_04_generic_table_extraction: PDF có bảng biểu thông tin tổng quát (không phải bảng từ vựng).
5. test_05_hierarchical_sections_and_headings: PDF có tiêu đề phân cấp (Chương / Mục / Section).
6. test_06_scanned_pdf_tesseract_check: PDF scan (ảnh) kiểm tra needs_ocr và OCRHandler.
7. test_07_mixed_text_and_scanned_pages: PDF trang text kết hợp trang ảnh scan.
8. test_08_vietnamese_diacritics_and_ipa: Bảo toàn tiếng Việt có dấu và ký hiệu ngữ âm IPA.
9. test_09_header_footer_page_number_filtering: Lọc header/footer/số trang ngoài lề trang.
10. test_10_corrupt_and_empty_pdf_handling: Xử lý tệp hỏng, 0 bytes hoặc PDF không hợp lệ.
11. test_11_batch_ingestion_multiple_distinct_pdfs: Nạp batch nhiều PDF khác nhau cùng lúc.
12. test_12_duplicate_upload_idempotency: Chống nạp trùng lặp dựa trên SHA-256 hash.
13. test_13_transaction_rollback_preserves_kb: Rollback an toàn khi xảy ra lỗi lập chỉ mục.
14. test_14_end_to_end_rag_retrieval: Tra cứu End-to-End từ bài viết tổng quát qua BM25 + BGE-M3 + RRF.
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


class TestGenericPDFIngestion(unittest.TestCase):
    """Bộ kiểm thử tổng quát cho bộ xử lý PDF (Generic PDF Ingestion)."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = PROJECT_ROOT / "temp_test_generic_pdf"
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
        """Hàm trợ giúp tạo PDF đơn giản từ danh sách các trang text."""
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

    def test_01_single_column_general_narrative_article(self):
        """1. PDF bài viết 1 cột thông thường: trích xuất theo đoạn văn, không gán từ vựng hay CEFR giả."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test01_article_{uid}.pdf"
        article_text = f"""Kiến trúc Hệ thống RAG Cục bộ

Retrieval-Augmented Generation (RAG) là một phương pháp kết hợp sức mạnh của mô hình ngôn ngữ lớn (LLM) với cơ sở tri thức cục bộ chuyên biệt.

Trong Chatbox 2.0, quy trình tra cứu sử dụng cơ chế lai kết hợp giữa BM25 và BGE-M3, sau đó hợp nhất qua Reciprocal Rank Fusion (RRF) nhằm mang lại kết quả chính xác nhất. Mã định danh bài viết: article_{uid}."""
        self._create_sample_pdf(f_pdf, [article_text])

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)

        # Kiểm tra tính tổng quát: không tự gán từ vựng hoặc cấp độ cho bài viết tự sự
        for rec in records:
            self.assertEqual(rec.word, "")
            self.assertEqual(rec.level, "")
            self.assertEqual(rec.metadata.get("content_type"), "general_text")
            self.assertIn("Trang 1", rec.sheet)

        full_content = " ".join(r.answer for r in records)
        self.assertIn(f"article_{uid}", full_content)
        self.assertIn("Retrieval-Augmented Generation", full_content)

    def test_02_two_column_reading_order(self):
        """2. PDF 2 cột: bảo toàn thứ tự đọc tự nhiên (cột trái từ trên xuống dưới, sau đó đến cột phải)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test02_twocol_{uid}.pdf"

        # Tạo PDF 2 cột với toạ độ cụ thể
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()
        font_arg = {"fontname": "arial", "fontfile": str(arial_path)} if has_arial else {"fontname": "helv"}

        # Cột trái (x: 50 -> 280)
        c1_top = f"Cột 1 Đoạn Đầu_{uid}: Giới thiệu phần mềm mã nguồn mở và kiến trúc hướng module."
        c1_bot = f"Cột 1 Đoạn Cuối_{uid}: Các thành phần cốt lõi của quy trình xử lý dữ liệu đầu vào."
        page.insert_textbox(pymupdf.Rect(50, 60, 280, 200), c1_top, **font_arg)
        page.insert_textbox(pymupdf.Rect(50, 220, 280, 400), c1_bot, **font_arg)

        # Cột phải (x: 320 -> 550)
        c2_top = f"Cột 2 Đoạn Đầu_{uid}: Đánh giá hiệu năng và so sánh tốc độ xử lý vector embedding."
        c2_bot = f"Cột 2 Đoạn Cuối_{uid}: Kết luận và định hướng phát triển các module tương lai."
        page.insert_textbox(pymupdf.Rect(320, 60, 550, 200), c2_top, **font_arg)
        page.insert_textbox(pymupdf.Rect(320, 220, 550, 400), c2_bot, **font_arg)

        doc.save(str(f_pdf))
        doc.close()

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 2)

        # Kiểm tra thứ tự xuất hiện của nội dung
        all_text = "\n".join(r.answer for r in records)
        pos_c1_top = all_text.find(f"Cột 1 Đoạn Đầu_{uid}")
        pos_c1_bot = all_text.find(f"Cột 1 Đoạn Cuối_{uid}")
        pos_c2_top = all_text.find(f"Cột 2 Đoạn Đầu_{uid}")
        pos_c2_bot = all_text.find(f"Cột 2 Đoạn Cuối_{uid}")

        self.assertNotEqual(pos_c1_top, -1)
        self.assertNotEqual(pos_c1_bot, -1)
        self.assertNotEqual(pos_c2_top, -1)
        self.assertNotEqual(pos_c2_bot, -1)

        self.assertLess(pos_c1_top, pos_c1_bot, "Cột 1 đoạn đầu phải đọc trước cột 1 đoạn cuối.")
        self.assertLess(pos_c1_bot, pos_c2_top, "Cột 1 phải đọc xong trước khi sang Cột 2.")
        self.assertLess(pos_c2_top, pos_c2_bot, "Cột 2 đoạn đầu phải đọc trước cột 2 đoạn cuối.")

    def test_03_multi_column_oxford_fixture(self):
        """3. PDF từ vựng 4 cột (The Oxford 5000): trích xuất >1500 records, itemized words, B2/C1 levels."""
        oxford_pdf = PROJECT_ROOT / "data" / "raw" / "The_Oxford_5000_by_CEFR_level.pdf"
        if not oxford_pdf.exists():
            self.skipTest(f"Không tìm thấy file mẫu: {oxford_pdf}")

        records = self.pdf_loader.load(oxford_pdf)
        self.assertGreaterEqual(len(records), 1500, "Oxford 5000 phải trích xuất được hơn 1500 bản ghi.")

        rep = self.pdf_loader.last_extraction_report
        self.assertEqual(rep.get("total_pages"), 8)
        self.assertEqual(rep.get("columns_detected"), 4)

        # Kiểm tra sự hiện diện của từ vựng mẫu
        words = {r.word.lower() for r in records if r.word}
        self.assertIn("absorb", words)
        self.assertIn("abstract", words)
        self.assertIn("accent", words)

        # Kiểm tra nhận diện cấp độ B2 và C1
        levels = {r.level for r in records if r.level}
        self.assertIn("B2", levels)
        self.assertIn("C1", levels)

    def test_04_generic_table_extraction(self):
        """4. PDF bảng biểu thông tin tổng quát (không phải bảng từ vựng): trích xuất thành Markdown key-value."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test04_table_{uid}.pdf"

        # Tạo PDF có bảng biểu tổng quát
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()
        font_arg = {"fontname": "arial", "fontfile": str(arial_path)} if has_arial else {"fontname": "helv"}

        # Dùng vẽ bảng qua đường line để PyMuPDF find_tables nhận diện
        page.draw_rect(pymupdf.Rect(50, 100, 550, 250), color=(0, 0, 0), width=1)
        page.draw_line(pymupdf.Point(50, 150), pymupdf.Point(550, 150), color=(0, 0, 0), width=1)
        page.draw_line(pymupdf.Point(50, 200), pymupdf.Point(550, 200), color=(0, 0, 0), width=1)
        page.draw_line(pymupdf.Point(200, 100), pymupdf.Point(200, 250), color=(0, 0, 0), width=1)
        page.draw_line(pymupdf.Point(380, 100), pymupdf.Point(380, 250), color=(0, 0, 0), width=1)

        # Chèn text vào các ô
        # Header
        page.insert_textbox(pymupdf.Rect(55, 110, 195, 145), "Mã Thiết Bị", **font_arg)
        page.insert_textbox(pymupdf.Rect(205, 110, 375, 145), "Tên Thiết Bị", **font_arg)
        page.insert_textbox(pymupdf.Rect(385, 110, 545, 145), "Trạng Thái", **font_arg)

        # Row 1
        page.insert_textbox(pymupdf.Rect(55, 160, 195, 195), f"DEV-{uid}-01", **font_arg)
        page.insert_textbox(pymupdf.Rect(205, 160, 375, 195), "Máy chủ GPU", **font_arg)
        page.insert_textbox(pymupdf.Rect(385, 160, 545, 195), "Hoạt động", **font_arg)

        # Row 2
        page.insert_textbox(pymupdf.Rect(55, 210, 195, 245), f"DEV-{uid}-02", **font_arg)
        page.insert_textbox(pymupdf.Rect(205, 210, 375, 245), "Switch Quang", **font_arg)
        page.insert_textbox(pymupdf.Rect(385, 210, 545, 245), "Bảo trì", **font_arg)

        doc.save(str(f_pdf))
        doc.close()

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)

        # Bảng phải được trích xuất (nếu PyMuPDF nhận diện table) hoặc fallback text trọn vẹn
        all_text = " ".join(r.answer for r in records)
        self.assertIn(f"DEV-{uid}-01", all_text)
        self.assertIn("Máy chủ GPU", all_text)

    def test_05_hierarchical_sections_and_headings(self):
        """5. PDF có tiêu đề phân cấp: nhận diện tiêu đề và lưu trong ngữ cảnh metadata."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test05_headings_{uid}.pdf"

        doc = pymupdf.open()
        page = doc.new_page()
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()
        font_arg = {"fontname": "arial", "fontfile": str(arial_path)} if has_arial else {"fontname": "helv"}

        # Block 1: Tiêu đề Chương 1
        page.insert_textbox(pymupdf.Rect(50, 50, 500, 80), "Chương 1: Tổng quan dự án Chatbox", **font_arg)
        # Block 2: Nội dung Chương 1
        page.insert_textbox(pymupdf.Rect(50, 90, 500, 200), f"Dự án Chatbox 2.0 triển khai mô hình RAG cục bộ mã hoá ID {uid}.", **font_arg)
        # Block 3: Tiêu đề Mục 2
        page.insert_textbox(pymupdf.Rect(50, 220, 500, 250), "Chương 2: Thiết kế kiến trúc", **font_arg)
        # Block 4: Nội dung Chương 2
        page.insert_textbox(pymupdf.Rect(50, 260, 500, 380), f"Kiến trúc phân tách rõ ràng giữa Ingestion pipeline và Query engine phiên bản {uid}.", **font_arg)

        doc.save(str(f_pdf))
        doc.close()

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 2)

        # Kiểm tra metadata và ngữ cảnh câu hỏi của các chunk
        headings_in_meta = [r.metadata.get("heading", "") for r in records]
        self.assertTrue(any("Chương 1" in h for h in headings_in_meta) or any("Chương 1" in r.question for r in records))
        self.assertTrue(any("Chương 2" in h for h in headings_in_meta) or any("Chương 2" in r.question for r in records))

    def test_06_scanned_pdf_tesseract_check(self):
        """6. PDF scan (chỉ có ảnh không có text): kiểm tra phát hiện needs_ocr và xử lý môi trường."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test06_scan_{uid}.pdf"

        # Tạo PDF chỉ có hình ảnh đồ họa (không có text)
        doc = pymupdf.open()
        page = doc.new_page()
        page.draw_circle(pymupdf.Point(200, 200), 50, color=(1, 0, 0), fill=(0, 1, 0))
        doc.save(str(f_pdf))
        doc.close()

        ocr_status = OCRHandler.check_environment()
        if not ocr_status["is_ready"]:
            # Chưa có Tesseract: Phải raise DataLoadError kèm hướng dẫn cài đặt minh bạch
            with self.assertRaises(DataLoadError) as ctx:
                self.pdf_loader.load(f_pdf)
            self.assertIn("Tesseract OCR", str(ctx.exception))
        else:
            # Nếu môi trường có Tesseract, hàm chạy an toàn
            pages = self.pdf_loader._extract_pages_content(f_pdf)
            self.assertTrue(pages[0].ocr_attempted)

    def test_07_mixed_text_and_scanned_pages(self):
        """7. PDF trộn trang text và trang ảnh scan: trích xuất trang text mà không bỏ qua trang scan."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test07_mixed_{uid}.pdf"

        doc = pymupdf.open()
        # Trang 1: Text bình thường
        p1 = doc.new_page()
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()
        font_arg = {"fontname": "arial", "fontfile": str(arial_path)} if has_arial else {"fontname": "helv"}
        p1.insert_textbox(pymupdf.Rect(50, 50, 500, 300), f"Trang 1 có văn bản chuẩn xác với định danh mixed_{uid}.", **font_arg)

        # Trang 2: Chỉ có hình vẽ (ảnh)
        p2 = doc.new_page()
        p2.draw_rect(pymupdf.Rect(100, 100, 300, 300), fill=(0.5, 0.5, 0.5))

        doc.save(str(f_pdf))
        doc.close()

        pages_extracted = self.pdf_loader._extract_pages_content(f_pdf)
        self.assertEqual(len(pages_extracted), 2)
        self.assertFalse(pages_extracted[0].needs_ocr)
        self.assertTrue(pages_extracted[1].needs_ocr)

        # Nạp dữ liệu qua load()
        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)
        self.assertTrue(any(f"mixed_{uid}" in r.answer for r in records))

    def test_08_vietnamese_diacritics_and_ipa(self):
        """8. Bảo toàn 100% tiếng Việt có dấu đầy đủ và ký hiệu ngữ âm IPA."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test08_unicode_{uid}.pdf"

        # Văn bản tiếng Việt có dấu phức tạp và ký tự IPA
        sample_text = f"""Bảo Toàn Ký Tự Tiếng Việt & Ngữ Âm IPA ({uid})

Tiếng Việt: "Học tập, nghiên cứu và phát triển trí tuệ nhân tạo ở Việt Nam đòi hỏi sự kiên nhẫn, nỗ lực không ngừng nghỉ."
Ký hiệu IPA: /əbˈsɔːb/, /ˈæksənt/, /ɪˈfem.ər.əl/, /təˈneɪ.ʃəs/.
Các nguyên âm và thanh điệu: á à ả ã ạ, ắ ằ ẳ ẵ ặ, ấ ầ ổ ỗ ộ, ứ ừ ử ữ ự."""

        self._create_sample_pdf(f_pdf, [sample_text])

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)

        all_text = " ".join(r.answer for r in records)
        self.assertIn("Học tập, nghiên cứu", all_text)
        self.assertIn("nghiên cứu và phát triển", all_text)
        self.assertIn("á à ả ã ạ", all_text)
        self.assertIn("ắ ằ ẳ ẵ ặ", all_text)
        self.assertIn("ấ ầ ổ ỗ ộ", all_text)
        self.assertIn("ứ ừ ử ữ ự", all_text)
        self.assertTrue("sɔːb" in all_text or "æks" in all_text)

    def test_09_header_footer_page_number_filtering(self):
        """9. Lọc header/footer/số trang ngoài lề (margin) không tạo chunk rác."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test09_margins_{uid}.pdf"

        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        has_arial = arial_path.exists()
        font_arg = {"fontname": "arial", "fontfile": str(arial_path)} if has_arial else {"fontname": "helv"}

        # Header ở mép trên (y: 10 -> 35)
        page.insert_textbox(pymupdf.Rect(50, 10, 550, 35), "Báo cáo kỹ thuật Chatbox 2.0 - Header Bí Mật Không Cần Chunk", **font_arg)

        # Nội dung chính (y: 80 -> 400)
        main_content = f"Nội dung cốt lõi của tài liệu phân tích hệ thống {uid}. Các thuật toán tối ưu hóa vector retrieval."
        page.insert_textbox(pymupdf.Rect(50, 80, 550, 400), main_content, **font_arg)

        # Footer ở mép dưới (y: 770 -> 795)
        page.insert_textbox(pymupdf.Rect(50, 770, 550, 795), "1 / 10 | Bản quyền thuộc về Chatbox 2.0", **font_arg)

        doc.save(str(f_pdf))
        doc.close()

        records = self.pdf_loader.load(f_pdf)
        self.assertGreaterEqual(len(records), 1)

        # Chunk chính phải có
        all_text = " ".join(r.answer for r in records)
        self.assertIn(f"Nội dung cốt lõi của tài liệu", all_text)
        # Footer "1 / 10" phải bị loại bỏ không tạo thành chunk độc lập
        self.assertNotIn("1 / 10 | Bản quyền", [r.answer.strip() for r in records])

    def test_10_corrupt_and_empty_pdf_handling(self):
        """10. Xử lý tệp hỏng, 0 bytes hoặc PDF không hợp lệ (DataLoadError rõ ràng)."""
        uid = uuid.uuid4().hex[:6]
        # 10.1 File rỗng 0 bytes
        f_empty = self.test_dir / f"test10_empty_{uid}.pdf"
        f_empty.write_bytes(b"")

        with self.assertRaises(DataLoadError) as ctx:
            self.pdf_loader.load(f_empty)
        err_msg = str(ctx.exception).lower()
        self.assertTrue("rỗng" in err_msg or "empty" in err_msg, f"Thông báo lỗi phải chỉ ra tệp rỗng: {err_msg}")

        # 10.2 File hỏng byte rác
        f_corrupt = self.test_dir / f"test10_corrupt_{uid}.pdf"
        f_corrupt.write_bytes(b"%PDF-INVALID_CORRUPT_BYTES_XYZ123")

        with self.assertRaises(DataLoadError):
            self.pdf_loader.load(f_corrupt)

    def test_11_batch_ingestion_multiple_distinct_pdfs(self):
        """11. Nạp batch nhiều PDF khác nhau cùng lúc (1 bài viết, 1 từ điển, 1 thông báo)."""
        uid = uuid.uuid4().hex[:6]
        f1 = self.test_dir / f"test11_article_{uid}.pdf"
        f2 = self.test_dir / f"test11_dict_{uid}.pdf"
        f3 = self.test_dir / f"test11_memo_{uid}.pdf"

        self._create_sample_pdf(f1, [f"Bài viết khoa học về xử lý văn bản tự nhiên {uid}."])
        self._create_sample_pdf(f2, [f"diligent_{uid} (adj)\nNghĩa: Cần cù, chăm chỉ.\nTrình độ: B2"])
        self._create_sample_pdf(f3, [f"Thông báo nội bộ về lịch bảo trì định kỳ của cụm máy chủ {uid}."])

        report = self.batch_manager.ingest_batch([f1, f2, f3], mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(report.total_files, 3)
        self.assertEqual(report.success_count, 3)
        self.assertEqual(report.failed_count, 0)

        # Kiểm tra toàn bộ đã có mặt trong JSONL
        records = self.test_loader.load_from_jsonl()
        answers_str = " ".join(r.answer for r in records)
        self.assertIn(f"khoa học về xử lý văn bản", answers_str)
        self.assertIn(f"diligent_{uid}", [r.word.lower() for r in records if r.word])
        self.assertIn(f"lịch bảo trì định kỳ", answers_str)

    def test_12_duplicate_upload_idempotency(self):
        """12. Chống nạp trùng lặp dựa trên SHA-256 hash (idempotency)."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test12_dup_{uid}.pdf"
        self._create_sample_pdf(f_pdf, [f"Tài liệu độc nhất vô nhị kiểm tra chống trùng {uid}."])

        # Nạp lần 1
        rep1 = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep1.batch_status, BatchStatus.SUCCESS)
        count_1 = len(self.test_loader.load_from_jsonl())

        # Nạp lần 2 cùng file đó
        rep2 = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep2.skipped_count, 1)
        self.assertEqual(rep2.file_results[0].status, FileStatus.SKIPPED)

        # Số lượng bản ghi trong JSONL không thay đổi
        count_2 = len(self.test_loader.load_from_jsonl())
        self.assertEqual(count_1, count_2, "Tệp trùng SHA-256 không được phép nhân bản dữ liệu.")

    def test_13_transaction_rollback_preserves_kb(self):
        """13. Rollback an toàn khi xảy ra lỗi lập chỉ mục: KB cũ được bảo toàn 100%."""
        uid = uuid.uuid4().hex[:6]
        # Tạo dữ liệu ban đầu
        f_init = self.test_dir / f"test13_init_{uid}.pdf"
        self._create_sample_pdf(f_init, [f"Dữ liệu ban đầu cần được bảo toàn tuyệt đối {uid}."])
        self.batch_manager.ingest_batch([f_init], mode="add")

        initial_count = len(self.test_loader.load_from_jsonl())
        self.assertGreaterEqual(initial_count, 1)

        # Nạp tệp mới nhưng giả lập lỗi sập ChromaDB
        f_fail = self.test_dir / f"test13_crash_{uid}.pdf"
        self._create_sample_pdf(f_fail, [f"Dữ liệu này sẽ gây lỗi và phải được rollback {uid}."])

        with patch.object(BGEChromaRetriever, "upsert_records", side_effect=RuntimeError("ChromaDB Simulated Disk Full")):
            rep = self.batch_manager.ingest_batch([f_fail], mode="add")
            self.assertEqual(rep.failed_count, 1)

        # Kiểm tra dữ liệu được khôi phục nguyên trạng
        recovered_count = len(self.test_loader.load_from_jsonl())
        self.assertEqual(recovered_count, initial_count, "Rollback phải khôi phục chính xác dữ liệu trước khi xảy ra lỗi.")

    def test_14_end_to_end_rag_retrieval(self):
        """14. Tra cứu End-to-End từ bài viết tổng quát qua BM25 + BGE-M3 + RRF."""
        uid = uuid.uuid4().hex[:6]
        f_pdf = self.test_dir / f"test14_rag_{uid}.pdf"
        text = f"""Tổng quan về Cơ chế Chấm điểm PhoBERT và RRF ({uid})

PhoBERT là mô hình ngôn ngữ dựa trên kiến trúc RoBERTa được huấn luyện đặc thù cho tiếng Việt.
Trong hệ thống Chatbox 2.0, PhoBERT được sử dụng trong bước Query Normalization và Relevance Gate.
Khi kết hợp cùng Reciprocal Rank Fusion (RRF), hệ thống đạt độ chính xác cao và triệt tiêu hallucination {uid}."""

        self._create_sample_pdf(f_pdf, [text])
        rep = self.batch_manager.ingest_batch([f_pdf], mode="add")
        self.assertEqual(rep.batch_status, BatchStatus.SUCCESS)

        active_recs = self.test_loader.load_from_jsonl()
        engine = ChatEngine(records=active_recs)
        engine.tracker.load_known_words(active_recs)

        # Đặt câu hỏi truy xuất bài viết
        query = f"Từ PhoBERT_{uid} có ý nghĩa gì trong bài viết?"
        expected_ans = f"PhoBERT_{uid} là mô hình ngôn ngữ tiếng Việt được sử dụng trong bước Query Normalization và Relevance Gate."
        with patch.object(engine.llm_client, "generate_with_langchain", return_value=expected_ans), \
             patch.object(engine.llm_client, "chat", return_value=expected_ans):
            resp = engine.ask(query)

        self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertGreater(resp.rrf_score, 0.0, "Điểm RRF phải dương khi tìm thấy tài liệu phù hợp.")
        self.assertIn(f"PhoBERT_{uid}", resp.answer)


if __name__ == "__main__":
    unittest.main()
