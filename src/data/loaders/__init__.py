"""Package chứa các bộ nạp dữ liệu đa định dạng (Loaders)."""

from src.data.loaders.base import BaseFileLoader, FileValidationResult, compute_file_hash
from src.data.loaders.csv_loader import CSVLoader
from src.data.loaders.docx_loader import DocxLoader
from src.data.loaders.excel_loader import ExcelLoader
from src.data.loaders.json_loader import JSONLoader
from src.data.loaders.oxford_pdf_loader import OxfordPDFParser
from src.data.loaders.pdf_loader import PDFLoader
from src.data.loaders.router import FileLoaderRouter
from src.data.loaders.sqlite_loader import (
    SQLiteColumnInfo,
    SQLiteForeignKeyInfo,
    SQLiteIngestionStats,
    SQLiteLoader,
    SQLiteMappingConfig,
    SQLiteMappingMode,
    SQLiteSchemaInfo,
    SQLiteTableInfo,
)
from src.data.loaders.text_loader import TextLoader

__all__ = [
    "BaseFileLoader",
    "FileValidationResult",
    "compute_file_hash",
    "FileLoaderRouter",
    "ExcelLoader",
    "CSVLoader",
    "JSONLoader",
    "TextLoader",
    "DocxLoader",
    "PDFLoader",
    "OxfordPDFParser",
    "SQLiteLoader",
    "SQLiteMappingConfig",
    "SQLiteMappingMode",
    "SQLiteSchemaInfo",
    "SQLiteTableInfo",
    "SQLiteColumnInfo",
    "SQLiteForeignKeyInfo",
    "SQLiteIngestionStats",
]
