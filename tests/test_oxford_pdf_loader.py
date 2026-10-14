"""Unit test cho Module OxfordPDFParser và tích hợp PDFLoader."""

import unittest
from pathlib import Path

from config.settings import settings
from src.data.loaders.oxford_pdf_loader import OxfordPDFParser
from src.data.loaders.pdf_loader import PDFLoader


class TestOxfordPDFLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = settings.OXFORD_PDF_PATH
        if not cls.pdf_path.exists():
            raise unittest.SkipTest(f"Không tìm thấy file Oxford PDF tại {cls.pdf_path}")

    def test_parse_oxford_entries_structure(self):
        """Kiểm tra bóc tách các mục từ vựng và cấp độ CEFR."""
        entries = OxfordPDFParser.parse_oxford_entries(self.pdf_path)
        self.assertGreater(len(entries), 3000)

        # Kiểm tra sự hiện diện của đủ 4 cấp độ
        levels = set(e["level"] for e in entries)
        self.assertIn("A1", levels)
        self.assertIn("A2", levels)
        self.assertIn("B1", levels)
        self.assertIn("B2", levels)

        # Đảm bảo không có mục nào từ bị rỗng
        for e in entries:
            self.assertTrue(len(e["clean_word"]) > 0)
            self.assertTrue(len(e["base_word"]) > 0)

    def test_pdf_loader_smart_routing(self):
        """Kiểm tra PDFLoader tự động nhận diện tài liệu Oxford và gọi OxfordPDFParser."""
        loader = PDFLoader()
        records = loader.load(self.pdf_path)
        self.assertGreater(len(records), 3000)

        # Đảm bảo các bản ghi có câu hỏi và câu trả lời hợp lệ
        first = records[0]
        self.assertIn("nghĩa là gì?", first.question)
        self.assertIn("Trình độ:", first.answer)
        self.assertEqual(first.source, self.pdf_path.name)


if __name__ == "__main__":
    unittest.main()
