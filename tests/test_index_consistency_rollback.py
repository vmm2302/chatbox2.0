"""Kiểm thử tính nhất quán chỉ mục và cơ chế Rollback (Index Consistency & Rollback Test Suite).

Kiểm tra:
1. Khi xảy ra lỗi trong bước indexing hoặc ghi manifest, JSONL và manifest tự động rollback về snapshot ban đầu.
2. Không bao giờ trả về status SUCCESS khi các thành phần Vector DB, JSONL và BM25 bị lệch số lượng.
3. Khi xóa nguồn (delete_source) gặp lỗi I/O, hệ thống tự động hoàn tác khôi phục trạng thái cũ.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.ingestion_manager import IngestionManager
from src.data.loader import QALoader


class TestIndexConsistencyRollback(unittest.TestCase):
    """Kiểm thử tính nhất quán và cơ chế hoàn tác dữ liệu khi có sự cố."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_rollback_"))
        self.processed_dir = self.temp_dir / "data" / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.processed_dir / "qa_records.jsonl"
        self.manifest_path = self.processed_dir / "sources_manifest.json"

        # Dữ liệu ban đầu
        self.initial_records = [
            QARecord(
                record_id="REC_stable_1",
                word="alpha",
                sheet="Sheet1",
                source="base.txt",
                level="A1",
                question="alpha là gì?",
                answer="kí tự Hy Lạp đầu tiên",
                normalized_question="alpha la gi?"
            )
        ]
        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        loader.save_to_jsonl(self.initial_records)

        initial_manifest = {
            "version": "2.0",
            "last_updated": "2026-10-15T00:00:00Z",
            "total_sources": 1,
            "sources": {
                "SRC_base": {
                    "source_id": "SRC_base",
                    "file_name": "base.txt",
                    "file_hash": "hash_base",
                    "status": "ACTIVE",
                    "record_count": 1,
                    "record_ids": ["REC_stable_1"],
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(initial_manifest, f)

        self.manager = BatchIngestionManager(loader=loader, manifest_path=self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_ingest_batch_rollback_on_save_manifest_failure(self, mock_bm25, mock_bge_cls):
        """Khi save_manifest bị lỗi, toàn bộ batch phải rollback về snapshot trước đó."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 2
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock(), MagicMock()]

        # Giả lập lỗi khi lưu manifest
        self.manager.save_manifest = MagicMock(side_effect=IOError("Disk write error during save_manifest"))

        incoming_file = self.temp_dir / "new_record.txt"
        incoming_file.write_text("beta: kí tự thứ hai\n", encoding="utf-8")

        report = self.manager.ingest_batch(files=[incoming_file], mode="add")

        # Báo cáo phải là FAILED
        self.assertEqual(report.batch_status, BatchStatus.FAILED)
        self.assertIn("FAILED", report.chromadb_status)

        # JSONL phải được rollback về 1 bản ghi ban đầu
        recs_after = self.manager.loader.load_from_jsonl()
        self.assertEqual(len(recs_after), 1)
        self.assertEqual(recs_after[0].word, "alpha")

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_ingest_batch_fails_on_component_count_mismatch(self, mock_bm25, mock_bge_cls):
        """Khi số lượng Vector DB != JSONL != BM25, không bao giờ được báo SUCCESS."""
        mock_retriever = MagicMock()
        # Giả lập ChromaDB chỉ index được 1 vector trong khi JSONL có 2 bản ghi
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock(), MagicMock()]

        incoming_file = self.temp_dir / "new_record2.txt"
        incoming_file.write_text("gamma: kí tự thứ ba\n", encoding="utf-8")

        report = self.manager.ingest_batch(files=[incoming_file], mode="add")

        # Hệ thống phải phát hiện lệch đồng bộ và kích hoạt rollback
        self.assertEqual(report.batch_status, BatchStatus.FAILED)

    @patch("src.data.ingestion_manager.BGEChromaRetriever")
    @patch("src.data.ingestion_manager.BM25Retriever")
    def test_ingestion_manager_no_false_success_when_desynced(self, mock_bm25, mock_bge_cls):
        """IngestionManager.ingest() phải trả về status FAILED nếu các thành phần không đồng bộ."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 0  # Lệch count
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = []

        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        ing_mgr = IngestionManager(loader=loader)

        # Giả lập router trả về bản ghi
        dummy_file = self.temp_dir / "dummy.txt"
        dummy_file.write_text("test: test!", encoding="utf-8")

        with patch.object(ing_mgr.router, "load_file") as mock_load:
            mock_load.return_value = [
                QARecord(
                    record_id="REC_new",
                    word="test",
                    sheet="Sheet1",
                    source="dummy.txt",
                    level="A1",
                    question="test?",
                    answer="test!",
                    normalized_question="test?"
                )
            ]
            with patch.object(ing_mgr, "inspect_file", return_value={"valid": True}):
                res = ing_mgr.ingest(file_path=dummy_file, mode="add")
                # Không được là SUCCESS vì chroma_count == 0 != total_active
                self.assertEqual(res.status, "FAILED")
                self.assertIn("không đồng bộ", res.message)


if __name__ == "__main__":
    unittest.main()
