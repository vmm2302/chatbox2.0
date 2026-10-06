"""Giao diện cơ sở cho các bộ nạp dữ liệu đa định dạng (Base Loader)."""

import abc
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import QARecord
from src.data.loader import normalize_vietnamese_text


@dataclass
class FileValidationResult:
    """Kết quả kiểm tra tính hợp lệ của tệp đầu vào."""
    is_valid: bool
    file_type: str
    file_size_bytes: int
    file_hash: str
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_file_hash(file_path: Path) -> str:
    """Tính toán mã băm SHA-256 của tệp để phát hiện trùng lặp chính xác."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


class BaseFileLoader(abc.ABC):
    """Lớp trừu tượng định nghĩa giao diện chung cho tất cả các File Loaders."""

    SUPPORTED_EXTENSIONS: List[str] = []

    @abc.abstractmethod
    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        """Đọc và chuẩn hóa nội dung tệp thành danh sách các bản ghi QARecord.

        Args:
            file_path: Đường dẫn tệp cần nạp.
            file_hash: Mã băm SHA-256 của tệp (nếu đã tính).
            start_index: Chỉ số bắt đầu để sinh record_id duy nhất.

        Returns:
            List[QARecord]: Danh sách các bản ghi Q&A kèm rich metadata.
        """
        pass

    def validate(self, file_path: Path) -> FileValidationResult:
        """Kiểm tra sự tồn tại, quyền đọc, dung lượng và phần mở rộng của tệp."""
        if not file_path.exists():
            return FileValidationResult(
                is_valid=False,
                file_type="",
                file_size_bytes=0,
                file_hash="",
                error_message=f"Tệp không tồn tại: {file_path.name}"
            )

        if not file_path.is_file():
            return FileValidationResult(
                is_valid=False,
                file_type="",
                file_size_bytes=0,
                file_hash="",
                error_message=f"Đường dẫn không phải là tệp hợp lệ: {file_path.name}"
            )

        ext = file_path.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_EXTENSIONS:
            return FileValidationResult(
                is_valid=False,
                file_type=ext,
                file_size_bytes=0,
                file_hash="",
                error_message=f"Định dạng '.{ext}' không được loader này hỗ trợ."
            )

        try:
            size = file_path.stat().st_size
            if size == 0:
                return FileValidationResult(
                    is_valid=False,
                    file_type=ext,
                    file_size_bytes=0,
                    file_hash="",
                    error_message=f"Tệp rỗng (0 bytes): {file_path.name}"
                )
            f_hash = compute_file_hash(file_path)
            return FileValidationResult(
                is_valid=True,
                file_type=ext,
                file_size_bytes=size,
                file_hash=f_hash
            )
        except Exception as err:
            return FileValidationResult(
                is_valid=False,
                file_type=ext,
                file_size_bytes=0,
                file_hash="",
                error_message=f"Lỗi truy cập tệp: {err}"
            )
