"""Bộ nạp tệp bảng tính Excel (.xlsx)."""

import logging
from pathlib import Path
from typing import List, Optional

from src.core.models import QARecord
from src.data.loader import QALoader
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)


class ExcelLoader(BaseFileLoader):
    """Xử lý các tệp Excel .xlsx qua stdlib XML."""

    SUPPORTED_EXTENSIONS = ["xlsx"]

    def __init__(self, qa_loader: Optional[QALoader] = None):
        self.qa_loader = qa_loader or QALoader()

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        records = self.qa_loader.load_from_excel(file_path)

        # Cập nhật metadata chuẩn hóa
        for idx, r in enumerate(records, start_index):
            r.source = file_path.name
            # Nếu là ID tự sinh hoặc chưa chuẩn hóa
            if not r.record_id or r.record_id.startswith("CUSTOM_") or r.record_id.startswith("APPEND_"):
                r.record_id = f"XLSX_{file_path.stem[:8]}_{idx:04d}"

        logger.info("ExcelLoader: Nạp thành công %d bản ghi từ %s", len(records), file_path.name)
        return records
