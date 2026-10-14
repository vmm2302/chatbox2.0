"""Kiểm thử xử lý tải lên nhiều tệp trùng tên gốc (Identical Filenames Upload Test Suite).

Kiểm tra:
1. Hai tệp cùng có tên gốc là 'notes.txt' nhưng có nội dung khác nhau được lưu an toàn không đè lên nhau.
2. Batch Ingestion nhận diện chính xác 2 nguồn độc lập với hash khác nhau.
3. Metadata hiển thị (file_name trong manifest và source trong QARecord) giữ nguyên tên gốc 'notes.txt'.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader


class TestUploadIdenticalFilenames(unittest.TestCase):
    """Kiểm thử tính an toàn khi nạp nhiều tệp có cùng tên gốc."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_identical_names_"))
        self.raw_dir = self.temp_dir / "data" / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir = self.temp_dir / "data" / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.processed_dir / "qa_records.jsonl"
        self.manifest_path = self.processed_dir / "sources_manifest.json"

        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        self.manager = BatchIngestionManager(loader=loader, manifest_path=self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_two_files_with_identical_original_names_processed_independently(self, mock_bm25, mock_bge_cls):
        """Hai tệp cùng tên 'notes.txt' với nội dung khác nhau không bị ghi đè và đều nạp thành công."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 2
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock(), MagicMock()]

        # Mô phỏng việc Streamlit lưu tệp với prefix UUID an toàn
        file1 = self.raw_dir / "batch_1111aaaa_notes.txt"
        file1.write_text("sun: mặt trời ấm áp\n", encoding="utf-8")

        file2 = self.raw_dir / "batch_2222bbbb_notes.txt"
        file2.write_text("moon: mặt trăng sáng ngời\n", encoding="utf-8")

        report = self.manager.ingest_batch(files=[file1, file2], mode="add")

        # Cả 2 tệp đều phải thành công
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(report.success_count, 2)
        self.assertEqual(report.total_records_added, 2)

        # Kiểm tra metadata hiển thị trong kết quả
        self.assertEqual(report.file_results[0].file_name, "notes.txt")
        self.assertEqual(report.file_results[1].file_name, "notes.txt")
        self.assertNotEqual(report.file_results[0].file_hash, report.file_results[1].file_hash)

        # Kiểm tra bản ghi lưu trong JSONL
        records = self.manager.loader.load_from_jsonl()
        self.assertEqual(len(records), 2)
        words = {r.word for r in records}
        self.assertIn("sun", words)
        self.assertIn("moon", words)

        # Cả hai bản ghi đều có source chuẩn hóa là 'notes.txt'
        for r in records:
            self.assertEqual(r.source, "notes.txt")

        # Manifest lưu trữ 2 nguồn riêng biệt với cùng file_name nhưng khác hash
        manifest = self.manager.load_manifest()
        sources = manifest.get("sources", {})
        self.assertEqual(len(sources), 2)
        for sinfo in sources.values():
            self.assertEqual(sinfo.get("file_name"), "notes.txt")


if __name__ == "__main__":
    unittest.main()
