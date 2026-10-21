"""Bộ nạp cơ sở dữ liệu SQLite (.db, .sqlite) tổng quát cho Knowledge Base của Chatbox 2.0.

Đặc tính kỹ thuật:
- Mở cơ sở dữ liệu ở chế độ chỉ đọc (Read-only URI mode=ro), tuyệt đối không ghi đè hoặc chỉnh sửa tệp gốc.
- Xác thực tệp SQLite thực tế qua 16-byte magic header (b"SQLite format 3\\x00") và PRAGMA quick_check.
- Lọc bỏ các bảng hệ thống SQLite nội bộ (sqlite_master, sqlite_sequence, sqlite_stat*).
- Đọc danh sách bảng, cột, kiểu dữ liệu và khóa ngoại (PRAGMA foreign_key_list).
- Hỗ trợ 3 chế độ ánh xạ chuẩn hóa:
  1. Hỏi - Đáp (Q&A): Cột câu hỏi, câu trả lời, từ khóa, trình độ, mã ID.
  2. Từ vựng Từ điển (Single-table Vocab): Từ tiếng Anh, nghĩa tiếng Việt, IPA, từ loại, ví dụ, dịch ví dụ, CEFR.
  3. Quan hệ Nhiều bảng (Relational Join): Kết hợp bảng chính và bảng liên kết qua khóa ngoại với cơ chế gom nhóm (grouping) tránh nhân bản dữ liệu.
- Đọc dữ liệu theo từng Batch (cursor.fetchmany) nhằm bảo vệ bộ nhớ RAM khi tiếp nhận database lớn.
- Báo cáo số bảng, số dòng đọc, số bản ghi hợp lệ và số bản ghi bị bỏ qua kèm lý do cụ thể.
- An toàn tuyệt đối: Thoát ký tự định danh (identifier escaping) chống SQL Injection; đóng cursor và kết nối trong khối finally.
"""

import hashlib
import logging
import re
import sqlite3
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import normalize_vietnamese_text
from src.data.loaders.base import (
    BaseFileLoader,
    FileValidationResult,
    clean_source_name,
    compute_file_hash,
    generate_stable_record_id,
)

logger = logging.getLogger(__name__)

# Header chuẩn 16 bytes của tệp SQLite định dạng 3
SQLITE_MAGIC_HEADER = b"SQLite format 3\x00"

# Giới hạn kích thước tệp tối đa (500 MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

# Kích thước batch đọc qua cursor.fetchmany để tiết kiệm RAM
DEFAULT_FETCH_BATCH_SIZE = 500

# Giới hạn tối đa số bản ghi trích xuất cho mỗi tệp để bảo vệ bộ nhớ hệ thống
DEFAULT_MAX_RECORDS_LIMIT = 50000


class SQLiteMappingMode(str, Enum):
    """Chế độ ánh xạ dữ liệu từ bảng SQLite sang schema chuẩn hóa."""
    QA = "qa"                      # Cấu trúc Hỏi - Đáp (Question / Answer)
    VOCAB = "vocab"                # Cấu trúc Từ vựng đơn bảng (Word / Definition / IPA / POS / Example)
    RELATIONAL = "relational"      # Cấu trúc Quan hệ nhiều bảng qua Khóa ngoại (Parent - Child Join)
    AUTO = "auto"                  # Tự động nhận diện cấu trúc


@dataclass
class SQLiteColumnInfo:
    """Thông tin chi tiết của một cột trong bảng SQLite."""
    name: str
    data_type: str = "TEXT"
    not_null: bool = False
    is_pk: bool = False


@dataclass
class SQLiteForeignKeyInfo:
    """Thông tin khóa ngoại liên kết giữa các bảng."""
    table: str                  # Tên bảng cha được tham chiếu (referenced table)
    from_col: str               # Tên cột khóa ngoại trong bảng hiện tại
    to_col: str                 # Tên cột khóa chính trong bảng cha


@dataclass
class SQLiteTableInfo:
    """Thông tin cấu trúc và mẫu dữ liệu của một bảng SQLite."""
    name: str
    columns: List[SQLiteColumnInfo] = field(default_factory=list)
    row_count: int = 0
    foreign_keys: List[SQLiteForeignKeyInfo] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SQLiteSchemaInfo:
    """Thông tin lược đồ tổng thể của tệp cơ sở dữ liệu SQLite."""
    file_path: str
    file_size_bytes: int
    file_hash: str
    is_valid: bool
    error_message: Optional[str] = None
    tables: Dict[str, SQLiteTableInfo] = field(default_factory=dict)


@dataclass
class SQLiteIngestionStats:
    """Thống kê chi tiết quá trình nạp bản ghi từ SQLite."""
    total_tables: int = 0
    tables_processed: List[str] = field(default_factory=list)
    total_rows_read: int = 0
    valid_records: int = 0
    skipped_records: int = 0
    skip_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass
