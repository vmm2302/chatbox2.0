"""Unit test cho Module QALoader và hàm chuẩn hóa chuỗi."""

import tempfile
import unittest
from pathlib import Path

from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text


class TestDataLoaderModule(unittest.TestCase):
    def test_normalize_vietnamese_text(self):
        """Kiểm tra tính đúng đắn của hàm chuẩn hóa tiếng Việt."""
        self.assertEqual(normalize_vietnamese_text("Xin Chào Thế Giới!"), "xin chao the gioi")
        self.assertEqual(normalize_vietnamese_text("Đường đi, Đất nước"), "duong di dat nuoc")
        self.assertEqual(normalize_vietnamese_text("a, an nghĩa là gì?"), "a an nghia la gi")
        self.assertEqual(normalize_vietnamese_text(""), "")

    def test_qa_record_serialization(self):
        """Kiểm tra chuyển đổi đối tượng QARecord sang Dict và ngược lại."""
        record = QARecord(
            id="TEST_001",
            sheet="test_sheet",
            question="Hello nghĩa là gì?",
            answer="Xin chào",
            source="Test Dict",
            normalized_question="hello nghia la gi"
        )
        rec_dict = record.to_dict()
        self.assertEqual(rec_dict["id"], "TEST_001")
        self.assertEqual(rec_dict["question"], "Hello nghĩa là gì?")

        restored = QARecord.from_dict(rec_dict)
        self.assertEqual(restored.id, record.id)
        self.assertEqual(restored.question, record.question)
        self.assertEqual(restored.answer, record.answer)

    def test_save_and_load_jsonl(self):
        """Kiểm tra lưu và nạp tệp JSONL."""
        records = [
            QARecord(
                id="T1",
                sheet="s1",
                question="Q1",
                answer="A1",
                normalized_question="q1"
            ),
            QARecord(
                id="T2",
                sheet="s2",
                question="Q2",
                answer="A2",
                normalized_question="q2"
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            jsonl_path = Path(tmp_dir) / "test_records.jsonl"
            loader = QALoader(processed_jsonl_path=jsonl_path)
            loader.save_to_jsonl(records)

            loaded_records = loader.load_from_jsonl()
            self.assertEqual(len(loaded_records), 2)
            self.assertEqual(loaded_records[0].id, "T1")
            self.assertEqual(loaded_records[1].id, "T2")

    def test_detect_column_mapping_with_source_variations(self):
        """Kiểm tra nhận diện cột nguồn với các biến thể tiêu đề khác nhau."""
        headers_vn = ["STT", "Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
        col_map = QALoader._detect_column_mapping(headers_vn)
        self.assertIsNotNone(col_map)
        self.assertIn("source", col_map)
        self.assertEqual(col_map["source"], 5)

        headers_en = ["word", "question", "answer", "source", "level"]
        col_map_en = QALoader._detect_column_mapping(headers_en)
        self.assertIsNotNone(col_map_en)
        self.assertIn("source", col_map_en)
        self.assertEqual(col_map_en["source"], 3)

        headers_trich_nguon = ["Câu hỏi", "Câu trả lời", "Trích nguồn"]
        col_map_tn = QALoader._detect_column_mapping(headers_trich_nguon)
        self.assertIsNotNone(col_map_tn)
        self.assertIn("source", col_map_tn)
        self.assertEqual(col_map_tn["source"], 2)

    def test_parse_custom_sheet_with_and_without_source(self):
        """Kiểm tra nạp dữ liệu sheet có và không có cột nguồn."""
        loader = QALoader()

        # Trường hợp 1: Có cột nguồn rõ ràng
        rows_with_src = [
            ["Câu hỏi", "Câu trả lời", "Từ vựng", "Trình độ", "Nguồn"],
            ["about nghĩa là gì?", "Về, khoảng chừng", "about", "A1", "Oxford Learner's Dictionary"],
        ]
        recs_with_src = loader._parse_custom_sheet(rows_with_src, "Sheet1", "DefaultFile.xlsx", 0)
        self.assertEqual(len(recs_with_src), 1)
        self.assertEqual(recs_with_src[0].word, "about")
        self.assertEqual(recs_with_src[0].source, "Oxford Learner's Dictionary")

        # Trường hợp 2: Không có cột nguồn -> Fallback về source_default
        rows_no_src = [
            ["Câu hỏi", "Câu trả lời", "Từ vựng", "Trình độ"],
            ["hello nghĩa là gì?", "Xin chào", "hello", "A1"],
        ]
        recs_no_src = loader._parse_custom_sheet(rows_no_src, "Sheet1", "VocabularyBook.xlsx", 0)
        self.assertEqual(len(recs_no_src), 1)
        self.assertEqual(recs_no_src[0].source, "VocabularyBook.xlsx")


if __name__ == "__main__":
    unittest.main()
