"""Bộ nạp tệp tài liệu Microsoft Word (.docx) thuần Python stdlib (zipfile + XML)."""

import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)

DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class DocxLoader(BaseFileLoader):
    """Xử lý tệp tài liệu Microsoft Word .docx qua thư viện chuẩn Python (zipfile + OpenXML)."""

    SUPPORTED_EXTENSIONS = ["docx"]

    @classmethod
    def _parse_docx_xml(cls, z: zipfile.ZipFile) -> Tuple[List[Tuple[str, str]], List[List[List[str]]]]:
        """Trích xuất danh sách đoạn văn (kèm tiêu đề section) và các bảng dữ liệu trong Word."""
        if "word/document.xml" not in z.namelist():
            raise DataLoadError("Tệp DOCX không hợp lệ (thiếu word/document.xml).")

        tree = ET.fromstring(z.read("word/document.xml"))
        paragraphs: List[Tuple[str, str]] = []  # (section_title, text)
        current_section = "General"

        # 1. Trích xuất các đoạn văn và bảng
        tables: List[List[List[str]]] = []

        # Xử lý các phần tử con trực tiếp của body
        body = tree.find(".//w:body", DOCX_NS)
        if body is None:
            return [], []

        for child in body:
            tag = child.tag.split("}")[-1]

            # Đoạn văn
            if tag == "p":
                # Kiểm tra xem có phải tiêu đề heading không
                style = child.find(".//w:pStyle", DOCX_NS)
                is_heading = False
                if style is not None:
                    val = style.attrib.get(f"{{{DOCX_NS['w']}}}val", "")
                    if "heading" in val.lower() or "title" in val.lower():
                        is_heading = True

                texts = [node.text for node in child.findall(".//w:t", DOCX_NS) if node.text]
                p_text = "".join(texts).strip()

                if p_text:
                    if is_heading:
                        current_section = p_text
                    paragraphs.append((current_section, p_text))

            # Bảng
            elif tag == "tbl":
                table_rows: List[List[str]] = []
                for tr in child.findall(".//w:tr", DOCX_NS):
                    row_cells: List[str] = []
                    for tc in tr.findall(".//w:tc", DOCX_NS):
                        cell_texts = [node.text for node in tc.findall(".//w:t", DOCX_NS) if node.text]
                        row_cells.append("".join(cell_texts).strip())
                    if any(row_cells):
                        table_rows.append(row_cells)
                if table_rows:
                    tables.append(table_rows)

        return paragraphs, tables

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        records: List[QARecord] = []

        try:
            with zipfile.ZipFile(file_path, "r") as z:
                paragraphs, tables = self._parse_docx_xml(z)
        except Exception as exc:
            raise DataLoadError(f"Lỗi khi đọc tệp DOCX '{file_path.name}': {exc}") from exc

        # 1. Ưu tiên xử lý bảng dữ liệu nếu có trong Word
        for tbl_idx, rows in enumerate(tables, 1):
            if len(rows) >= 2:
                first_row = rows[0]
                col_map = QALoader._detect_column_mapping(first_row)
                data_rows = rows[1:] if col_map is not None else rows

                if col_map is None and len(first_row) >= 2:
                    col_map = {"question": 0, "answer": 1}

                if col_map is not None:
                    q_idx = col_map.get("question", 0)
                    a_idx = col_map.get("answer", 1)
                    w_idx = col_map.get("word")
                    lvl_idx = col_map.get("level")

                    for row in data_rows:
                        if len(row) > max(q_idx, a_idx):
                            q = row[q_idx].strip()
                            a = row[a_idx].strip()
                            if q and a:
                                w = row[w_idx].strip() if w_idx is not None and w_idx < len(row) else ""
                                lvl = row[lvl_idx].strip().upper() if lvl_idx is not None and lvl_idx < len(row) else ""
                                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, a)
                                rec_id = f"DOCX_{file_path.stem[:8]}_{len(records) + start_index:04d}"
                                records.append(QARecord(
                                    record_id=rec_id,
                                    word=w or ext_w,
                                    sheet=f"TABLE_{tbl_idx}",
                                    source=file_path.name,
                                    level=lvl or ext_lvl,
                                    question=q,
                                    answer=a,
                                    normalized_question=normalize_vietnamese_text(q),
                                ))

        # Nếu đã bóc tách được các bản ghi từ bảng, trả về kết quả
        if records:
            logger.info("DocxLoader: Nạp thành công %d bản ghi từ các bảng trong %s", len(records), file_path.name)
            return records

        # 2. Xử lý các đoạn văn bản (Paragraphs)
        entry_pattern = re.compile(r"^#*\s*([a-zA-Z\s\-]{2,30})\s*[:\-–]\s*(.+)$")
        for section, p_text in paragraphs:
            if len(p_text) < 15:
                continue

            m = entry_pattern.match(p_text)
            if m:
                term = m.group(1).strip()
                meaning = m.group(2).strip()
                q = f"{term} nghĩa là gì?"
                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, meaning)
                rec_id = f"DOCX_{file_path.stem[:8]}_{len(records) + start_index:04d}"
                records.append(QARecord(
                    record_id=rec_id,
                    word=ext_w or term,
                    sheet=section,
                    source=file_path.name,
                    level=ext_lvl,
                    question=q,
                    answer=meaning,
                    normalized_question=normalize_vietnamese_text(q),
                ))
            else:
                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(p_text, p_text)
                first_sentence = p_text.split(".")[0][:80].strip()
                q = f"Thông tin về '{ext_w}' ({section})" if ext_w else f"{section}: {first_sentence}"
                rec_id = f"DOCX_{file_path.stem[:8]}_{len(records) + start_index:04d}"
                records.append(QARecord(
                    record_id=rec_id,
                    word=ext_w,
                    sheet=section,
                    source=file_path.name,
                    level=ext_lvl,
                    question=q,
                    answer=p_text,
                    normalized_question=normalize_vietnamese_text(q),
                ))

        logger.info("DocxLoader: Nạp thành công %d bản ghi từ %s", len(records), file_path.name)
        return records
