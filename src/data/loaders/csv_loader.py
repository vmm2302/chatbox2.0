"""Bộ nạp tệp dữ liệu dạng bảng CSV (.csv)."""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)


class CSVLoader(BaseFileLoader):
    """Xử lý tệp bảng dữ liệu CSV với khả năng tự động nhận diện encoding và delimiter."""

    SUPPORTED_EXTENSIONS = ["csv"]

    @staticmethod
    def _read_csv_lines(file_path: Path) -> List[List[str]]:
        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        raw_text = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw_text = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if raw_text is None:
            raise DataLoadError(f"Không thể giải mã tệp CSV '{file_path.name}' bằng các bảng mã thông dụng.")

        lines = raw_text.splitlines()
        if not lines:
            return []

        # Tự động nhận diện dấu phân cách (delimiter)
        first_line = lines[0]
        delimiter = ","
        for d in [",", ";", "\t", "|"]:
            if first_line.count(d) > first_line.count(delimiter):
                delimiter = d

        reader = csv.reader(lines, delimiter=delimiter)
        rows: List[List[str]] = []
        for r in reader:
            cleaned = [c.strip() for c in r]
            if any(cleaned):
                rows.append(cleaned)
        return rows

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        rows = self._read_csv_lines(file_path)
        if not rows:
            return []

        first_row = rows[0]
        col_map = QALoader._detect_column_mapping(first_row)
        data_rows = rows[1:] if col_map is not None else rows

        if col_map is None:
            if len(first_row) >= 2:
                col_map = {"question": 0, "answer": 1}
                if len(first_row) >= 3:
                    col_map["word"] = 2
                if len(first_row) >= 4:
                    col_map["level"] = 3
                if len(first_row) >= 5:
                    col_map["source"] = 4
            else:
                raise DataLoadError(f"Tệp CSV '{file_path.name}' phải có ít nhất 2 cột (Câu hỏi, Câu trả lời).")

        records: List[QARecord] = []
        q_idx = col_map.get("question", 0)
        a_idx = col_map.get("answer", 1)
        w_idx = col_map.get("word")
        lvl_idx = col_map.get("level")
        src_idx = col_map.get("source")

        for r_idx, row in enumerate(data_rows, start_index):
            if len(row) <= max(q_idx, a_idx):
                continue

            question = row[q_idx].strip()
            answer = row[a_idx].strip()
            if not question or not answer:
                continue

            # Bỏ qua nếu dòng dữ liệu là tiêu đề lặp lại
            if normalize_vietnamese_text(question) in ["cau hoi", "question"]:
                continue

            word = row[w_idx].strip() if w_idx is not None and w_idx < len(row) else ""
            level = row[lvl_idx].strip().upper() if lvl_idx is not None and lvl_idx < len(row) else ""
            source = row[src_idx].strip() if src_idx is not None and src_idx < len(row) and row[src_idx].strip() else file_path.name

            # Fallback regex nếu thiếu từ hoặc trình độ
            ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(question, answer)
            if not word:
                word = ext_w
            if not level:
                level = ext_lvl

            rec_id = f"CSV_{file_path.stem[:8]}_{len(records) + start_index:04d}"
            records.append(QARecord(
                record_id=rec_id,
                word=word,
                sheet="CSV_DATA",
                source=source,
                level=level,
                question=question,
                answer=answer,
                normalized_question=normalize_vietnamese_text(question),
            ))

        logger.info("CSVLoader: Nạp thành công %d bản ghi từ %s", len(records), file_path.name)
        return records
