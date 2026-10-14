"""Bộ kiểm thử ngăn chặn lỗi trùng lặp ID (Duplicate IDs in upsert) trong ChromaDB & Batch Ingestion."""

import unittest
from pathlib import Path

from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, FileStatus
from src.data.loaders.oxford_pdf_loader import OxfordPDFParser
from src.data.loaders.pdf_loader import PDFLoader
from src.retriever.bge_chroma import BGEChromaRetriever


class TestUpsertDeduplication(unittest.TestCase):
    """Kiểm thử tính bền vững chống duplicate ID tại mọi tầng kiến trúc."""

    def test_bge_chroma_upsert_records_with_duplicate_ids(self):
        """Đảm bảo upsert_records tự động khử trùng lặp ID trước khi gọi ChromaDB."""
        retriever = BGEChromaRetriever(records=[])
        # Tạo danh sách các bản ghi có ID bị trùng lặp cố ý
        records = [
            QARecord(record_id="REC_TEST_DUP_1", word="apple", question="apple là gì?", answer="quả táo"),
            QARecord(record_id="REC_TEST_DUP_1", word="apple", question="apple là gì?", answer="quả táo (cập nhật)"),
            QARecord(record_id="REC_TEST_DUP_2", word="banana", question="banana là gì?", answer="quả chuối"),
            QARecord(record_id="REC_TEST_DUP_2", word="banana", question="banana là gì?", answer="quả chuối (cập nhật)"),
        ]
        # Không được văng ngoại lệ: Expected IDs to be unique, found duplicates
        try:
            # Upsert vào collection in-memory / test: 4 bản ghi với 2 ID duy nhất -> upsert 2 bản ghi
            count = retriever.upsert_records(records)
            self.assertEqual(count, 2)
        except ValueError as e:
            self.fail(f"upsert_records ném ngoại lệ ValueError do duplicate ID: {e}")

    def test_oxford_pdf_loader_never_returns_duplicate_ids(self):
        """Đảm bảo OxfordPDFParser không bao giờ sinh ra các bản ghi có ID trùng nhau."""
        pdf_path = Path("data/raw/The_Oxford_3000_by_CEFR_level.pdf")
        if not pdf_path.exists():
            self.skipTest("Không tìm thấy tệp Oxford PDF để kiểm thử")

        parser = OxfordPDFParser()
        records = parser.load(pdf_path)
        record_ids = [r.record_id for r in records]

        unique_ids = set(record_ids)
        self.assertEqual(
            len(record_ids),
            len(unique_ids),
            f"Phát hiện {len(record_ids) - len(unique_ids)} ID bị trùng trong kết quả của OxfordPDFParser!",
        )

    def test_pdf_loader_generic_disambiguates_duplicate_terms(self):
        """Đảm bảo PDFLoader tự động phân biệt ID khi có các mục trùng lặp trong PDF thông thường."""
        loader = PDFLoader()
        pdf_path = Path("data/raw/The_Oxford_5000_by_CEFR_level.pdf")
        if not pdf_path.exists():
            self.skipTest("Không tìm thấy tệp The_Oxford_5000_by_CEFR_level.pdf")

        records = loader.load(pdf_path)
        record_ids = [r.record_id for r in records]
        unique_ids = set(record_ids)

        self.assertEqual(
            len(record_ids),
            len(unique_ids),
            f"Phát hiện {len(record_ids) - len(unique_ids)} ID bị trùng trong kết quả của PDFLoader!",
        )


if __name__ == "__main__":
    unittest.main()
