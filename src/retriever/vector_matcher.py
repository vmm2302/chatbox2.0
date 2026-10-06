"""Module truy xuất vector ngữ nghĩa cục bộ (Vector Matcher).

Sử dụng sentence-transformers với mô hình all-MiniLM-L6-v2 đã được lưu cục bộ,
hoạt động hoàn toàn offline mà không gửi bất kỳ yêu cầu nào ra Internet.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np

from config.settings import settings
from src.core.exceptions import RetrievalError
from src.core.models import QARecord, RetrievalResult

logger = logging.getLogger(__name__)

# Bật cờ chạy offline tuyệt đối cho huggingface
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class VectorMatcher:
    """Lớp chịu trách nhiệm lập chỉ mục và tìm kiếm vector tương đồng."""

    def __init__(self, records: List[QARecord], embeddings_path: Optional[Path] = None):
        self.records = records
        self.embeddings_path = embeddings_path or settings.EMBEDDINGS_PATH
        self.model = None
        self.embeddings: Optional[np.ndarray] = None

    def _load_embedding_model(self):
        """Khởi tạo mô hình sentence-transformers từ bộ nhớ đệm cục bộ."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Đang nạp mô hình embedding offline: %s", settings.EMBEDDING_MODEL_NAME)
                self.model = SentenceTransformer(
                    settings.EMBEDDING_MODEL_NAME,
                    local_files_only=True
                )
            except Exception as err:
                raise RetrievalError(f"Không thể nạp mô hình embedding cục bộ: {err}") from err
        return self.model

    def build_or_load_index(self) -> None:
        """Tải ma trận vector từ tệp .npy sẵn có, hoặc tạo mới và lưu lại."""
        if self.embeddings_path.exists():
            try:
                logger.info("Đang nạp ma trận vector từ tệp: %s", self.embeddings_path)
                loaded_embeddings = np.load(self.embeddings_path)
                if len(loaded_embeddings) == len(self.records):
                    self.embeddings = loaded_embeddings
                    logger.info("Đã nạp thành công %d vector embedding.", len(self.embeddings))
                    return
                logger.warning("Số lượng vector trong tệp (%d) không khớp với số bản ghi (%d). Tạo lại index...",
                               len(loaded_embeddings), len(self.records))
            except Exception as err:
                logger.warning("Lỗi khi đọc tệp vector có sẵn: %s. Tiến hành tính toán lại...", err)

        # Tính toán embedding cho toàn bộ câu hỏi trong dataset
        model = self._load_embedding_model()
        questions = [r.question for r in self.records]
        logger.info("Bắt đầu mã hóa vector cho %d câu hỏi...", len(questions))

        # encode với normalize_embeddings=True để tính cosine similarity bằng tích vô hướng (dot product)
        embeddings = model.encode(
            questions,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        self.embeddings = np.array(embeddings, dtype=np.float32)

        # Lưu ma trận vector ra đĩa
        self.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(self.embeddings_path, self.embeddings)
        logger.info("Đã lưu ma trận vector vào: %s", self.embeddings_path)

    def search(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """Tìm kiếm top_k câu hỏi có độ tương đồng cosine cao nhất với câu hỏi người dùng."""
        if self.embeddings is None:
            self.build_or_load_index()

        if not query.strip() or self.embeddings is None or len(self.embeddings) == 0:
            return []

        model = self._load_embedding_model()
        query_vector = model.encode(query.strip(), normalize_embeddings=True)

        # Tính cosine similarity (tích vô hướng giữa vector chuẩn hóa)
        similarities = np.dot(self.embeddings, query_vector)

        # Lấy top_k chỉ số có điểm cao nhất
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[RetrievalResult] = []
        for idx in top_indices:
            score = float(similarities[idx])
            results.append(RetrievalResult(
                record=self.records[idx],
                score=round(score, 4),
                method="VECTOR"
            ))

        return results
