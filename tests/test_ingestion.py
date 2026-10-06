"""Bộ kiểm thử đơn vị cho hệ thống nạp dữ liệu Excel (Ingestion Tests)."""

import sys
import unittest
from pathlib import Path

# Đảm bảo đường dẫn gốc
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.models import QARecord
from src.data.ingestion_manager import IngestionManager
from src.data.loader import QALoader


class TestExcelIngestion(unittest.TestCase):
    """Kiểm thử tính năng kiểm tra, trích xuất và hợp nhất dữ liệu từ Excel."""

    def setUp(self):
        self.manager = IngestionManager()
        self.sample_excel = project_root / "data" / "mau_nhap_lieu_tuvung.xlsx"

    def test_inspect_valid_excel(self):
        """Kiểm tra đọc siêu dữ liệu tệp Excel hợp lệ."""
        res = self.manager.inspect_excel(self.sample_excel)
        self.assertTrue(res["valid"])
        self.assertIn("TuVungMau", res["sheets"])
        self.assertGreaterEqual(res["estimated_rows"], 3)

    def test_inspect_invalid_excel(self):
        """Kiểm tra từ chối khi tệp không tồn tại."""
        res = self.manager.inspect_excel(Path("khong_ton_tai.xlsx"))
        self.assertFalse(res["valid"])
        self.assertIn("Không tìm thấy", res["error"])

    def test_detect_column_mapping_vietnamese(self):
        """Kiểm tra nhận diện tiêu đề cột tiếng Việt."""
        headers = ["Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
        col_map = QALoader._detect_column_mapping(headers)
        self.assertIsNotNone(col_map)
        self.assertEqual(col_map["word"], 0)
        self.assertEqual(col_map["question"], 1)
        self.assertEqual(col_map["answer"], 2)
        self.assertEqual(col_map["level"], 3)
        self.assertEqual(col_map["source"], 4)

    def test_detect_column_mapping_english(self):
        """Kiểm tra nhận diện tiêu đề cột tiếng Anh."""
        headers = ["Vocab", "Question", "Answer", "Level", "Source"]
        col_map = QALoader._detect_column_mapping(headers)
        self.assertIsNotNone(col_map)
        self.assertEqual(col_map["word"], 0)
        self.assertEqual(col_map["question"], 1)
        self.assertEqual(col_map["answer"], 2)

    def test_extract_word_and_level_fallback(self):
        """Kiểm tra trích xuất tự động từ vựng và level qua regex khi thiếu cột."""
        q = "resilient nghĩa là gì?"
        a = "Có khả năng phục hồi tốt. Trình độ: B2"
        w, lvl = QALoader._extract_word_and_level_fallback(q, a)
        self.assertEqual(w, "resilient")
        self.assertEqual(lvl, "B2")

    def test_merge_records_deduplication(self):
        """Kiểm tra tính năng loại bỏ bản ghi trùng lặp khi nạp thêm dữ liệu."""
        existing = [
            QARecord("rec_1", "abandon", "sheet1", "src", "B1", "abandon nghĩa là gì?", "Từ bỏ."),
            QARecord("rec_2", "confident", "sheet1", "src", "B1", "confident nghĩa là gì?", "Tự tin."),
        ]
        incoming = [
            # Bản ghi trùng với rec_1
            QARecord("inc_1", "abandon", "sheet_new", "src", "B1", "abandon nghĩa là gì?", "Từ bỏ."),
            # Bản ghi hoàn toàn mới
            QARecord("inc_2", "serendipity", "sheet_new", "src", "C1", "serendipity nghĩa là gì?", "Cơ duyên."),
        ]

        merged, added, dupes = QALoader.merge_records(existing, incoming)
        self.assertEqual(added, 1)
        self.assertEqual(dupes, 1)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[-1].word, "serendipity")


if __name__ == "__main__":
    unittest.main()
