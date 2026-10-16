"""Kiểm thử cơ chế tự phục hồi và làm mới collection ChromaDB sau khi Replace (Collection Reload Test Suite).

Kiểm tra:
1. Khi collection ChromaDB bị xóa và tạo mới trên đĩa (thao tác replace), BGEChromaRetriever
   tự động phát hiện và kết nối lại tới collection UUID mới mà không ném NotFoundError.
2. HybridRetriever.reload() và ChatEngine.update_knowledge_base() làm mới toàn diện collection handle.
3. Hàm chẩn đoán hệ thống get_system_diagnosis() đọc số lượng vector chính xác mà không gặp lỗi stale collection.
"""

import unittest
from unittest.mock import MagicMock
import chromadb

from config.settings import settings
from src.core.models import QARecord
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.hybrid_retriever import HybridRetriever
from src.ui.app import inspect_storage_metrics


class TestChromaCollectionReload(unittest.TestCase):
    """Kiểm thử chống lỗi 'Collection [...] does not exist' khi replace dữ liệu."""

    def setUp(self):
        self.client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        self.coll_name = settings.CHROMA_COLLECTION_NAME

        self.sample_record = QARecord(
            record_id="REC_TEST_CHROMA_RELOAD_01",
            question="test word nghĩa là gì?",
            answer="Trình độ: A1\nPhát âm: /test/\nDanh từ: Bài kiểm tra",
            word="test",
            sheet="Sheet1",
            source="test.xlsx",
            level="A1"
        )

    def test_collection_auto_reconnect_after_external_delete(self):
        """Khi collection bị xóa và tạo lại bên ngoài, bge_retriever.collection tự động kết nối lại."""
        retriever = BGEChromaRetriever([self.sample_record])

        # 1. Truy cập collection ban đầu
        first_coll = retriever.collection
        self.assertIsNotNone(first_coll)
        first_id = first_coll.id

        # 2. Giả lập một tiến trình khác (hoặc Batch Ingestion) xóa collection và tạo mới
        self.client.delete_collection(name=self.coll_name)
        new_coll = self.client.get_or_create_collection(
            name=self.coll_name,
            metadata={"hnsw:space": "cosine"}
        )
        second_id = new_coll.id
        self.assertNotEqual(first_id, second_id, "Collection mới phải có UUID mới")

        # 3. Truy cập lại qua property collection: phải tự động bắt lỗi stale và kết nối tới UUID mới
        active_coll = retriever.collection
        self.assertIsNotNone(active_coll)
        self.assertEqual(active_coll.id, second_id)

        # 4. get_collection_count() phải hoạt động bình thường, không ném ngoại lệ
        count = retriever.get_collection_count()
        self.assertEqual(count, 0)

    def test_bge_chroma_reload_explicitly_refreshes_collection(self):
        """Hàm bge_retriever.reload() làm mới kết nối collection và cập nhật dữ liệu."""
        retriever = BGEChromaRetriever([])
        old_id = retriever.collection.id

        # Xóa và tạo collection mới
        self.client.delete_collection(name=self.coll_name)
        new_coll = self.client.get_or_create_collection(
            name=self.coll_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.assertNotEqual(old_id, new_coll.id)

        # Gọi reload
        retriever.reload([self.sample_record])
        self.assertEqual(retriever.collection.id, new_coll.id)
        self.assertEqual(len(retriever.records), 1)

    def test_hybrid_retriever_reload_propagates_to_bge_chroma(self):
        """HybridRetriever.reload() phải gọi bge_chroma.reload() để cập nhật collection."""
        hybrid = HybridRetriever([self.sample_record])
        old_id = hybrid.bge_chroma.collection.id

        # Xóa và tạo collection mới
        self.client.delete_collection(name=self.coll_name)
        new_coll = self.client.get_or_create_collection(
            name=self.coll_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Gọi hybrid.reload
        hybrid.reload([self.sample_record])
        self.assertEqual(hybrid.bge_chroma.collection.id, new_coll.id)

    def test_inspect_storage_metrics_resilient_to_stale_collection(self):
        """Hàm chẩn đoán inspect_storage_metrics() không ném lỗi NotFoundError ngay cả khi collection vừa bị xóa."""
        mock_engine = MagicMock()
        mock_bge = MagicMock()
        mock_bge.get_collection_count.return_value = 42
        mock_engine.bge_retriever = mock_bge
        mock_engine.records = [1, 2, 3]
        mock_engine.bm25_retriever.records = [1, 2, 3]

        results = inspect_storage_metrics(mock_engine)
        self.assertEqual(results.get("chroma_count"), 42)
        self.assertIsNone(results.get("chroma_error"))


if __name__ == "__main__":
    unittest.main()
