"""Bộ kiểm thử 14 kịch bản bắt buộc cho chức năng:
XÓA TOÀN BỘ DỮ LIỆU KNOWLEDGE BASE (CLEAR KNOWLEDGE BASE).

Các kịch bản kiểm thử:
1. Xóa Knowledge Base có nhiều bản ghi.
2. Xóa Knowledge Base đang trống (Idempotent).
3. Xóa toàn bộ nguồn đã nạp (Manifest & Active sources).
4. Xác minh JSONL không còn bản ghi (0 dòng).
5. Xác minh ChromaDB không còn dữ liệu thuộc Knowledge Base (0 vector).
6. Xác minh BM25 không còn dữ liệu cũ (bm25 is None / 0 bản ghi).
7. Xác minh ChatEngine không thể truy xuất bản ghi đã xóa (trả về Empty KB response).
8. Xác minh Ollama và các model không bị xóa.
9. Xác minh mã nguồn, .env và .venv không bị ảnh hưởng.
10. Xác minh không thể chạy xóa đồng thời với ingestion (Reject khi busy).
11. Giả lập lỗi giữa quy trình xóa và kiểm tra rollback khôi phục dữ liệu ban đầu.
12. Khởi động lại ứng dụng và xác minh Knowledge Base vẫn trống (không tự sinh dữ liệu mẫu).
13. Nạp lại dữ liệu sau khi xóa và xác minh chatbot hoạt động bình thường.
14. Xác minh dữ liệu độc lập ngoài phạm vi xóa (dictionary_en_vi.db, .gitkeep) được giữ nguyên 100%.
"""

import io
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

# Đảm bảo môi trường offline tuyệt đối
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.chat.engine import ChatEngine
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader
from src.resource.manager import ResourceState, get_resource_manager
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever


