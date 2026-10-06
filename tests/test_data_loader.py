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


if __name__ == "__main__":
    unittest.main()
