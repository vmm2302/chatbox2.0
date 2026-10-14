"""Kiểm thử toàn diện các cải tiến cho PDFLoader (Generic PDF Ingestion Test Suite).

Kiểm tra:
1. Không chuyển hướng sang Oxford parser chỉ vì tên file chứa 'oxford'.
2. PDF 2 cột được sắp xếp theo đúng thứ tự đọc tự nhiên (cột trái trước, cột phải sau).
3. Trang scan/ảnh không có text layer được ghi nhận cảnh báo và placeholder, không drop âm thầm.
4. Đoạn văn bản ngắn (< 15 ký tự) như định nghĩa, tiêu đề không bị bỏ qua.
"""

import tempfile
import unittest
from pathlib import Path
import pymupdf

from src.core.models import QARecord
from src.data.loaders.pdf_loader import PDFLoader


class TestPDFLoaderFixes(unittest.TestCase):
    """Kiểm thử các trường hợp biên của PDFLoader."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_pdf_loader_"))
        self.loader = PDFLoader()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_oxford_filename_not_routed_to_oxford_parser(self):
        """Tài liệu có chữ 'oxford' trong tên nhưng không phải từ vựng Oxford 3000 phải parse bình thường."""
        pdf_path = self.temp_dir / "oxford_university_research_summary.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        page.insert_text(
            (50, 100),
            "This is a general research paper about modern computer science from Oxford authors.\n"
            "Machine Learning: A subfield of artificial intelligence focusing on data patterns."
        )
        doc.save(str(pdf_path))
        doc.close()

        records = self.loader.load(pdf_path)
        self.assertTrue(len(records) >= 1)
        # Nguồn gốc phải giữ đúng tên tệp
        self.assertEqual(records[0].source, "oxford_university_research_summary.pdf")
        # Phải chứa nội dung trích xuất
        combined_text = " ".join(r.answer for r in records)
        self.assertIn("computer science", combined_text)

    def test_multicolumn_reading_order(self):
        """PDF dàn 2 cột phải được đọc theo cột 1 trước, sau đó đến cột 2."""
        pdf_path = self.temp_dir / "two_column_document.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)

        # Cột trái (x = 50, mid = 300)
        page.insert_text((50, 100), "Column1_Top: History of computing.")
        page.insert_text((50, 250), "Column1_Bottom: Era of microprocessors.")

        # Cột phải (x = 350)
        page.insert_text((350, 100), "Column2_Top: Growth of the Internet.")
        page.insert_text((350, 250), "Column2_Bottom: Modern AI applications.")

        doc.save(str(pdf_path))
        doc.close()

        pages_extracted = self.loader._extract_text_by_pages(pdf_path)
        self.assertEqual(len(pages_extracted), 1)
        extracted_text = pages_extracted[0][1]

        # Vị trí xuất hiện của các chuỗi trong văn bản trích xuất
        idx_c1_top = extracted_text.find("Column1_Top")
        idx_c1_bot = extracted_text.find("Column1_Bottom")
        idx_c2_top = extracted_text.find("Column2_Top")
        idx_c2_bot = extracted_text.find("Column2_Bottom")

        # Thứ tự đúng: Cột 1 Đầu -> Cột 1 Cuối -> Cột 2 Đầu -> Cột 2 Cuối
        self.assertNotEqual(idx_c1_top, -1)
        self.assertNotEqual(idx_c1_bot, -1)
        self.assertNotEqual(idx_c2_top, -1)
        self.assertNotEqual(idx_c2_bot, -1)

        self.assertLess(idx_c1_top, idx_c1_bot)
        self.assertLess(idx_c1_bot, idx_c2_top)
        self.assertLess(idx_c2_top, idx_c2_bot)

    def test_scanned_page_not_silently_dropped_in_mixed_pdf(self):
        """PDF hỗn hợp (trang 1 có text, trang 2 scan/trống) không được bỏ qua âm thầm trang 2."""
        pdf_path = self.temp_dir / "mixed_document.pdf"
        doc = pymupdf.open()
        p1 = doc.new_page(width=600, height=800)
        p1.insert_text((50, 100), "Page 1 general text content.")

        # Trang 2 trống (mô phỏng trang scan không có text layer)
        p2 = doc.new_page(width=600, height=800)

        doc.save(str(pdf_path))
        doc.close()

        records = self.loader.load(pdf_path)
        sheets = [r.sheet for r in records]

        # Cả Trang 1 và Trang 2 đều phải có mặt trong kết quả
        self.assertIn("Trang 1", sheets)
        self.assertIn("Trang 2", sheets)

        p2_records = [r for r in records if r.sheet == "Trang 2"]
        self.assertTrue(any("scan/hình ảnh" in r.answer for r in p2_records))

    def test_short_text_and_tables_preserved(self):
        """Các đoạn văn bản ngắn (< 15 ký tự) không bị bỏ qua."""
        pdf_path = self.temp_dir / "short_text_doc.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        page.insert_text((50, 100), "AI: Tri tue NT\nML: May hoc\nDL: Hoc sau\n")
        doc.save(str(pdf_path))
        doc.close()

        records = self.loader.load(pdf_path)
        answers = [r.answer for r in records]
        # Tất cả các định nghĩa ngắn đều phải được giữ lại
        self.assertTrue(any("Tri tue NT" in a for a in answers))
        self.assertTrue(any("May hoc" in a for a in answers))
        self.assertTrue(any("Hoc sau" in a for a in answers))


if __name__ == "__main__":
    unittest.main()
