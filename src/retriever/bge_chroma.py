"""Module lưu trữ và tìm kiếm vector ngữ nghĩa sử dụng BGE-M3 và ChromaDB cục bộ.

Hoạt động 100% offline với mô hình BAAI/bge-m3 (1024 chiều) và cơ sở dữ liệu ChromaDB persistent.
Đảm bảo duy trì mapping rõ ràng: Chroma Document ID -> record_id -> Original Data.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

# Đảm bảo môi trường offline tuyệt đối trước khi import thư viện NLP
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import chromadb
from sentence_transformers import SentenceTransformer

from config.settings import settings
from src.core.exceptions import RetrievalError
from src.core.models import QARecord

logger = logging.getLogger(__name__)


class BGEChromaRetriever:
    """Lớp quản lý ChromaDB cục bộ và mô hình embedding BGE-M3."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        self.rec_map: Dict[str, QARecord] = {r.record_id: r for r in records}
        self.client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        self.model: Optional[SentenceTransformer] = None
        self.collection = None

    def _get_embedding_model(self) -> SentenceTransformer:
        """Nạp mô hình BGE-M3 từ local cache (chạy trên CPU để tiết kiệm VRAM cho Qwen)."""
        if self.model is None:
            logger.info("Đang nạp mô hình BGE-M3 từ local cache: %s", settings.BGE_M3_MODEL_NAME)
            try:
                self.model = SentenceTransformer(
                    settings.BGE_M3_MODEL_NAME,
                    device="cpu",
                    local_files_only=True
                )
            except Exception as exc:
                logger.info("Chưa có cache cục bộ cho BGE-M3 (%s), đang tải từ Hugging Face...", exc)
                old_hf = os.environ.pop("HF_HUB_OFFLINE", None)
                old_tr = os.environ.pop("TRANSFORMERS_OFFLINE", None)
                try:
                    self.model = SentenceTransformer(
                        settings.BGE_M3_MODEL_NAME,
                        device="cpu",
                        local_files_only=False
                    )
                finally:
                    if old_hf:
                        os.environ["HF_HUB_OFFLINE"] = old_hf
                    if old_tr:
                        os.environ["TRANSFORMERS_OFFLINE"] = old_tr
        return self.model

    def build_or_load_collection(self, force_reindex: bool = False) -> None:
        """Tải collection ChromaDB sẵn có từ đĩa hoặc tạo mới và index toàn bộ dữ liệu."""
        coll_name = settings.CHROMA_COLLECTION_NAME

        if force_reindex:
            try:
                self.client.delete_collection(name=coll_name)
                logger.info("Đã xóa collection cũ '%s' để re-index.", coll_name)
            except Exception:
                pass

        # Lấy hoặc tạo collection với cosine distance
        self.collection = self.client.get_or_create_collection(
            name=coll_name,
            metadata={"hnsw:space": "cosine"}
        )

        existing_count = self.collection.count()
        if existing_count > 0 and not force_reindex:
            logger.info("Collection '%s' đã có sẵn %d vector. Sẵn sàng sử dụng.", coll_name, existing_count)
            return

        if not self.records:
            logger.info("ChromaDB khởi tạo ở trạng thái rỗng (0 vector).")
            return

        logger.info("Bắt đầu lập chỉ mục ChromaDB cho %d bản ghi bằng BGE-M3...", len(self.records))
        model = self._get_embedding_model()

        batch_size = 64
        total = len(self.records)

        for i in range(0, total, batch_size):
            batch_records = self.records[i:i + batch_size]
            # Nội dung đưa vào vector embedding: kết hợp câu hỏi, từ vựng và phần đầu câu trả lời
            batch_texts = [
                f"Câu hỏi: {r.question}. Từ vựng: {r.word}. {r.answer[:250]}"
                for r in batch_records
            ]
            batch_ids = [r.record_id for r in batch_records]
            batch_metadatas = [
                {
                    "record_id": r.record_id,
                    "word": r.word,
                    "sheet": r.sheet,
                    "source": r.source,
                    "level": r.level
                }
                for r in batch_records
            ]

            # Mã hóa vector với BGE-M3 (normalize_embeddings=True)
            batch_embeddings = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                show_progress_bar=False,
                normalize_embeddings=True
            ).tolist()

            self.collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas
            )
            logger.info("Đã index %d/%d bản ghi vào ChromaDB...", min(i + batch_size, total), total)

        logger.info("Hoàn tất lập chỉ mục ChromaDB với %d vector.", self.collection.count())

    def add_records(self, new_records: List[QARecord], batch_size: int = 64) -> int:
        """Thêm các bản ghi mới vào ChromaDB mà không cần tính toán lại các vector cũ.

        Returns:
            int: Số lượng bản ghi mới thực sự được mã hóa và lưu vào ChromaDB.
        """
        if not new_records:
            return 0

        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

        # Lấy danh sách ID đã có trong ChromaDB để tránh trùng
        existing_ids = set()
        try:
            sample_ids = [r.record_id for r in new_records]
            existing_data = self.collection.get(ids=sample_ids, include=[])
            existing_ids = set(existing_data.get("ids", []))
        except Exception as err:
            logger.warning("Không thể kiểm tra ID có sẵn trong ChromaDB: %s", err)

        records_to_add = [r for r in new_records if r.record_id not in existing_ids]
        if not records_to_add:
            logger.info("Tất cả %d bản ghi đã tồn tại trong ChromaDB.", len(new_records))
            return 0

        logger.info("Đang mã hóa BGE-M3 cho %d bản ghi mới...", len(records_to_add))
        model = self._get_embedding_model()
        total = len(records_to_add)

        for i in range(0, total, batch_size):
            batch = records_to_add[i:i + batch_size]
            batch_texts = [
                f"Câu hỏi: {r.question}. Từ vựng: {r.word}. {r.answer[:250]}"
                for r in batch
            ]
            batch_ids = [r.record_id for r in batch]
            batch_metadatas = [
                {
                    "record_id": r.record_id,
                    "word": r.word,
                    "sheet": r.sheet,
                    "source": r.source,
                    "level": r.level
                }
                for r in batch
            ]

            batch_embeddings = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                show_progress_bar=False,
                normalize_embeddings=True
            ).tolist()

            self.collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas
            )

        # Cập nhật cache bản ghi trong retriever
        for r in records_to_add:
            self.rec_map[r.record_id] = r
            if r not in self.records:
                self.records.append(r)

        logger.info(
            "Đã nạp bổ sung thành công %d vector mới vào ChromaDB (Tổng: %d vector).",
            len(records_to_add),
            self.collection.count()
        )
        return len(records_to_add)

    def upsert_records(self, records: List[QARecord], batch_size: int = 64) -> int:
        """Cập nhật hoặc thêm mới các bản ghi vector vào ChromaDB (hỗ trợ update/overwrite)."""
        if not records:
            return 0

        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

        model = self._get_embedding_model()
        total = len(records)

        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            batch_texts = [
                f"Câu hỏi: {r.question}. Từ vựng: {r.word}. {r.answer[:250]}"
                for r in batch
            ]
            batch_ids = [r.record_id for r in batch]
            batch_metadatas = [
                {
                    "record_id": r.record_id,
                    "word": r.word,
                    "sheet": r.sheet,
                    "source": r.source,
                    "level": r.level
                }
                for r in batch
            ]

            batch_embeddings = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                show_progress_bar=False,
                normalize_embeddings=True
            ).tolist()

            self.collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas
            )

        # Cập nhật cache bản ghi
        for r in records:
            self.rec_map[r.record_id] = r
            replaced = False
            for idx, existing in enumerate(self.records):
                if existing.record_id == r.record_id:
                    self.records[idx] = r
                    replaced = True
                    break
            if not replaced:
                self.records.append(r)

        logger.info("Đã upsert thành công %d vector trong ChromaDB.", len(records))
        return len(records)

    def delete_records(self, record_ids: List[str]) -> int:
        """Xóa các vector tương ứng với danh sách record_id khỏi ChromaDB.

        Returns:
            int: Số lượng vector đã xóa thành công.
        """
        if not record_ids:
            return 0

        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

        try:
            self.collection.delete(ids=record_ids)
            logger.info("Đã xóa %d vector khỏi ChromaDB.", len(record_ids))
        except Exception as err:
            logger.error("Lỗi khi xóa vector khỏi ChromaDB: %s", err)
            return 0

        # Cập nhật cache bộ nhớ trong retriever
        id_set = set(record_ids)
        self.records = [r for r in self.records if r.record_id not in id_set]
        self.rec_map = {r.record_id: r for r in self.records}

        return len(record_ids)

    def search(self, query: str, top_k: int = 15) -> List[Tuple[QARecord, float, int]]:
        """Tìm kiếm top_k văn bản tương đồng ngữ nghĩa bằng BGE-M3 trên ChromaDB.

        Returns:
            List[Tuple[QARecord, float, int]]: Danh sách (bản ghi, điểm similarity cosine, thứ hạng rank 1-indexed)
        """
        if not query.strip() or self.collection is None or not self.records or self.collection.count() == 0:
            return []

        n_results = min(top_k, len(self.records), self.collection.count())
        if n_results <= 0:
            return []

        model = self._get_embedding_model()
        query_vector = model.encode(query.strip(), normalize_embeddings=True).tolist()

        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results
            )
        except Exception as err:
            logger.error("Lỗi khi truy vấn ChromaDB: %s", err)
            raise RetrievalError(f"Lỗi truy vấn ChromaDB: {err}") from err

        candidates: List[Tuple[QARecord, float, int]] = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for rank, (rec_id, dist) in enumerate(zip(ids, distances), 1):
            # Với khoảng cách cosine trong ChromaDB: cosine_similarity = 1 - distance
            sim_score = max(0.0, 1.0 - float(dist))
            rec = self.rec_map.get(rec_id)
            if rec:
                candidates.append((rec, round(sim_score, 4), rank))

        return candidates