class SQLiteMappingConfig:
    """Cấu hình ánh xạ cột tùy chỉnh cho tệp SQLite."""
    mode: SQLiteMappingMode = SQLiteMappingMode.QA
    primary_table: str = ""

    # Dành cho chế độ RELATIONAL
    related_table: Optional[str] = None
    foreign_key_child_col: Optional[str] = None
    foreign_key_parent_col: Optional[str] = None

    # Ánh xạ cột Hỏi - Đáp
    question_col: Optional[str] = None
    answer_col: Optional[str] = None

    # Ánh xạ cột Từ vựng
    word_col: Optional[str] = None
    definition_col: Optional[str] = None
    ipa_col: Optional[str] = None
    pos_col: Optional[str] = None
    example_col: Optional[str] = None
    example_trans_col: Optional[str] = None
    level_col: Optional[str] = None
    id_col: Optional[str] = None

    # Giới hạn số lượng bản ghi (tùy chọn)
    max_records: Optional[int] = None


def escape_sql_identifier(identifier: str) -> str:
    """Thoát ký tự an toàn cho tên bảng và cột SQL để phòng chống SQL Injection.
    
    Quy tắc SQLite: Bọc tên định danh trong cặp ngoặc kép và nhân đôi dấu ngoặc kép bên trong.
    """
    clean_id = str(identifier).replace('"', '""')
    return f'"{clean_id}"'


def open_readonly_sqlite(file_path: Path) -> sqlite3.Connection:
    """Khởi tạo kết nối SQLite ở chế độ chỉ đọc an toàn (Read-Only URI)."""
    posix_path = file_path.resolve().as_posix()
    try:
        uri = f"file:{posix_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    except Exception:
        quoted = urllib.parse.quote(posix_path, safe="/:")
        conn = sqlite3.connect(f"file:{quoted}?mode=ro", uri=True, check_same_thread=False)
    
    conn.row_factory = sqlite3.Row
    return conn


def format_vocab_record_answer(
    word: str,
    definition: str,
    ipa: Optional[str] = None,
    pos: Optional[str] = None,
    example: Optional[str] = None,
    example_trans: Optional[str] = None,
    level: Optional[str] = None,
) -> str:
    """Định dạng nội dung câu trả lời từ vựng chuẩn hóa, tương thích hoàn toàn với RAG."""
    parts: List[str] = []
    if level and str(level).strip():
        parts.append(f"Trình độ: {str(level).strip().upper()}")

    if ipa and str(ipa).strip():
        clean_ipa = str(ipa).strip()
        if not clean_ipa.startswith("/"):
            clean_ipa = f"/{clean_ipa}"
        if not clean_ipa.endswith("/"):
            clean_ipa = f"{clean_ipa}/"
        parts.append(f"Phát âm: {clean_ipa}")

    pos_line = ""
    if pos and str(pos).strip():
        pos_line = f"Từ loại: {str(pos).strip()}\n"

    def_block = f"{pos_line}Định nghĩa:\n{str(definition).strip()}"
    if example and str(example).strip():
        ex_line = f"   • Ví dụ: {str(example).strip()}"
        if example_trans and str(example_trans).strip():
            ex_line += f"\n     (Dịch: {str(example_trans).strip()})"
        def_block += f"\n{ex_line}"

    parts.append(def_block)
    return "\n\n".join(parts)


