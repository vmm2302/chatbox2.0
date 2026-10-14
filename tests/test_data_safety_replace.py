"""Kiểm thử an toàn dữ liệu trong chế độ REPLACE (REPLACE Data Safety Test Suite).

Kiểm tra:
1. Khi nạp với mode="replace" mà toàn bộ tệp đầu vào bị hỏng/lỗi extraction:
   - Dữ liệu cũ trong qa_records.jsonl và sources_manifest.json KHÔNG bị xóa.
   - Vector collection không bị xóa hay ghi đè thành rỗng.
   - Trạng thái trả về FAILED kèm lý do bảo toàn dữ liệu.
2. Khi nạp với mode="replace" có tệp hợp lệ:
   - Dữ liệu staging được kiểm tra trước khi chuyển sang thay thế dữ liệu cũ.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader


class TestDataSafetyReplace(unittest.TestCase):
    """Kiểm thử cơ chế Staging và Safety Gate khi chạy ingest_batch với mode='replace'."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_safety_replace_"))
        self.processed_dir = self.test_dir / "data" / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.processed_dir / "qa_records.jsonl"
        self.manifest_path = self.processed_dir / "sources_manifest.json"

        # Khởi tạo 3 bản ghi ban đầu trong kho tri thức
        self.initial_records = [
            QARecord(
                record_id="REC_init_001",
                word="apple",
                sheet="A1",
                source="init.xlsx",
                level="A1",
                question="apple nghĩa là gì?",
                answer="quả táo",
                normalized_question="apple nghia la gi?"
            ),
            QARecord(
                record_id="REC_init_002",
                word="banana",
                sheet="A1",
                source="init.xlsx",
                level="A1",
                question="banana nghĩa là gì?",
                answer="quả chuối",
                normalized_question="banana nghia la gi?"
            ),
            QARecord(
                record_id="REC_init_003",
                word="cat",
                sheet="A1",
                source="init.xlsx",
                level="A1",
                question="cat nghĩa là gì?",
                answer="con mèo",
                normalized_question="cat nghia la gi?"
            ),
        ]
        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        loader.save_to_jsonl(self.initial_records)

        # Khởi tạo manifest ban đầu
        initial_manifest = {
            "version": "2.0",
            "last_updated": "2026-10-15T00:00:00Z",
            "total_sources": 1,
            "sources": {
                "SRC_init123": {
                    "source_id": "SRC_init123",
                    "file_name": "init.xlsx",
                    "file_hash": "hash_init_123",
                    "status": "ACTIVE",
                    "record_count": 3,
                    "record_ids": ["REC_init_001", "REC_init_002", "REC_init_003"],
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(initial_manifest, f)

        self.manager = BatchIngestionManager(loader=loader, manifest_path=self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_replace_aborted_when_all_files_fail(self, mock_bm25, mock_bge_cls):
        """Khi mode='replace' và tất cả tệp đầu vào lỗi: DB cũ phải được bảo toàn 100%."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 3
        mock_bge_cls.return_value = mock_retriever

        # Tạo 2 tệp rỗng / lỗi
        bad_file1 = self.test_dir / "corrupted_1.txt"
        bad_file1.write_text("", encoding="utf-8")  # Rỗng

        bad_file2 = self.test_dir / "corrupted_2.pdf"
        bad_file2.write_bytes(b"%PDF-corrupted-bytes-without-valid-structure")

        report = self.manager.ingest_batch(
            files=[bad_file1, bad_file2],
            mode="replace"
        )

        # Báo cáo phải là FAILED
        self.assertEqual(report.batch_status, BatchStatus.FAILED)
        self.assertEqual(report.success_count, 0)
        self.assertEqual(report.chromadb_status, "UNCHANGED (REPLACE ABORTED)")

        # Verify: build_or_load_collection(force_reindex=True) TUYỆT ĐỐI KHÔNG ĐƯỢC GỌI
        mock_retriever.build_or_load_collection.assert_not_called()

        # Dữ liệu cũ trong qa_records.jsonl vẫn còn nguyên 3 bản ghi
        recs_after = self.manager.loader.load_from_jsonl()
        self.assertEqual(len(recs_after), 3)
        self.assertEqual(recs_after[0].word, "apple")

        # Manifest vẫn còn nguyên nguồn ban đầu
        manifest_after = self.manager.load_manifest()
        self.assertIn("SRC_init123", manifest_after.get("sources", {}))

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_replace_succeeds_when_input_valid(self, mock_bm25, mock_bge_cls):
        """Khi mode='replace' và tệp đầu vào hợp lệ: thay thế dữ liệu cũ an toàn."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock()]

        valid_file = self.test_dir / "valid_new.txt"
        valid_file.write_text("dog: con chó trung thành\n", encoding="utf-8")

        report = self.manager.ingest_batch(
            files=[valid_file],
            mode="replace"
        )

        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(report.success_count, 1)

        # Vector DB đã được rebuild với dữ liệu mới
        mock_retriever.build_or_load_collection.assert_called_with(force_reindex=True)

        # JSONL được cập nhật thành bản ghi mới
        recs_after = self.manager.loader.load_from_jsonl()
        self.assertEqual(len(recs_after), 1)
        self.assertEqual(recs_after[0].word, "dog")


if __name__ == "__main__":
    unittest.main()
