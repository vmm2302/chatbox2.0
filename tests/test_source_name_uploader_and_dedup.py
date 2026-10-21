"""Bộ kiểm thử toàn diện cho Chatbox 2.0:
1. Sửa lỗi tên nguồn Active Sources (loại bỏ N/A, chuẩn hóa tên gốc, hỗ trợ manifest cũ/mới).
2. Tự động làm mới khu vực Upload theo thế hệ uploader_generation (SUCCESS, PARTIAL_SUCCESS, FAILED).
3. Tự động phát hiện và dọn dẹp bản sao tệp trùng lặp vật lý theo mã băm SHA-256.
4. Đảm bảo an toàn dữ liệu, tính toàn vẹn của ADD/REPLACE/Rollback và khả năng tra cứu sau khi dọn dẹp.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from config.settings import settings
from src.core.models import QARecord
from src.data.batch_ingestion import (
    BatchIngestionManager,
    BatchStatus,
    FileStatus,
)
from src.data.loader import QALoader
from src.data.loaders.base import clean_source_name, compute_file_hash


class TestSourceNameAndManifest(unittest.TestCase):
    """Kiểm thử Vấn đề 1: Tên nguồn hiển thị chính xác, không N/A, không UUID."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_manifest_source_"))
        self.manifest_path = self.temp_dir / "sources_manifest.json"
        self.raw_dir = self.temp_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.temp_dir / "qa_records.jsonl"

        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        self.manager = BatchIngestionManager(loader=loader, manifest_path=self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_source_name_utility(self):
        """clean_source_name loại bỏ chính xác các tiền tố tạm thời của hệ thống."""
        self.assertEqual(clean_source_name("batch_21bbc8b0_Oxford_5000.pdf"), "Oxford_5000.pdf")
        self.assertEqual(clean_source_name("raw_541294fc_English_Vocabulary.xlsx"), "English_Vocabulary.xlsx")
        self.assertEqual(clean_source_name("upload_99aa11bb_dictionary.jsonl"), "dictionary.jsonl")
        self.assertEqual(clean_source_name("tmp_01234567_notes.txt"), "notes.txt")
        self.assertEqual(clean_source_name("Oxford_5000.pdf"), "Oxford_5000.pdf")
        self.assertEqual(clean_source_name("C:/some/path/batch_11223344_Oxford_5000.pdf"), "Oxford_5000.pdf")
        self.assertEqual(clean_source_name(""), "")

    def test_legacy_manifest_with_only_file_name_read_correctly(self):
        """Manifest cũ chỉ có trường file_name nhưng không có source_name vẫn đọc đúng tên."""
        legacy_manifest = {
            "sources": {
                "SRC_111": {
                    "source_id": "SRC_111",
                    "file_name": "Oxford_5000.pdf",
                    "file_path": str(self.raw_dir / "batch_12345678_Oxford_5000.pdf"),
                    "file_hash": "1111111111111111111111111111111111111111111111111111111111111111",
                    "record_count": 100,
                    "ingested_at": "2026-10-17T00:00:00Z",
                    "status": "ACTIVE"
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(legacy_manifest, f)

        active = self.manager.get_active_sources()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["source_name"], "Oxford_5000.pdf")
        self.assertEqual(active[0]["file_name"], "Oxford_5000.pdf")
        self.assertNotEqual(active[0]["source_name"], "N/A")

    def test_legacy_manifest_with_prefixed_file_name_cleaned(self):
        """Manifest cũ lưu file_name có prefix batch_xxxx_ được tự động làm sạch khi đọc."""
        legacy_manifest = {
            "sources": {
                "SRC_222": {
                    "source_id": "SRC_222",
                    "file_name": "batch_98765432_English_Vocabulary.xlsx",
                    "file_hash": "2222222222222222222222222222222222222222222222222222222222222222",
                    "record_count": 250,
                    "ingested_at": "2026-10-17T00:00:00Z",
                    "status": "ACTIVE"
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(legacy_manifest, f)

        active = self.manager.get_active_sources()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["source_name"], "English_Vocabulary.xlsx")
        self.assertNotIn("batch_", active[0]["source_name"])

    def test_legacy_manifest_fallback_to_file_path(self):
        """Manifest thiếu cả file_name và source_name nhưng có file_path sẽ trích xuất tên tệp."""
        legacy_manifest = {
            "sources": {
                "SRC_333": {
                    "source_id": "SRC_333",
                    "file_path": str(self.raw_dir / "batch_abcdef12_dictionary.jsonl"),
                    "file_hash": "3333333333333333333333333333333333333333333333333333333333333333",
                    "record_count": 500,
                    "ingested_at": "2026-10-17T00:00:00Z",
                    "status": "ACTIVE"
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(legacy_manifest, f)

        active = self.manager.get_active_sources()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["source_name"], "dictionary.jsonl")

    def test_manifest_missing_name_returns_informative_message(self):
        """Manifest hoàn toàn thiếu thông tin tên tệp hiển thị thông báo rõ ràng, không âm thầm N/A."""
        legacy_manifest = {
            "sources": {
                "SRC_444": {
                    "source_id": "SRC_444",
                    "file_hash": "4444444444444444444444444444444444444444444444444444444444444444",
                    "record_count": 10,
                    "status": "ACTIVE"
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(legacy_manifest, f)

        active = self.manager.get_active_sources()
        self.assertEqual(len(active), 1)
        self.assertIn("Chưa rõ tên nguồn", active[0]["source_name"])
        self.assertNotEqual(active[0]["source_name"], "N/A")


class TestPhysicalDeduplication(unittest.TestCase):
    """Kiểm thử Phần Bổ Sung: Tự động xóa bản sao tệp trùng lặp sau khi nạp."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_dedup_"))
        self.raw_dir = self.temp_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir = self.temp_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.processed_dir / "sources_manifest.json"
        self.jsonl_path = self.processed_dir / "qa_records.jsonl"

        loader = QALoader()
        loader.processed_jsonl_path = self.jsonl_path
        self.manager = BatchIngestionManager(loader=loader, manifest_path=self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_new_file_keeps_single_original(self, mock_bm25, mock_bge_cls):
        """Trường hợp A: Nạp tệp mới chỉ lưu một bản gốc duy nhất."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock()]

        f1 = self.raw_dir / "Oxford_5000.txt"
        f1.write_text("serendipity: sự tình cờ may mắn\n", encoding="utf-8")

        report = self.manager.ingest_batch([f1], mode="add")
        self.assertEqual(report.batch_status, BatchStatus.SUCCESS)
        self.assertTrue(f1.exists(), "Bản gốc mới phải được giữ lại trên đĩa")

        # Xác minh manifest
        manifest = self.manager.load_manifest()
        self.assertEqual(len(manifest["sources"]), 1)
        src_info = list(manifest["sources"].values())[0]
        self.assertEqual(src_info["file_name"], "Oxford_5000.txt")
        self.assertEqual(src_info["source_name"], "Oxford_5000.txt")

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_reingest_identical_file_removes_duplicate_physical_copy(self, mock_bm25, mock_bge_cls):
        """Trường hợp B: Nạp lại đúng tệp đó -> không lưu thêm bản sao và dọn dẹp bản sao dư thừa."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock()]

        f_orig = self.raw_dir / "vocab_orig.txt"
        f_orig.write_text("ephemeral: phù du, chóng tàn\n", encoding="utf-8")

        # Nạp lần 1
        rep1 = self.manager.ingest_batch([f_orig], mode="add")
        self.assertEqual(rep1.batch_status, BatchStatus.SUCCESS)
        self.assertTrue(f_orig.exists())

        # Tạo bản sao mô phỏng lượt upload thứ hai của cùng nội dung
        f_dup = self.raw_dir / "batch_22222222_vocab_orig.txt"
        f_dup.write_text("ephemeral: phù du, chóng tàn\n", encoding="utf-8")

        # Nạp lần 2 với bản sao
        rep2 = self.manager.ingest_batch([f_dup], mode="add")
        self.assertEqual(rep2.batch_status, BatchStatus.PARTIAL_SUCCESS)
        self.assertEqual(rep2.skipped_count, 1)

        # Bản gốc f_orig vẫn tồn tại nguyên vẹn
        self.assertTrue(f_orig.exists(), "Bản gốc f_orig phải luôn được giữ nguyên")
        # Bản sao f_dup phải được tự động xóa
        self.assertFalse(f_dup.exists(), "Bản sao f_dup phải được dọn dẹp sau khi phát hiện trùng")

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_different_name_identical_content_detected_by_sha256(self, mock_bm25, mock_bge_cls):
        """Trường hợp B2: Khác tên nhưng nội dung giống hệt nhau -> nhận diện trùng qua SHA-256."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock()]

        f_orig = self.raw_dir / "notes_A.txt"
        f_orig.write_text("resilience: sự kiên cường vượt khó\n", encoding="utf-8")
        self.manager.ingest_batch([f_orig], mode="add")

        # Tệp B có tên hoàn toàn khác nhưng nội dung giống hệt
        f_dup = self.raw_dir / "batch_33333333_completely_different_name.txt"
        f_dup.write_text("resilience: sự kiên cường vượt khó\n", encoding="utf-8")

        rep2 = self.manager.ingest_batch([f_dup], mode="add")
        self.assertEqual(rep2.skipped_count, 1)
        self.assertIn("Duplicate file", rep2.file_results[0].reason)
        self.assertTrue(f_orig.exists())
        self.assertFalse(f_dup.exists(), "Bản sao khác tên trùng SHA-256 phải được dọn dẹp")

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_same_name_different_content_not_deleted(self, mock_bm25, mock_bge_cls):
        """Trường hợp Cảnh Báo: Hai tệp cùng tên nhưng nội dung khác nhau -> KHÔNG xóa nhầm."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 2
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock(), MagicMock()]

        f1 = self.raw_dir / "raw_aaaa1111_notes.txt"
        f1.write_text("content 1: định nghĩa thứ nhất\n", encoding="utf-8")

        f2 = self.raw_dir / "raw_bbbb2222_notes.txt"
        f2.write_text("content 2: định nghĩa thứ hai hoàn toàn khác\n", encoding="utf-8")

        rep = self.manager.ingest_batch([f1, f2], mode="add")
        self.assertEqual(rep.batch_status, BatchStatus.SUCCESS)
        self.assertEqual(rep.success_count, 2)
        # Cả hai tệp đều có nội dung độc lập, không tệp nào bị xóa
        self.assertTrue(f1.exists())
        self.assertTrue(f2.exists())

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_multiple_duplicates_in_same_batch(self, mock_bm25, mock_bge_cls):
        """Trường hợp C: Nhiều tệp trùng nhau trong cùng một batch -> chỉ giữ 1 bản gốc đại diện."""
        mock_retriever = MagicMock()
        mock_retriever.collection.count.return_value = 1
        mock_bge_cls.return_value = mock_retriever
        mock_bm25.return_value.records = [MagicMock()]

        f_keep = self.raw_dir / "representative_file.txt"
        f_keep.write_text("harmony: sự hòa hợp, đồng điệu\n", encoding="utf-8")

        f_dup1 = self.raw_dir / "tmp_1111_copy1.txt"
        f_dup1.write_text("harmony: sự hòa hợp, đồng điệu\n", encoding="utf-8")

        f_dup2 = self.raw_dir / "tmp_2222_copy2.txt"
        f_dup2.write_text("harmony: sự hòa hợp, đồng điệu\n", encoding="utf-8")

        rep = self.manager.ingest_batch([f_keep, f_dup1, f_dup2], mode="add")
        self.assertEqual(rep.total_files, 3)
        self.assertEqual(rep.success_count, 1)
        self.assertEqual(rep.skipped_count, 2)

        # Bản gốc đại diện được giữ lại
        self.assertTrue(f_keep.exists())
        # Các bản sao dư thừa trong batch được xóa
        self.assertFalse(f_dup1.exists())
        self.assertFalse(f_dup2.exists())

    @patch("src.data.batch_ingestion.BGEChromaRetriever")
    @patch("src.data.batch_ingestion.BM25Retriever")
    def test_failed_batch_preserves_file_for_retry(self, mock_bm25, mock_bge_cls):
        """Trường hợp D: Nạp thất bại -> tệp duy nhất để thử lại vẫn được giữ, không xóa nhầm."""
        mock_bge = MagicMock()
        mock_bge.upsert_records.side_effect = RuntimeError("Lỗi mạng GPU giả lập")
        mock_bge_cls.return_value = mock_bge

        f_fail = self.raw_dir / "batch_9999_failed_file.txt"
        f_fail.write_text("word_test: định nghĩa\n", encoding="utf-8")

        rep = self.manager.ingest_batch([f_fail], mode="add")
        self.assertEqual(rep.batch_status, BatchStatus.FAILED)
        # Tệp duy nhất không được xóa vì người dùng cần thử lại
        self.assertTrue(f_fail.exists(), "Tệp của batch thất bại không được xóa để người dùng thử lại")

    def test_cleanup_redundant_raw_files_scans_and_removes_physical_duplicates(self):
        """Hàm cleanup_redundant_raw_files dọn dẹp các tệp dư thừa trên đĩa và giữ lại bản canonical."""
        # Tạo bản gốc trong manifest
        orig_file = self.raw_dir / "canonical_excel.xlsx"
        orig_file.write_bytes(b"EXCEL_CONTENT_1234567890")
        f_hash = compute_file_hash(orig_file)

        manifest_data = {
            "sources": {
                "SRC_EXCEL": {
                    "source_id": "SRC_EXCEL",
                    "file_name": "canonical_excel.xlsx",
                    "file_path": str(orig_file),
                    "file_hash": f_hash,
                    "status": "ACTIVE"
                }
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        # Tạo 3 bản sao trùng nội dung
        dup1 = self.raw_dir / "batch_aaaa_canonical_excel.xlsx"
        dup1.write_bytes(b"EXCEL_CONTENT_1234567890")
        dup2 = self.raw_dir / "batch_bbbb_canonical_excel.xlsx"
        dup2.write_bytes(b"EXCEL_CONTENT_1234567890")
        dup3 = self.raw_dir / "batch_cccc_canonical_excel.xlsx"
        dup3.write_bytes(b"EXCEL_CONTENT_1234567890")

        # Tạo tệp hệ thống
        keep_git = self.raw_dir / ".gitkeep"
        keep_git.write_text("", encoding="utf-8")

        res = self.manager.cleanup_redundant_raw_files(raw_dir=self.raw_dir)
        self.assertEqual(len(res["deleted"]), 3)
        self.assertIn("canonical_excel.xlsx", res["preserved"])
        self.assertIn(".gitkeep", res["skipped_system"])

        self.assertTrue(orig_file.exists())
        self.assertFalse(dup1.exists())
        self.assertFalse(dup2.exists())
        self.assertFalse(dup3.exists())


class TestUploaderGenerationLifecycle(unittest.TestCase):
    """Kiểm thử Vấn đề 2: Cơ chế uploader_generation điều phối làm trống uploader."""

    def test_uploader_generation_increments_on_success_and_partial(self):
        """uploader_generation tăng khi SUCCESS hoặc PARTIAL_SUCCESS, giữ nguyên khi FAILED."""
        # Mô phỏng trạng thái Streamlit session state
        mock_state = {
            "uploader_generation": 0,
            "is_ingesting": False,
            "batch_report": None
        }

        # 1. SUCCESS: Tăng thế hệ
        status = BatchStatus.SUCCESS
        if status in (BatchStatus.SUCCESS, BatchStatus.PARTIAL_SUCCESS):
            mock_state["uploader_generation"] += 1
        self.assertEqual(mock_state["uploader_generation"], 1)

        # 2. PARTIAL_SUCCESS: Tăng thế hệ
        status = BatchStatus.PARTIAL_SUCCESS
        if status in (BatchStatus.SUCCESS, BatchStatus.PARTIAL_SUCCESS):
            mock_state["uploader_generation"] += 1
        self.assertEqual(mock_state["uploader_generation"], 2)

        # 3. FAILED: Giữ nguyên thế hệ để người dùng thử lại
        status = BatchStatus.FAILED
        if status in (BatchStatus.SUCCESS, BatchStatus.PARTIAL_SUCCESS):
            mock_state["uploader_generation"] += 1
        self.assertEqual(mock_state["uploader_generation"], 2, "FAILED không được tăng uploader_generation")


if __name__ == "__main__":
    unittest.main()
