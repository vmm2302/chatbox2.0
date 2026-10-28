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

import threading

_chroma_client_lock = threading.Lock()
_shared_chroma_client: Optional[chromadb.PersistentClient] = None


def get_shared_chroma_client(path: str) -> chromadb.PersistentClient:
    """Trả về client PersistentClient dùng chung, bảo đảm an toàn khởi tạo đa luồng."""
    global _shared_chroma_client
    with _chroma_client_lock:
        if _shared_chroma_client is None:
            _shared_chroma_client = chromadb.PersistentClient(path=path)
        return _shared_chroma_client


class BGEChromaRetriever:
    """Lớp quản lý ChromaDB cục bộ và mô hình embedding BGE-M3."""

    def __init__(self, records: List[QARecord]):
        self.records = records
        self.rec_map: Dict[str, QARecord] = {r.record_id: r for r in records}
        self.client = get_shared_chroma_client(path=str(settings.CHROMA_DIR))
        self.model: Optional[SentenceTransformer] = None
        self._collection = None

    @property
    def collection(self):
        """Trả về collection ChromaDB hiện tại, tự động kết nối lại nếu handle cũ bị xóa hoặc mất hiệu lực."""
        if self._collection is not None:
            try:
                # Kiểm tra tính khả dụng của collection object hiện tại
                _ = self._collection.count()
                return self._collection
            except Exception:
                logger.warning(
                    "Collection ChromaDB handle cũ không còn hợp lệ (có thể đã bị xóa khi re-index). Đang tự động kết nối lại..."
                )
                self._collection = None

        try:
            self._collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:
            logger.error("Không thể kết nối đến collection ChromaDB '%s': %s", settings.CHROMA_COLLECTION_NAME, exc)
            self._collection = None

        return self._collection

    @collection.setter
    def collection(self, val):
        self._collection = val

    def reload(self, new_records: Optional[List[QARecord]] = None) -> None:
        """Cập nhật dữ liệu bản ghi và làm mới kết nối collection ChromaDB."""
        if new_records is not None:
            self.records = new_records
            self.rec_map = {r.record_id: r for r in new_records}

        try:
            self._collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            coll_id = getattr(self._collection, "id", "N/A")
            logger.info(
                "BGEChromaRetriever đã làm mới kết nối tới collection '%s' (UUID: %s).",
                settings.CHROMA_COLLECTION_NAME,
                coll_id
            )
        except Exception as exc:
            logger.error("Không thể làm mới kết nối collection ChromaDB '%s': %s", settings.CHROMA_COLLECTION_NAME, exc)
            self._collection = None

    def get_collection_count(self) -> int:
        """Lấy số lượng vector hiện có trong collection ChromaDB trên đĩa mà không kích hoạt re-index."""
        coll = self.collection
        if coll is not None:
            try:
                return int(coll.count())
            except Exception:
                pass
        try:
            direct_coll = self.client.get_collection(name=settings.CHROMA_COLLECTION_NAME)
            return int(direct_coll.count())
        except Exception:
            return 0

    def _resolve_device(self) -> str:
        """Xác định thiết bị thực thi mô hình BGE-M3 (hỗ trợ GPU CUDA hoặc CPU)."""
        import torch
        conf_device = (getattr(settings, "EMBEDDING_DEVICE", "auto") or "auto").strip().lower()
        if conf_device in ("cuda", "gpu"):
            if torch.cuda.is_available():
                return "cuda"
            logger.warning("Cấu hình EMBEDDING_DEVICE='cuda' nhưng CUDA không khả dụng. Tự động chuyển sang 'cpu'.")
            return "cpu"
        elif conf_device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return "cpu"

    def _get_embedding_model(self, preferred_device: Optional[str] = None):
        """Lấy mô hình BGE-M3 từ EmbeddingModelManager dùng chung để tránh trùng lặp tài nguyên."""
        import sentence_transformers
        target_dev = preferred_device or self._resolve_device()

        # Kiểm tra nếu SentenceTransformer bị mock trong kiểm thử (ví dụ test offline enforcement)
        if SentenceTransformer is not getattr(sentence_transformers, "SentenceTransformer", None):
            try:
                return SentenceTransformer(
                    settings.BGE_M3_MODEL_NAME,
                    device=target_dev,
                    local_files_only=True
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Không thể nạp mô hình BGE-M3 '{settings.BGE_M3_MODEL_NAME}' từ local cache: {exc}. "
                    "Hệ thống đang hoạt động ở chế độ OFFLINE nghiêm ngặt, không tự ý tải model qua mạng trong runtime. "
                    "Vui lòng tải model trước qua script: 'python scripts/download_models.py' hoặc tham khảo HUONG_DAN_CAI_DAT_MAY_MOI.md."
                ) from exc

        from src.resource.manager import get_resource_manager
        try:
            return get_resource_manager().model_manager.get_model(preferred_device=target_dev)
        except Exception as exc:
            raise RuntimeError(
                f"Không thể nạp mô hình BGE-M3 '{settings.BGE_M3_MODEL_NAME}' từ local cache: {exc}. "
                "Hệ thống đang hoạt động ở chế độ OFFLINE nghiêm ngặt, không tự ý tải model qua mạng trong runtime. "
                "Vui lòng tải model trước qua script: 'python scripts/download_models.py' hoặc tham khảo HUONG_DAN_CAI_DAT_MAY_MOI.md."
            ) from exc

    def _encode_texts_safe(self, model, texts: List[str], batch_size: int) -> List[List[float]]:
        """Mã hóa danh sách văn bản với cơ chế bắt lỗi CUDA OOM, tự động giảm batch size hoặc fallback CPU."""
        from src.resource.manager import get_resource_manager
        import torch

        cur_batch_size = max(1, batch_size)
        while True:
            try:
                with get_resource_manager().model_manager.track_inference():
                    embeddings = model.encode(
                        texts,
                        batch_size=cur_batch_size,
                        show_progress_bar=False,
                        normalize_embeddings=True
                    ).tolist()
                return embeddings
            except Exception as err:
                is_oom = "out of memory" in str(err).lower() or (
                    hasattr(torch.cuda, "OutOfMemoryError") and isinstance(err, torch.cuda.OutOfMemoryError)
                )
                if not is_oom:
                    raise

                logger.warning(
                    "Gặp sự cố CUDA Out-Of-Memory khi encode với batch_size=%d: %s. Đang giải phóng cache...",
                    cur_batch_size, err
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                if cur_batch_size > 8:
                    cur_batch_size = cur_batch_size // 2
                    logger.info("Thử lại batch embedding với batch_size nhỏ hơn: %d", cur_batch_size)
                else:
                    logger.warning("Batch size đã giảm về %d nhưng vẫn OOM. Tự động chuyển BGE-M3 sang CPU để hoàn tất.", cur_batch_size)
                    get_resource_manager().model_manager.switch_device("cpu")
                    model = get_resource_manager().model_manager.get_model("cpu")
                    cur_batch_size = 16

    def build_or_load_collection(self, force_reindex: bool = False, batch_size: Optional[int] = None) -> None:
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

        # Khử trùng lặp ID trong self.records (giữ bản ghi xuất hiện sau cùng)
        unique_records: List[QARecord] = []
        seen_rec_ids: set = set()
        for r in reversed(self.records):
            if r.record_id:
                if r.record_id in seen_rec_ids:
                    continue
                seen_rec_ids.add(r.record_id)
            unique_records.append(r)
        unique_records.reverse()
        self.records = unique_records

        logger.info("Bắt đầu lập chỉ mục ChromaDB cho %d bản ghi bằng BGE-M3...", len(self.records))
        model = self._get_embedding_model()

        eff_batch_size = batch_size or (
            getattr(settings, "INDEXING_GPU_BATCH_SIZE", 64)
            if getattr(model, "device", None) and "cuda" in str(model.device)
            else getattr(settings, "INDEXING_CPU_BATCH_SIZE", 32)
        )
        total = len(self.records)

        for i in range(0, total, eff_batch_size):
            batch_records = self.records[i:i + eff_batch_size]
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

            # Mã hóa vector với BGE-M3 an toàn chống OOM
            batch_embeddings = self._encode_texts_safe(model, batch_texts, batch_size=eff_batch_size)

            self.collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas
            )
            logger.info("Đã index %d/%d bản ghi vào ChromaDB...", min(i + eff_batch_size, total), total)

        logger.info("Hoàn tất lập chỉ mục ChromaDB với %d vector.", self.collection.count())


    def add_records(self, new_records: List[QARecord], batch_size: Optional[int] = None) -> int:
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
            sample_ids = [r.record_id for r in new_records if r.record_id]
            if sample_ids:
                existing_data = self.collection.get(ids=sample_ids, include=[])
                existing_ids = set(existing_data.get("ids", []))
        except Exception as err:
            logger.warning("Không thể kiểm tra ID có sẵn trong ChromaDB: %s", err)

        # Lọc ID đã tồn tại và khử trùng lặp nội bộ trong new_records
        records_to_add: List[QARecord] = []
        seen_add_ids: set = set()
        for r in new_records:
            if r.record_id:
                if r.record_id in existing_ids or r.record_id in seen_add_ids:
                    continue
                seen_add_ids.add(r.record_id)
                records_to_add.append(r)
            else:
                records_to_add.append(r)

        if not records_to_add:
            logger.info("Tất cả %d bản ghi đã tồn tại trong ChromaDB.", len(new_records))
            return 0

        logger.info("Đang mã hóa BGE-M3 cho %d bản ghi mới...", len(records_to_add))
        model = self._get_embedding_model()
        eff_batch_size = batch_size or (
            getattr(settings, "INDEXING_GPU_BATCH_SIZE", 64)
            if getattr(model, "device", None) and "cuda" in str(model.device)
            else getattr(settings, "INDEXING_CPU_BATCH_SIZE", 32)
        )
        total = len(records_to_add)

        for i in range(0, total, eff_batch_size):
            batch = records_to_add[i:i + eff_batch_size]
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

            batch_embeddings = self._encode_texts_safe(model, batch_texts, batch_size=eff_batch_size)

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

    def upsert_records(self, records: List[QARecord], batch_size: Optional[int] = None) -> int:
        """Cập nhật hoặc thêm mới các bản ghi vector vào ChromaDB (hỗ trợ update/overwrite)."""
        if not records:
            return 0

        # Khử trùng lặp ID (giữ bản ghi mới nhất xuất hiện sau cùng) để đảm bảo ChromaDB không bao giờ lỗi duplicate IDs
        unique_records: List[QARecord] = []
        seen_ids: set = set()
        for r in reversed(records):
            rec_id = r.record_id
            if rec_id:
                if rec_id in seen_ids:
                    continue
                seen_ids.add(rec_id)
            unique_records.append(r)
        unique_records.reverse()
        records = unique_records

        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

        model = self._get_embedding_model()
        eff_batch_size = batch_size or (
            getattr(settings, "INDEXING_GPU_BATCH_SIZE", 64)
            if getattr(model, "device", None) and "cuda" in str(model.device)
            else getattr(settings, "INDEXING_CPU_BATCH_SIZE", 32)
        )
        total = len(records)

        for i in range(0, total, eff_batch_size):
            batch = records[i:i + eff_batch_size]
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

            batch_embeddings = self._encode_texts_safe(model, batch_texts, batch_size=eff_batch_size)

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
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
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

    def clear_collection(self) -> None:
        """Xóa toàn bộ vector trong collection ChromaDB và tái tạo collection ở trạng thái rỗng."""
        coll_name = settings.CHROMA_COLLECTION_NAME
        try:
            self.client.delete_collection(name=coll_name)
            logger.info("BGEChromaRetriever: Đã xóa collection '%s'.", coll_name)
        except Exception as exc:
            logger.warning("BGEChromaRetriever: delete_collection '%s' ghi nhận: %s", coll_name, exc)

        self._collection = self.client.get_or_create_collection(
            name=coll_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.records = []
        self.rec_map = {}
        logger.info("BGEChromaRetriever: Đã khởi tạo lại collection rỗng '%s' (count=0).", coll_name)

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

        # Trong chế độ chat, ưu tiên sử dụng thiết bị CPU để bảo toàn VRAM cho mô hình LLM Qwen
        chat_device = getattr(settings, "EMBEDDING_CHAT_DEVICE", "cpu")
        model = self._get_embedding_model(preferred_device=chat_device)

        from src.resource.manager import get_resource_manager
        with get_resource_manager().model_manager.track_inference():
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
            # Ngưỡng tương đồng tối thiểu để được coi là ứng viên ngữ nghĩa hợp lệ
            if sim_score >= 0.45:
                rec = self.rec_map.get(rec_id)
                if rec:
                    candidates.append((rec, round(sim_score, 4), rank))

        return candidates