class TestClearKnowledgeBase(unittest.TestCase):
    """Bộ kiểm thử 14 kịch bản cho chức năng Xóa Toàn Bộ Dữ Liệu Knowledge Base."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo môi trường kiểm thử cách ly tuyệt đối khỏi Knowledge Base thật."""
        cls.test_dir = PROJECT_ROOT / "temp_test_clear_kb"
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        cls.test_raw_dir = cls.test_dir / "raw"
        cls.test_processed_dir = cls.test_dir / "processed"
        cls.test_chroma_dir = cls.test_dir / "chroma_db"
        cls.test_raw_dir.mkdir(parents=True, exist_ok=True)
        cls.test_processed_dir.mkdir(parents=True, exist_ok=True)
        cls.test_chroma_dir.mkdir(parents=True, exist_ok=True)

        # Lưu cấu hình gốc
        cls.orig_raw_dir = settings.RAW_DATA_DIR
        cls.orig_raw_excel = settings.RAW_EXCEL_PATH
        cls.orig_processed_dir = settings.PROCESSED_DATA_DIR
        cls.orig_processed_jsonl = settings.PROCESSED_JSONL_PATH
        cls.orig_chroma_dir = settings.CHROMA_DIR
        cls.orig_manifest_path = settings.SOURCES_MANIFEST_PATH
        cls.orig_dict_db_path = settings.DICTIONARY_DB_PATH

        # Cấu hình chuyển hướng sang môi trường test cách ly
        cls.test_jsonl_path = cls.test_processed_dir / "qa_records.jsonl"
        cls.test_manifest_path = cls.test_processed_dir / "sources_manifest.json"
        cls.test_raw_excel = cls.test_raw_dir / "empty.xlsx"
        cls.test_dict_db = cls.test_raw_dir / "dictionary_en_vi.db"

        object.__setattr__(settings, "RAW_DATA_DIR", cls.test_raw_dir)
        object.__setattr__(settings, "RAW_EXCEL_PATH", cls.test_raw_excel)
        object.__setattr__(settings, "PROCESSED_DATA_DIR", cls.test_processed_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.test_jsonl_path)
        object.__setattr__(settings, "CHROMA_DIR", cls.test_chroma_dir)
        object.__setattr__(settings, "SOURCES_MANIFEST_PATH", cls.test_manifest_path)
        object.__setattr__(settings, "DICTIONARY_DB_PATH", cls.test_dict_db)

        cls.batch_manager = BatchIngestionManager(manifest_path=cls.test_manifest_path)

    @classmethod
    def tearDownClass(cls):
        """Khôi phục cấu hình gốc và dọn dẹp thư mục kiểm thử tạm."""
        object.__setattr__(settings, "RAW_DATA_DIR", cls.orig_raw_dir)
        object.__setattr__(settings, "RAW_EXCEL_PATH", cls.orig_raw_excel)
        object.__setattr__(settings, "PROCESSED_DATA_DIR", cls.orig_processed_dir)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", cls.orig_processed_jsonl)
        object.__setattr__(settings, "CHROMA_DIR", cls.orig_chroma_dir)
        object.__setattr__(settings, "SOURCES_MANIFEST_PATH", cls.orig_manifest_path)
        object.__setattr__(settings, "DICTIONARY_DB_PATH", cls.orig_dict_db_path)

        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _seed_test_kb(self) -> List[QARecord]:
        """Tạo sẵn bộ dữ liệu mẫu trong môi trường test cách ly."""
        records = [
            QARecord(
                record_id="REC_TEST_001",
                word="resilience",
                question="resilience nghĩa là gì?",
                answer="Khả năng phục hồi, kiên cường vượt qua khó khăn.",
                sheet="Vocab",
                source="test_source_1.txt",
                level="B2"
            ),
            QARecord(
                record_id="REC_TEST_002",
                word="ephemeral",
                question="ephemeral nghĩa là gì?",
                answer="Phù du, chóng tàn, tồn tại trong thời gian rất ngắn.",
                sheet="Vocab",
                source="test_source_1.txt",
                level="C1"
            ),
            QARecord(
                record_id="REC_TEST_003",
                word="serendipity",
                question="serendipity nghĩa là gì?",
                answer="Sự tình cờ may mắn tìm thấy điều tốt đẹp bất ngờ.",
                sheet="Vocab",
                source="test_source_2.txt",
                level="B2"
            ),
        ]
        # Lưu JSONL
        self.batch_manager.loader.save_to_jsonl(records)

        # Lưu Manifest
        manifest = {
            "sources": {
                "SRC_TEST_1": {
                    "source_id": "SRC_TEST_1",
                    "file_name": "test_source_1.txt",
                    "source_name": "test_source_1.txt",
                    "file_path": str(self.test_raw_dir / "raw_111111_test_source_1.txt"),
                    "file_hash": "hash111111",
                    "record_count": 2,
                    "record_ids": ["REC_TEST_001", "REC_TEST_002"],
                    "status": "ACTIVE",
                },
                "SRC_TEST_2": {
                    "source_id": "SRC_TEST_2",
                    "file_name": "test_source_2.txt",
                    "source_name": "test_source_2.txt",
                    "file_path": str(self.test_raw_dir / "raw_222222_test_source_2.txt"),
                    "file_hash": "hash222222",
                    "record_count": 1,
                    "record_ids": ["REC_TEST_003"],
                    "status": "ACTIVE",
                }
            }
        }
        self.batch_manager.save_manifest(manifest)

        # Tạo file raw giả lập
        (self.test_raw_dir / "raw_111111_test_source_1.txt").write_text("dummy content 1", encoding="utf-8")
        (self.test_raw_dir / "raw_222222_test_source_2.txt").write_text("dummy content 2", encoding="utf-8")

        # Nạp ChromaDB
        bge = BGEChromaRetriever(records)
        bge.build_or_load_collection(force_reindex=True)

        return records

    def test_01_clear_kb_with_multiple_records(self):
        """Kịch bản 1: Xóa Knowledge Base có nhiều bản ghi."""
        self._seed_test_kb()
        engine = ChatEngine()

        # Kiểm tra trước khi xóa: có bản ghi
        self.assertEqual(len(engine.records), 3)
        self.assertEqual(engine.bge_retriever.get_collection_count(), 3)
        self.assertEqual(len(self.batch_manager.get_active_sources()), 2)

        # Thực hiện xóa toàn bộ
        res = self.batch_manager.clear_knowledge_base(engine=engine)

        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["success"])
        self.assertEqual(res["deleted_records"], 3)
        self.assertEqual(res["deleted_sources"], 2)
        self.assertEqual(res["jsonl_count"], 0)
        self.assertEqual(res["chromadb_count"], 0)
        self.assertEqual(res["bm25_count"], 0)
        self.assertEqual(res["active_sources_count"], 0)

    def test_02_clear_empty_kb_idempotent(self):
        """Kịch bản 2: Xóa Knowledge Base đang trống (Idempotent)."""
        # Đảm bảo môi trường đang rỗng
        self.batch_manager.clear_knowledge_base()

        engine = ChatEngine()
        self.assertEqual(len(engine.records), 0)

        # Thực hiện xóa lần 2 trên KB rỗng
        res = self.batch_manager.clear_knowledge_base(engine=engine)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["success"])
        self.assertEqual(res["deleted_records"], 0)
        self.assertEqual(res["deleted_sources"], 0)
        self.assertEqual(res["jsonl_count"], 0)
        self.assertEqual(res["chromadb_count"], 0)
        self.assertEqual(res["bm25_count"], 0)

    def test_03_clear_all_ingested_sources_manifest(self):
        """Kịch bản 3: Xóa toàn bộ nguồn đã nạp (Manifest & Active sources)."""
        self._seed_test_kb()
        self.assertEqual(len(self.batch_manager.get_active_sources()), 2)

        self.batch_manager.clear_knowledge_base()

        manifest = self.batch_manager.load_manifest()
        self.assertEqual(manifest.get("sources"), {})
        self.assertEqual(len(self.batch_manager.get_active_sources()), 0)

    def test_04_verify_jsonl_empty(self):
        """Kịch bản 4: Xác minh JSONL không còn bản ghi (0 dòng)."""
        self._seed_test_kb()
        self.assertTrue(self.test_jsonl_path.exists())
        self.assertGreater(len(self.batch_manager.loader.load_from_jsonl()), 0)

        self.batch_manager.clear_knowledge_base()

        records_after = self.batch_manager.loader.load_from_jsonl()
        self.assertEqual(len(records_after), 0)

        # Đọc trực tiếp số dòng từ file
        with open(self.test_jsonl_path, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 0)

    def test_05_verify_chromadb_empty(self):
        """Kịch bản 5: Xác minh ChromaDB không còn dữ liệu thuộc Knowledge Base (0 vector)."""
        self._seed_test_kb()
        bge = BGEChromaRetriever([])
        self.assertGreater(bge.get_collection_count(), 0)

        self.batch_manager.clear_knowledge_base()

        self.assertEqual(bge.get_collection_count(), 0)
        if bge.collection:
            self.assertEqual(bge.collection.count(), 0)

    def test_06_verify_bm25_empty(self):
        """Kịch bản 6: Xác minh BM25 không còn dữ liệu cũ (bm25 is None / 0 bản ghi)."""
        self._seed_test_kb()
        engine = ChatEngine()
        self.assertIsNotNone(engine.retriever.bm25_retriever.bm25)

        self.batch_manager.clear_knowledge_base(engine=engine)

        self.assertEqual(len(engine.retriever.bm25_retriever.records), 0)
        self.assertIsNone(engine.retriever.bm25_retriever.bm25)
        # Tìm kiếm trên BM25 trả về rỗng
        bm25_res = engine.retriever.bm25_retriever.search("resilience")
        self.assertEqual(bm25_res, [])

    def test_07_verify_chatengine_cannot_retrieve_deleted_records(self):
        """Kịch bản 7: Xác minh ChatEngine không thể truy xuất bản ghi đã xóa (trả về Empty KB response)."""
        self._seed_test_kb()
        engine = ChatEngine()

        # Trước khi xóa: tra cứu từ vựng thành công
        resp_before = engine.ask("resilience nghĩa là gì?")
        self.assertIn(resp_before.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(resp_before.record_id, "REC_TEST_001")
        self.assertEqual(resp_before.word, "resilience")
        self.assertIn("phục hồi", resp_before.answer.lower())

        # Xóa KB
        self.batch_manager.clear_knowledge_base(engine=engine)

        # Sau khi xóa: hỏi lại cùng câu hỏi
        resp_after = engine.ask("resilience nghĩa là gì?")
        self.assertEqual(resp_after.mode, "NO_MATCH")
        self.assertIn(settings.EMPTY_KB_RESPONSE, resp_after.answer)

        # Stream cũng phải trả về empty KB response
        stream_chunks = list(engine.ask_stream("resilience nghĩa là gì?"))
        full_stream_text = "".join(chunk for chunk, _ in stream_chunks)
        self.assertIn(settings.EMPTY_KB_RESPONSE, full_stream_text)

    def test_08_verify_ollama_and_models_intact(self):
        """Kịch bản 8: Xác minh Ollama và các model không bị xóa."""
        self._seed_test_kb()
        self.batch_manager.clear_knowledge_base()

        # Cấu hình Ollama và Model vẫn giữ nguyên
        self.assertEqual(settings.OLLAMA_MODEL, "qwen2.5:7b")
        self.assertEqual(settings.BGE_M3_MODEL_NAME, "BAAI/bge-m3")
        self.assertEqual(settings.PHOBERT_MODEL_NAME, "vinai/phobert-base-v2")

        # Bộ điều phối model vẫn hoạt động bình thường
        rm = get_resource_manager()
        self.assertIsNotNone(rm.model_manager)

    def test_09_verify_source_code_and_configs_intact(self):
        """Kịch bản 9: Xác minh mã nguồn, .env và .venv không bị ảnh hưởng."""
        self._seed_test_kb()
        self.batch_manager.clear_knowledge_base()

        self.assertTrue((PROJECT_ROOT / "src").exists())
        self.assertTrue((PROJECT_ROOT / "config").exists())
        self.assertTrue((PROJECT_ROOT / ".venv").exists())
        self.assertTrue((PROJECT_ROOT / ".env.example").exists())
        self.assertTrue((PROJECT_ROOT / "src" / "chat" / "engine.py").exists())
        self.assertTrue((PROJECT_ROOT / "src" / "data" / "batch_ingestion.py").exists())

    def test_10_verify_cannot_clear_concurrently_with_ingestion(self):
        """Kịch bản 10: Xác minh không thể chạy xóa đồng thời với ingestion (Reject khi busy)."""
        self._seed_test_kb()
        rm = get_resource_manager()

        try:
            # Giả lập trạng thái đang nạp dữ liệu
            rm.state = ResourceState.INDEXING_CPU

            res = self.batch_manager.clear_knowledge_base()
            self.assertEqual(res["status"], "REJECTED")
            self.assertFalse(res["success"])
            self.assertIn("đang chạy", res["message"])

            # Dữ liệu KB cũ phải được bảo toàn nguyên vẹn
            records = self.batch_manager.loader.load_from_jsonl()
            self.assertEqual(len(records), 3)
        finally:
            rm.state = ResourceState.CHAT_READY

    def test_11_simulate_failure_and_verify_rollback(self):
        """Kịch bản 11: Giả lập lỗi giữa quy trình xóa và kiểm tra rollback khôi phục hoàn chỉnh."""
        self._seed_test_kb()
        engine = ChatEngine()
        self.assertEqual(len(engine.records), 3)

        # Giả lập lỗi tại bước lưu JSONL
        with patch.object(self.batch_manager.loader, "save_to_jsonl", side_effect=IOError("Simulated disk error")):
            res = self.batch_manager.clear_knowledge_base(engine=engine)

        self.assertEqual(res["status"], "FAILED")
        self.assertFalse(res["success"])

        # Rollback phải khôi phục đầy đủ dữ liệu ban đầu
        restored_records = self.batch_manager.loader.load_from_jsonl()
        self.assertEqual(len(restored_records), 3)
        self.assertEqual(engine.bge_retriever.get_collection_count(), 3)
        self.assertEqual(len(self.batch_manager.get_active_sources()), 2)

    def test_12_restart_app_preserves_empty_knowledge_base(self):
        """Kịch bản 12: Khởi động lại ứng dụng và xác minh Knowledge Base vẫn trống (không tự sinh dữ liệu mẫu)."""
        self._seed_test_kb()
        self.batch_manager.clear_knowledge_base()

        # Giả lập khởi động lại ứng dụng: khởi tạo ChatEngine mới hoàn toàn
        new_engine = ChatEngine()
        self.assertEqual(len(new_engine.records), 0)
        self.assertEqual(new_engine.bge_retriever.get_collection_count(), 0)

        # Hỏi câu hỏi trên engine mới: chatbot phải báo KB rỗng, không tự tạo dữ liệu mẫu
        resp = new_engine.ask("từ vựng resilience nghĩa là gì?")
        self.assertEqual(resp.mode, "NO_MATCH")
        self.assertIn(settings.EMPTY_KB_RESPONSE, resp.answer)

    def test_13_reingest_after_clear_operates_normally(self):
        """Kịch bản 13: Nạp lại dữ liệu sau khi xóa và xác minh chatbot hoạt động bình thường."""
        self._seed_test_kb()
        engine = ChatEngine()
        self.batch_manager.clear_knowledge_base(engine=engine)

        self.assertEqual(len(engine.records), 0)

        # Tạo tệp mới để nạp lại
        new_file = self.test_raw_dir / "reingest_test.txt"
        new_file.write_text("serendipity: Sự may mắn tình cờ.", encoding="utf-8")

        report = self.batch_manager.ingest_batch(files=[new_file], mode="add")
        self.assertIn(report.batch_status, [BatchStatus.SUCCESS, BatchStatus.PARTIAL_SUCCESS])

        # Cập nhật engine
        new_records = self.batch_manager.loader.load_from_jsonl()
        self.assertGreater(len(new_records), 0)
        engine.update_knowledge_base(new_records)

        # Chatbot hoạt động bình thường với dữ liệu mới
        with patch.object(engine.llm_client, "generate_with_langchain", return_value="Sự may mắn tình cờ."):
            resp = engine.ask("serendipity nghĩa là gì?")
            self.assertIn(resp.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
            self.assertIn("may mắn", resp.answer.lower())

    def test_14_independent_data_outside_kb_preserved(self):
        """Kịch bản 14: Xác minh dữ liệu độc lập ngoài phạm vi xóa (dictionary_en_vi.db, .gitkeep) được giữ nguyên 100%."""
        self._seed_test_kb()

        # Tạo file từ điển hệ thống và .gitkeep giả lập
        dict_file = self.test_raw_dir / "dictionary_en_vi.db"
        dict_file.write_text("SYSTEM_SQLITE_DATABASE_MOCK", encoding="utf-8")

        dict_backup = self.test_raw_dir / "dictionary_en_vi.db.backup"
        dict_backup.write_text("SYSTEM_BACKUP_MOCK", encoding="utf-8")

        gitkeep_file = self.test_raw_dir / ".gitkeep"
        gitkeep_file.write_text("# gitkeep", encoding="utf-8")

        managed_file = self.test_raw_dir / "raw_111111_test_source_1.txt"
        self.assertTrue(managed_file.exists())

        # Xóa KB
        res = self.batch_manager.clear_knowledge_base(delete_managed_raw_files=True)
        self.assertEqual(res["status"], "SUCCESS")

        # Tệp nguồn do KB quản lý bị xóa
        self.assertFalse(managed_file.exists())

        # Tệp hệ thống độc lập TUYỆT ĐỐI KHÔNG BỊ XÓA
        self.assertTrue(dict_file.exists(), "dictionary_en_vi.db KHÔNG được phép bị xóa!")
        self.assertEqual(dict_file.read_text(encoding="utf-8"), "SYSTEM_SQLITE_DATABASE_MOCK")

        self.assertTrue(dict_backup.exists(), "dictionary_en_vi.db.backup KHÔNG được phép bị xóa!")
        self.assertTrue(gitkeep_file.exists(), ".gitkeep KHÔNG được phép bị xóa!")


if __name__ == "__main__":
    unittest.main()
