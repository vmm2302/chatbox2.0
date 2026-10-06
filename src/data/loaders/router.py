"""Bộ định tuyến nạp tệp (File Loader Router) tự động điều phối theo định dạng."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loaders.base import BaseFileLoader, FileValidationResult, compute_file_hash
from src.data.loaders.csv_loader import CSVLoader
from src.data.loaders.docx_loader import DocxLoader
from src.data.loaders.excel_loader import ExcelLoader
from src.data.loaders.json_loader import JSONLoader
from src.data.loaders.pdf_loader import PDFLoader
from src.data.loaders.text_loader import TextLoader

logger = logging.getLogger(__name__)


class FileLoaderRouter:
    """Định tuyến và điều phối xử lý tệp theo định dạng phần mở rộng (MIME/Extension)."""

    def __init__(self):
        self.loaders: Dict[str, BaseFileLoader] = {}
        self._register_default_loaders()

    def _register_default_loaders(self):
        excel = ExcelLoader()
        csv = CSVLoader()
        json_loader = JSONLoader()
        text = TextLoader()
        docx = DocxLoader()
        pdf = PDFLoader()

        for ext in excel.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = excel
        for ext in csv.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = csv
        for ext in json_loader.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = json_loader
        for ext in text.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = text
        for ext in docx.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = docx
        for ext in pdf.SUPPORTED_EXTENSIONS:
            self.loaders[ext.lower()] = pdf

    @property
    def supported_extensions(self) -> List[str]:
        """Danh sách các phần mở rộng tệp được hệ thống hỗ trợ."""
        return sorted(list(self.loaders.keys()))

    def get_loader(self, file_path: Path) -> BaseFileLoader:
        """Lấy loader tương ứng với phần mở rộng của tệp."""
        ext = file_path.suffix.lower().lstrip(".")
        if not ext:
            raise DataLoadError(f"Tệp '{file_path.name}' không có phần mở rộng định dạng.")

        loader = self.loaders.get(ext)
        if not loader:
            raise DataLoadError(
                f"Định dạng '.{ext}' chưa được hỗ trợ. "
                f"Các định dạng hợp lệ: {', '.join(self.supported_extensions)}"
            )
        return loader

    def validate_file(self, file_path: Path) -> FileValidationResult:
        """Xác thực tính hợp lệ của tệp trước khi đưa vào pipeline nạp."""
        try:
            loader = self.get_loader(file_path)
            return loader.validate(file_path)
        except Exception as err:
            return FileValidationResult(
                is_valid=False,
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=0,
                file_hash="",
                error_message=str(err)
            )

    def load_file(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        """Tải và trích xuất dữ liệu từ tệp thông qua loader thích hợp."""
        loader = self.get_loader(file_path)
        return loader.load(file_path, file_hash=file_hash, start_index=start_index)