class SQLiteLoader(BaseFileLoader):
    """Bộ nạp cơ sở dữ liệu SQLite (.db, .sqlite) tổng quát cho Chatbox 2.0."""

    SUPPORTED_EXTENSIONS = ["db", "sqlite"]

    def __init__(
        self,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
        fetch_batch_size: int = DEFAULT_FETCH_BATCH_SIZE,
        max_records_limit: int = DEFAULT_MAX_RECORDS_LIMIT,
    ):
        self.max_file_size_bytes = max_file_size_bytes
        self.fetch_batch_size = fetch_batch_size
        self.max_records_limit = max_records_limit
        self.last_stats: Optional[SQLiteIngestionStats] = None

    def validate(self, file_path: Path) -> FileValidationResult:
        """Xác thực tính hợp lệ của tệp SQLite:
        1. Kiểm tra sự tồn tại và dung lượng (không rỗng, không vượt ngưỡng).
        2. Kiểm tra phần mở rộng (.db, .sqlite).
        3. Kiểm tra 16 bytes magic header đặc trưng của SQLite.
        4. Kiểm tra mở tệp ở chế độ read-only và thực thi PRAGMA quick_check.
        5. Kiểm tra có ít nhất một bảng dữ liệu người dùng (không phải hệ thống).
        """
        # Kiểm tra cơ sở
        base_val = super().validate(file_path)
        if not base_val.is_valid:
            return base_val

        # Kiểm tra giới hạn dung lượng
        if base_val.file_size_bytes > self.max_file_size_bytes:
            return FileValidationResult(
                is_valid=False,
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=base_val.file_size_bytes,
                file_hash=base_val.file_hash,
                error_message=(
                    f"Dung lượng tệp ({base_val.file_size_bytes / (1024 * 1024):.2f} MB) "
                    f"vượt quá ngưỡng cho phép ({self.max_file_size_bytes / (1024 * 1024):.0f} MB)."
                )
            )

        # Kiểm tra magic header 16 bytes của SQLite
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header != SQLITE_MAGIC_HEADER:
                return FileValidationResult(
                    is_valid=False,
                    file_type=file_path.suffix.lower().lstrip("."),
                    file_size_bytes=base_val.file_size_bytes,
                    file_hash=base_val.file_hash,
                    error_message=f"Tệp '{file_path.name}' không phải là cơ sở dữ liệu SQLite hợp lệ (Header magic bytes không khớp)."
                )
        except Exception as read_err:
            return FileValidationResult(
                is_valid=False,
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=base_val.file_size_bytes,
                file_hash=base_val.file_hash,
                error_message=f"Không thể đọc header của tệp: {read_err}"
            )

        # Mở read-only và chạy PRAGMA quick_check
        conn = None
        try:
            conn = open_readonly_sqlite(file_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check(1);")
            check_res = cursor.fetchone()
            if not check_res or str(check_res[0]).strip().lower() != "ok":
                return FileValidationResult(
                    is_valid=False,
                    file_type=file_path.suffix.lower().lstrip("."),
                    file_size_bytes=base_val.file_size_bytes,
                    file_hash=base_val.file_hash,
                    error_message=f"Cơ sở dữ liệu SQLite bị lỗi toàn vẹn: {check_res[0] if check_res else 'Unknown error'}"
                )

            # Đọc danh sách bảng người dùng
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            tables = [row[0] for row in cursor.fetchall()]
            if not tables:
                return FileValidationResult(
                    is_valid=False,
                    file_type=file_path.suffix.lower().lstrip("."),
                    file_size_bytes=base_val.file_size_bytes,
                    file_hash=base_val.file_hash,
                    error_message=f"Cơ sở dữ liệu '{file_path.name}' không chứa bảng dữ liệu người dùng nào."
                )

            return FileValidationResult(
                is_valid=True,
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=base_val.file_size_bytes,
                file_hash=base_val.file_hash,
                metadata={"user_tables": tables, "table_count": len(tables)}
            )

        except Exception as sql_err:
            return FileValidationResult(
                is_valid=False,
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=base_val.file_size_bytes,
                file_hash=base_val.file_hash,
                error_message=f"Không thể mở cơ sở dữ liệu SQLite ở chế độ chỉ đọc: {sql_err}"
            )
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def inspect_schema(self, file_path: Path) -> SQLiteSchemaInfo:
        """Khám phá cấu trúc bảng, cột, kiểu dữ liệu, khóa ngoại và dữ liệu mẫu của tệp SQLite."""
        val_res = self.validate(file_path)
        if not val_res.is_valid:
            return SQLiteSchemaInfo(
                file_path=str(file_path),
                file_size_bytes=val_res.file_size_bytes,
                file_hash=val_res.file_hash,
                is_valid=False,
                error_message=val_res.error_message,
                tables={}
            )

        tables_info: Dict[str, SQLiteTableInfo] = {}
        conn = None
        try:
            conn = open_readonly_sqlite(file_path)
            cursor = conn.cursor()

            # Lấy danh sách bảng người dùng (loại trừ các bảng hệ thống SQLite)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            table_names = [row[0] for row in cursor.fetchall()]

            for t_name in table_names:
                escaped_t = escape_sql_identifier(t_name)

                # 1. Đọc thông tin cột
                cursor.execute(f"PRAGMA table_info({escaped_t});")
                col_rows = cursor.fetchall()
                columns: List[SQLiteColumnInfo] = []
                for c in col_rows:
                    columns.append(SQLiteColumnInfo(
                        name=c["name"],
                        data_type=c["type"] or "TEXT",
                        not_null=bool(c["notnull"]),
                        is_pk=bool(c["pk"])
                    ))

                # 2. Đọc thông tin khóa ngoại
                foreign_keys: List[SQLiteForeignKeyInfo] = []
                try:
                    cursor.execute(f"PRAGMA foreign_key_list({escaped_t});")
                    fk_rows = cursor.fetchall()
                    for fk in fk_rows:
                        foreign_keys.append(SQLiteForeignKeyInfo(
                            table=fk["table"],
                            from_col=fk["from"],
                            to_col=fk["to"] or "id"
                        ))
                except Exception as fk_err:
                    logger.debug("Không thể đọc foreign_key_list cho %s: %s", t_name, fk_err)

                # 3. Đếm số dòng dữ liệu
                row_count = 0
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {escaped_t};")
                    count_row = cursor.fetchone()
                    row_count = int(count_row[0]) if count_row else 0
                except Exception as count_err:
                    logger.debug("Không thể đếm dòng cho %s: %s", t_name, count_err)

                # 4. Trích xuất mẫu 5 dòng đầu
                sample_rows: List[Dict[str, Any]] = []
                try:
                    cursor.execute(f"SELECT * FROM {escaped_t} LIMIT 5;")
                    samples = cursor.fetchall()
                    for s in samples:
                        sample_dict = {}
                        for k in s.keys():
                            cell_val = s[k]
                            if isinstance(cell_val, bytes):
                                try:
                                    cell_val = cell_val.decode("utf-8")
                                except Exception:
                                    cell_val = f"<BLOB {len(cell_val)} bytes>"
                            elif cell_val is None:
                                cell_val = "NULL"
                            sample_dict[k] = cell_val
                        sample_rows.append(sample_dict)
                except Exception as sample_err:
                    logger.debug("Không thể đọc dữ liệu mẫu cho %s: %s", t_name, sample_err)

                tables_info[t_name] = SQLiteTableInfo(
                    name=t_name,
                    columns=columns,
                    row_count=row_count,
                    foreign_keys=foreign_keys,
                    sample_rows=sample_rows
                )

            return SQLiteSchemaInfo(
                file_path=str(file_path),
                file_size_bytes=val_res.file_size_bytes,
                file_hash=val_res.file_hash,
                is_valid=True,
                error_message=None,
                tables=tables_info
            )

        except Exception as err:
            return SQLiteSchemaInfo(
                file_path=str(file_path),
                file_size_bytes=val_res.file_size_bytes,
                file_hash=val_res.file_hash,
                is_valid=False,
                error_message=f"Lỗi khi khám phá cấu trúc SQLite: {err}",
                tables={}
            )
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def auto_detect_mapping(self, schema: SQLiteSchemaInfo) -> Optional[SQLiteMappingConfig]:
        """Tự động suy luận cấu hình ánh xạ nếu cấu trúc bảng trùng khớp với các mẫu phổ biến."""
        if not schema.is_valid or not schema.tables:
            return None

        table_names_lower = {k.lower(): k for k in schema.tables.keys()}

        # 1. Kiểm tra mẫu Cơ sở dữ liệu từ điển quan hệ chuẩn (words, definitions, word_definitions)
        if "words" in table_names_lower and "definitions" in table_names_lower:
            words_t = table_names_lower["words"]
            defs_t = table_names_lower["definitions"]
            w_cols = {c.name.lower(): c.name for c in schema.tables[words_t].columns}
            d_cols = {c.name.lower(): c.name for c in schema.tables[defs_t].columns}

            if "word" in w_cols and "definition" in d_cols:
                # Kiểm tra khóa ngoại giữa definitions và words
                fk_child_col = None
                for fk in schema.tables[defs_t].foreign_keys:
                    if fk.table.lower() == "words":
                        fk_child_col = fk.from_col
                        break

                if not fk_child_col and "word_id" in d_cols:
                    fk_child_col = d_cols["word_id"]

                if fk_child_col:
                    return SQLiteMappingConfig(
                        mode=SQLiteMappingMode.RELATIONAL,
                        primary_table=words_t,
                        related_table=defs_t,
                        foreign_key_parent_col=w_cols.get("id", "id"),
                        foreign_key_child_col=fk_child_col,
                        word_col=w_cols.get("word"),
                        definition_col=d_cols.get("definition"),
                        pos_col=d_cols.get("pos"),
                        example_col=d_cols.get("example"),
                        level_col=w_cols.get("level"),
                        id_col=w_cols.get("id"),
                    )

        # 2. Duyệt qua từng bảng để nhận diện mẫu Hỏi - Đáp (Q&A) hoặc Từ vựng đơn bảng (Vocab)
        q_candidates = ["question", "cau_hoi", "query", "prompt", "cauhoi", "q"]
        a_candidates = ["answer", "cau_tra_loi", "tra_loi", "response", "content", "cautraloi", "a"]
        w_candidates = ["word", "tu_vung", "vocab", "term", "keyword", "english", "tieng_anh"]
        def_candidates = ["definition", "dinh_nghia", "meaning", "nghia", "vietnamese", "tieng_viet", "giai_thich"]

        for t_name, t_info in schema.tables.items():
            cols_lower = {c.name.lower(): c.name for c in t_info.columns}

            # Kiểm tra mẫu Hỏi - Đáp (Q&A)
            matched_q = next((cols_lower[c] for c in q_candidates if c in cols_lower), None)
            matched_a = next((cols_lower[c] for c in a_candidates if c in cols_lower), None)
            if matched_q and matched_a:
                matched_w = next((cols_lower[c] for c in w_candidates if c in cols_lower), None)
                matched_lvl = next((cols_lower[c] for c in ["level", "trinh_do", "cefr", "cap_do"] if c in cols_lower), None)
                matched_id = next((cols_lower[c] for c in ["id", "record_id", "qa_id"] if c in cols_lower), None)
                return SQLiteMappingConfig(
                    mode=SQLiteMappingMode.QA,
                    primary_table=t_name,
                    question_col=matched_q,
                    answer_col=matched_a,
                    word_col=matched_w,
                    level_col=matched_lvl,
                    id_col=matched_id,
                )

            # Kiểm tra mẫu Từ vựng đơn bảng (Vocab)
            matched_w = next((cols_lower[c] for c in w_candidates if c in cols_lower), None)
            matched_def = next((cols_lower[c] for c in def_candidates if c in cols_lower), None)
            if matched_w and matched_def:
                matched_ipa = next((cols_lower[c] for c in ["ipa", "phien_am", "pronunciation", "pronounce"] if c in cols_lower), None)
                matched_pos = next((cols_lower[c] for c in ["pos", "tu_loai", "part_of_speech", "type"] if c in cols_lower), None)
                matched_ex = next((cols_lower[c] for c in ["example", "vi_du", "sentence", "cau_vi_du"] if c in cols_lower), None)
                matched_ex_tr = next((cols_lower[c] for c in ["example_trans", "dich_vi_du", "example_vi"] if c in cols_lower), None)
                matched_lvl = next((cols_lower[c] for c in ["level", "trinh_do", "cefr", "cap_do"] if c in cols_lower), None)
                matched_id = next((cols_lower[c] for c in ["id", "record_id", "word_id"] if c in cols_lower), None)
                return SQLiteMappingConfig(
                    mode=SQLiteMappingMode.VOCAB,
                    primary_table=t_name,
                    word_col=matched_w,
                    definition_col=matched_def,
                    ipa_col=matched_ipa,
                    pos_col=matched_pos,
                    example_col=matched_ex,
                    example_trans_col=matched_ex_tr,
                    level_col=matched_lvl,
                    id_col=matched_id,
                )

        return None

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1,
        mapping_config: Optional[SQLiteMappingConfig] = None
    ) -> List[QARecord]:
        """Tải và trích xuất dữ liệu từ tệp SQLite thành danh sách QARecord chuẩn hóa.
        
        Nếu mapping_config là None, hệ thống sẽ tự động phân tích lược đồ và suy luận
        cấu hình ánh xạ phù hợp.
        """
        val_res = self.validate(file_path)
        if not val_res.is_valid:
            raise DataLoadError(f"Không thể nạp tệp SQLite '{file_path.name}': {val_res.error_message}")

        f_hash = file_hash or val_res.file_hash
        schema = self.inspect_schema(file_path)

        config = mapping_config
        if config is None:
            config = self.auto_detect_mapping(schema)
            if config is None:
                raise DataLoadError(
                    f"Không thể tự động nhận diện cấu trúc dữ liệu trong tệp SQLite '{file_path.name}'. "
                    f"Vui lòng chỉ định cấu hình ánh xạ bảng và cột trước khi nạp."
                )

        # Kiểm tra bảng chính có tồn tại không
        if not config.primary_table or config.primary_table not in schema.tables:
            raise DataLoadError(
                f"Bảng '{config.primary_table}' không tồn tại trong tệp SQLite '{file_path.name}'. "
                f"Các bảng hợp lệ: {', '.join(schema.tables.keys())}"
            )

        # Khởi tạo đối tượng thống kê
        stats = SQLiteIngestionStats(
            total_tables=len(schema.tables),
            tables_processed=[config.primary_table],
        )

        records: List[QARecord] = []
        conn = None
        try:
            conn = open_readonly_sqlite(file_path)

            if config.mode == SQLiteMappingMode.QA:
                records = self._load_qa_mode(conn, file_path, config, schema, start_index, stats)
            elif config.mode == SQLiteMappingMode.VOCAB:
                records = self._load_vocab_mode(conn, file_path, config, schema, start_index, stats)
            elif config.mode == SQLiteMappingMode.RELATIONAL:
                if config.related_table:
                    stats.tables_processed.append(config.related_table)
                records = self._load_relational_mode(conn, file_path, config, schema, start_index, stats)
            else:
                raise DataLoadError(f"Chế độ ánh xạ '{config.mode}' không được hỗ trợ.")

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        stats.valid_records = len(records)
        self.last_stats = stats

        logger.info(
            "SQLiteLoader: Đã hoàn tất xử lý '%s' (Đọc: %d dòng, Hợp lệ: %d, Bỏ qua: %d, Bảng: %s)",
            file_path.name,
            stats.total_rows_read,
            stats.valid_records,
            stats.skipped_records,
            ", ".join(stats.tables_processed),
        )
        return records

    def preview_records(
        self,
        file_path: Path,
        mapping_config: SQLiteMappingConfig,
        limit: int = 5
    ) -> List[QARecord]:
        """Trích xuất một số bản ghi mẫu sau khi ánh xạ phục vụ kiểm tra trước khi nạp chính thức."""
        preview_cfg = SQLiteMappingConfig(
            mode=mapping_config.mode,
            primary_table=mapping_config.primary_table,
            related_table=mapping_config.related_table,
            foreign_key_child_col=mapping_config.foreign_key_child_col,
            foreign_key_parent_col=mapping_config.foreign_key_parent_col,
            question_col=mapping_config.question_col,
            answer_col=mapping_config.answer_col,
            word_col=mapping_config.word_col,
            definition_col=mapping_config.definition_col,
            ipa_col=mapping_config.ipa_col,
            pos_col=mapping_config.pos_col,
            example_col=mapping_config.example_col,
            example_trans_col=mapping_config.example_trans_col,
            level_col=mapping_config.level_col,
            id_col=mapping_config.id_col,
            max_records=limit
        )
        return self.load(file_path=file_path, start_index=1, mapping_config=preview_cfg)

    # --- CÁC HÀM XỬ LÝ NỘI BỘ THEO CHẾ ĐỘ ÁNH XẠ ---

    def _load_qa_mode(
        self,
        conn: sqlite3.Connection,
        file_path: Path,
        config: SQLiteMappingConfig,
        schema: SQLiteSchemaInfo,
        start_index: int,
        stats: SQLiteIngestionStats,
    ) -> List[QARecord]:
        """Xử lý nạp dữ liệu ở chế độ Hỏi - Đáp (Q&A)."""
        table_info = schema.tables[config.primary_table]
        col_names = {c.name for c in table_info.columns}

        if not config.question_col or config.question_col not in col_names:
            raise DataLoadError(f"Cột câu hỏi '{config.question_col}' không tồn tại trong bảng '{config.primary_table}'.")
        if not config.answer_col or config.answer_col not in col_names:
            raise DataLoadError(f"Cột câu trả lời '{config.answer_col}' không tồn tại trong bảng '{config.primary_table}'.")

        # Xác thực và thoát ký tự tên cột
        escaped_table = escape_sql_identifier(config.primary_table)
        cols_to_select = [config.question_col, config.answer_col]
        if config.word_col and config.word_col in col_names:
            cols_to_select.append(config.word_col)
        if config.level_col and config.level_col in col_names:
            cols_to_select.append(config.level_col)
        if config.id_col and config.id_col in col_names:
            cols_to_select.append(config.id_col)

        escaped_cols = ", ".join(escape_sql_identifier(c) for c in cols_to_select)
        max_limit = config.max_records or self.max_records_limit
        query = f"SELECT {escaped_cols} FROM {escaped_table};"

        cursor = conn.cursor()
        cursor.execute(query)

        records: List[QARecord] = []
        clean_src = clean_source_name(file_path.name)

        while len(records) < max_limit:
            rows = cursor.fetchmany(self.fetch_batch_size)
            if not rows:
                break

            for row in rows:
                stats.total_rows_read += 1
                q_val = row[config.question_col]
                a_val = row[config.answer_col]

                # Xử lý an toàn dữ liệu NULL hoặc kiểu dữ liệu không mong đợi
                q_str = str(q_val).strip() if q_val is not None else ""
                a_str = str(a_val).strip() if a_val is not None else ""

                if not q_str or not a_str:
                    stats.skipped_records += 1
                    stats.skip_reasons["Trường câu hỏi hoặc câu trả lời bị rỗng/NULL"] = (
                        stats.skip_reasons.get("Trường câu hỏi hoặc câu trả lời bị rỗng/NULL", 0) + 1
                    )
                    continue

                # Bỏ qua nếu dòng dữ liệu là tiêu đề lặp lại
                if normalize_vietnamese_text(q_str) in ["cau hoi", "question"]:
                    stats.skipped_records += 1
                    stats.skip_reasons["Dòng tiêu đề trùng lặp"] = (
                        stats.skip_reasons.get("Dòng tiêu đề trùng lặp", 0) + 1
                    )
                    continue

                w_val = row[config.word_col] if config.word_col and config.word_col in row.keys() else ""
                w_str = str(w_val).strip() if w_val is not None else ""

                lvl_val = row[config.level_col] if config.level_col and config.level_col in row.keys() else ""
                lvl_str = str(lvl_val).strip().upper() if lvl_val is not None else ""

                custom_id_val = row[config.id_col] if config.id_col and config.id_col in row.keys() else ""
                custom_id = str(custom_id_val).strip() if custom_id_val is not None else ""

                rec_id = generate_stable_record_id(clean_src, q_str, custom_id=custom_id or None)
                records.append(QARecord(
                    record_id=rec_id,
                    word=w_str,
                    sheet=config.primary_table,
                    source=clean_src,
                    level=lvl_str,
                    question=q_str,
                    answer=a_str,
                    normalized_question=normalize_vietnamese_text(q_str),
                ))

                if len(records) >= max_limit:
                    break

        return records

    def _load_vocab_mode(
        self,
        conn: sqlite3.Connection,
        file_path: Path,
        config: SQLiteMappingConfig,
        schema: SQLiteSchemaInfo,
        start_index: int,
        stats: SQLiteIngestionStats,
    ) -> List[QARecord]:
        """Xử lý nạp dữ liệu ở chế độ Từ vựng Đơn bảng (Single-table Vocab)."""
        table_info = schema.tables[config.primary_table]
        col_names = {c.name for c in table_info.columns}

        if not config.word_col or config.word_col not in col_names:
            raise DataLoadError(f"Cột từ vựng '{config.word_col}' không tồn tại trong bảng '{config.primary_table}'.")
        if not config.definition_col or config.definition_col not in col_names:
            raise DataLoadError(f"Cột định nghĩa '{config.definition_col}' không tồn tại trong bảng '{config.primary_table}'.")

        escaped_table = escape_sql_identifier(config.primary_table)
        cols_to_select = [config.word_col, config.definition_col]
        optional_fields = [
            config.ipa_col, config.pos_col, config.example_col,
            config.example_trans_col, config.level_col, config.id_col
        ]
        for opt in optional_fields:
            if opt and opt in col_names and opt not in cols_to_select:
                cols_to_select.append(opt)

        escaped_cols = ", ".join(escape_sql_identifier(c) for c in cols_to_select)
        max_limit = config.max_records or self.max_records_limit
        query = f"SELECT {escaped_cols} FROM {escaped_table};"

        cursor = conn.cursor()
        cursor.execute(query)

        records: List[QARecord] = []
        clean_src = clean_source_name(file_path.name)

        while len(records) < max_limit:
            rows = cursor.fetchmany(self.fetch_batch_size)
            if not rows:
                break

            for row in rows:
                stats.total_rows_read += 1
                w_val = row[config.word_col]
                def_val = row[config.definition_col]

                w_str = str(w_val).strip() if w_val is not None else ""
                def_str = str(def_val).strip() if def_val is not None else ""

                if not w_str or not def_str:
                    stats.skipped_records += 1
                    stats.skip_reasons["Trường từ vựng hoặc định nghĩa bị rỗng/NULL"] = (
                        stats.skip_reasons.get("Trường từ vựng hoặc định nghĩa bị rỗng/NULL", 0) + 1
                    )
                    continue

                ipa_str = str(row[config.ipa_col]).strip() if config.ipa_col and row[config.ipa_col] is not None else ""
                pos_str = str(row[config.pos_col]).strip() if config.pos_col and row[config.pos_col] is not None else ""
                ex_str = str(row[config.example_col]).strip() if config.example_col and row[config.example_col] is not None else ""
                ex_tr_str = str(row[config.example_trans_col]).strip() if config.example_trans_col and row[config.example_trans_col] is not None else ""
                lvl_str = str(row[config.level_col]).strip().upper() if config.level_col and row[config.level_col] is not None else ""

                custom_id_val = row[config.id_col] if config.id_col and row[config.id_col] is not None else ""
                custom_id = str(custom_id_val).strip() if custom_id_val is not None else ""

                # Định dạng câu hỏi chuẩn hóa
                question_text = f"Nghĩa của từ {w_str} là gì?"
                answer_text = format_vocab_record_answer(
                    word=w_str,
                    definition=def_str,
                    ipa=ipa_str or None,
                    pos=pos_str or None,
                    example=ex_str or None,
                    example_trans=ex_tr_str or None,
                    level=lvl_str or None,
                )

                rec_id = generate_stable_record_id(clean_src, question_text, custom_id=custom_id or None)
                records.append(QARecord(
                    record_id=rec_id,
                    word=w_str,
                    sheet=config.primary_table,
                    source=clean_src,
                    level=lvl_str,
                    question=question_text,
                    answer=answer_text,
                    normalized_question=normalize_vietnamese_text(question_text),
                ))

                if len(records) >= max_limit:
                    break

        return records

    def _load_relational_mode(
        self,
        conn: sqlite3.Connection,
        file_path: Path,
        config: SQLiteMappingConfig,
        schema: SQLiteSchemaInfo,
        start_index: int,
        stats: SQLiteIngestionStats,
    ) -> List[QARecord]:
        """Xử lý nạp dữ liệu phân tán giữa nhiều bảng qua Khóa ngoại (Relational Join).
        
        Để tránh nhân bản dữ liệu định nghĩa và ví dụ (Cartesian explosion), hệ thống
        thực hiện gom nhóm (grouping) các bản ghi bảng con theo khóa của bảng cha.
        """
        p_table = config.primary_table
        r_table = config.related_table
        if not r_table or r_table not in schema.tables:
            raise DataLoadError(f"Bảng liên kết '{r_table}' không tồn tại trong tệp SQLite '{file_path.name}'.")

        p_info = schema.tables[p_table]
        r_info = schema.tables[r_table]
        p_cols = {c.name for c in p_info.columns}
        r_cols = {c.name for c in r_info.columns}

        # Xác định khóa liên kết (FK / PK)
        fk_child = config.foreign_key_child_col
        fk_parent = config.foreign_key_parent_col or "id"

        if not fk_child:
            # Tự động tìm khóa ngoại từ schema của bảng con sang bảng cha
            for fk in r_info.foreign_keys:
                if fk.table.lower() == p_table.lower():
                    fk_child = fk.from_col
                    fk_parent = fk.to_col or "id"
                    break

        if not fk_child or fk_child not in r_cols:
            raise DataLoadError(
                f"Không thể xác định khóa ngoại an toàn giữa '{r_table}' và '{p_table}'. "
                f"Vui lòng chỉ định cột khóa liên kết phù hợp."
            )

        if fk_parent not in p_cols:
            raise DataLoadError(f"Cột khóa chính '{fk_parent}' không tồn tại trong bảng '{p_table}'.")

        # Xác định các cột ánh xạ
        word_col = config.word_col
        if not word_col or word_col not in p_cols:
            raise DataLoadError(f"Cột từ vựng '{word_col}' không tồn tại trong bảng chính '{p_table}'.")

        def_col = config.definition_col
        if not def_col or def_col not in r_cols:
            raise DataLoadError(f"Cột định nghĩa '{def_col}' không tồn tại trong bảng liên kết '{r_table}'.")

        escaped_p = escape_sql_identifier(p_table)
        escaped_r = escape_sql_identifier(r_table)
        escaped_fk_p = escape_sql_identifier(fk_parent)
        escaped_fk_c = escape_sql_identifier(fk_child)

        # Xây dựng câu truy vấn an toàn kết hợp 2 bảng
        p_select_cols = [f"p.{escape_sql_identifier(fk_parent)} AS __p_id", f"p.{escape_sql_identifier(word_col)} AS __p_word"]
        if config.level_col and config.level_col in p_cols:
            p_select_cols.append(f"p.{escape_sql_identifier(config.level_col)} AS __p_level")
        if config.ipa_col and config.ipa_col in p_cols:
            p_select_cols.append(f"p.{escape_sql_identifier(config.ipa_col)} AS __p_ipa")
        if config.id_col and config.id_col in p_cols:
            p_select_cols.append(f"p.{escape_sql_identifier(config.id_col)} AS __p_custom_id")

        r_select_cols = [f"r.{escape_sql_identifier(def_col)} AS __r_def"]
        if config.pos_col and config.pos_col in r_cols:
            r_select_cols.append(f"r.{escape_sql_identifier(config.pos_col)} AS __r_pos")
        if config.example_col and config.example_col in r_cols:
            r_select_cols.append(f"r.{escape_sql_identifier(config.example_col)} AS __r_example")

        all_select = ", ".join(p_select_cols + r_select_cols)
        query = (
            f"SELECT {all_select} "
            f"FROM {escaped_p} p "
            f"LEFT JOIN {escaped_r} r ON p.{escaped_fk_p} = r.{escaped_fk_c} "
            f"ORDER BY p.{escaped_fk_p};"
        )

        cursor = conn.cursor()
        cursor.execute(query)

        # Gom nhóm theo parent ID để tránh nhân bản bản ghi
        grouped_parents: Dict[Any, Dict[str, Any]] = {}
        max_limit = config.max_records or self.max_records_limit

        while len(grouped_parents) < max_limit:
            rows = cursor.fetchmany(self.fetch_batch_size)
            if not rows:
                break

            for row in rows:
                stats.total_rows_read += 1
                p_id = row["__p_id"]
                word_val = row["__p_word"]
                word_str = str(word_val).strip() if word_val is not None else ""

                if not word_str:
                    stats.skipped_records += 1
                    stats.skip_reasons["Từ vựng ở bảng chính bị rỗng/NULL"] = (
                        stats.skip_reasons.get("Từ vựng ở bảng chính bị rỗng/NULL", 0) + 1
                    )
                    continue

                if p_id not in grouped_parents:
                    if len(grouped_parents) >= max_limit:
                        break
                    lvl_val = row["__p_level"] if "__p_level" in row.keys() else ""
                    ipa_val = row["__p_ipa"] if "__p_ipa" in row.keys() else ""
                    cid_val = row["__p_custom_id"] if "__p_custom_id" in row.keys() else ""

                    grouped_parents[p_id] = {
                        "word": word_str,
                        "level": str(lvl_val).strip().upper() if lvl_val is not None else "",
                        "ipa": str(ipa_val).strip() if ipa_val is not None else "",
                        "custom_id": str(cid_val).strip() if cid_val is not None else "",
                        "definitions": []
                    }

                # Thêm định nghĩa từ bảng liên kết (nếu có)
                def_val = row["__r_def"]
                def_str = str(def_val).strip() if def_val is not None else ""
                if def_str:
                    pos_val = row["__r_pos"] if "__r_pos" in row.keys() else ""
                    ex_val = row["__r_example"] if "__r_example" in row.keys() else ""
                    grouped_parents[p_id]["definitions"].append({
                        "definition": def_str,
                        "pos": str(pos_val).strip() if pos_val is not None else "",
                        "example": str(ex_val).strip() if ex_val is not None else "",
                    })

        # Tổng hợp các nhóm thành danh sách QARecord chuẩn hóa
        records: List[QARecord] = []
        clean_src = clean_source_name(file_path.name)

        for p_id, item in grouped_parents.items():
            word_str = item["word"]
            defs = item["definitions"]
            if not defs:
                stats.skipped_records += 1
                stats.skip_reasons["Từ không có định nghĩa nào trong bảng liên kết"] = (
                    stats.skip_reasons.get("Từ không có định nghĩa nào trong bảng liên kết", 0) + 1
                )
                continue

            # Xây dựng câu trả lời tổng hợp gọn gàng
            answer_parts: List[str] = []
            if item["level"]:
                answer_parts.append(f"Trình độ: {item['level']}")
            if item["ipa"]:
                ipa_clean = item["ipa"]
                if not ipa_clean.startswith("/"):
                    ipa_clean = f"/{ipa_clean}"
                if not ipa_clean.endswith("/"):
                    ipa_clean = f"{ipa_clean}/"
                answer_parts.append(f"Phát âm: {ipa_clean}")

            # Nhóm định nghĩa theo từ loại (POS)
            by_pos: Dict[str, List[Dict[str, str]]] = {}
            for d in defs:
                p_key = d["pos"] or "Chung"
                by_pos.setdefault(p_key, []).append(d)

            for p_key, def_list in by_pos.items():
                pos_header = f"Từ loại: {p_key}\n" if p_key != "Chung" else ""
                lines = [f"{pos_header}Định nghĩa:"]
                for idx, d_item in enumerate(def_list[:4], 1):
                    prefix = f"{idx}. " if len(def_list) > 1 else ""
                    d_line = f"{prefix}{d_item['definition']}"
                    if d_item["example"]:
                        d_line += f"\n   • Ví dụ: {d_item['example']}"
                    lines.append(d_line)
                answer_parts.append("\n".join(lines))

            question_text = f"Nghĩa của từ {word_str} là gì?"
            combined_answer = "\n\n".join(answer_parts)
            rec_id = generate_stable_record_id(clean_src, question_text, custom_id=item["custom_id"] or None)

            records.append(QARecord(
                record_id=rec_id,
                word=word_str,
                sheet=f"{p_table}+{r_table}",
                source=clean_src,
                level=item["level"],
                question=question_text,
                answer=combined_answer,
                normalized_question=normalize_vietnamese_text(question_text),
            ))

        return records
