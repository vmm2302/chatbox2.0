"""Bộ nạp tệp văn bản thuần TXT (.txt) và Markdown (.md)."""

import logging
import re
from pathlib import Path
from typing import List, Optional

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)


class TextLoader(BaseFileLoader):
    """Xử lý tệp văn bản .txt và .md với khả năng nhận diện mục từ và phân đoạn (chunking)."""

    SUPPORTED_EXTENSIONS = ["txt", "md"]

    @staticmethod
    def _read_text_content(file_path: Path) -> str:
        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except Exception:
                continue
        raise DataLoadError(f"Không thể đọc tệp văn bản '{file_path.name}'.")

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        content = self._read_text_content(file_path)
        if not content.strip():
            return []

        records: List[QARecord] = []

        # Phương án 1: Phát hiện cặp tường minh Q: ... và A: ... hoặc Hỏi: ... Trả lời: ...
        qa_blocks = re.split(r"\n(?=(?:[QqHh]ỏi|[Qq]uestion)\s*[:\-])", content)
        if len(qa_blocks) > 1 or re.search(r"^(?:[QqHh]ỏi|[Qq]uestion)\s*[:\-]", content):
            for idx, block in enumerate(qa_blocks, start_index):
                clean_b = block.strip()
                if not clean_b:
                    continue
                # Tách phần hỏi và phần trả lời
                parts = re.split(r"\n(?:[Aa]|[Tt]rả\s*lời|[Aa]nswer)\s*[:\-]", clean_b, maxsplit=1)
                if len(parts) == 2:
                    q = re.sub(r"^(?:[QqHh]ỏi|[Qq]uestion)\s*[:\-]\s*", "", parts[0]).strip()
                    a = parts[1].strip()
                    if q and a:
                        ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, a)
                        id_m = re.search(r"\[(?:id|record_id)\s*[:=]\s*([^\]]+)\]", clean_b, re.IGNORECASE)
                        custom_id = id_m.group(1).strip() if id_m else None
                        from src.data.loaders.base import generate_stable_record_id
                        rec_id = generate_stable_record_id(file_path.name, q, custom_id=custom_id)
                        records.append(QARecord(
                            record_id=rec_id,
                            word=ext_w,
                            sheet="TEXT_QA",
                            source=file_path.name,
                            level=ext_lvl,
                            question=q,
                            answer=a,
                            normalized_question=normalize_vietnamese_text(q),
                        ))
            if records:
                logger.info("TextLoader: Nhận diện %d cặp Q&A tường minh từ %s", len(records), file_path.name)
                return records

        # Phương án 2: Phát hiện mục từ từ điển (Dạng "Word: Definition" hoặc "Word - Definition" hoặc "## Word")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        entry_pattern = re.compile(r"^#*\s*([a-zA-Z0-9_\s\-]{2,50})\s*[:\-–]\s*(.+)$")
        candidate_entries = []
        pending_id = None

        for line in lines:
            id_m = re.match(r"^\[(?:id|record_id)\s*[:=]\s*([^\]]+)\]$", line, re.IGNORECASE)
            if id_m:
                pending_id = id_m.group(1).strip()
                continue
            m = entry_pattern.match(line)
            if m:
                term = m.group(1).strip()
                meaning = m.group(2).strip()
                cid = pending_id
                inline_id = re.search(r"\[(?:id|record_id)\s*[:=]\s*([^\]]+)\]", meaning, re.IGNORECASE)
                if inline_id:
                    cid = inline_id.group(1).strip()
                    meaning = re.sub(r"\[(?:id|record_id)\s*[:=]\s*[^\]]+\]", "", meaning).strip()
                if len(meaning) > 5:
                    candidate_entries.append((term, meaning, cid))
                pending_id = None

        if len(candidate_entries) >= 2 or (len(lines) <= 5 and candidate_entries):
            for idx, (term, meaning, cid) in enumerate(candidate_entries, start_index):
                q = f"{term} nghĩa là gì?"
                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, meaning)
                from src.data.loaders.base import generate_stable_record_id
                rec_id = generate_stable_record_id(file_path.name, q, custom_id=cid)
                records.append(QARecord(
                    record_id=rec_id,
                    word=ext_w or term,
                    sheet="DICTIONARY_ENTRIES",
                    source=file_path.name,
                    level=ext_lvl,
                    question=q,
                    answer=meaning,
                    normalized_question=normalize_vietnamese_text(q),
                ))
            if records:
                logger.info("TextLoader: Nhận diện %d mục từ từ điển từ %s", len(records), file_path.name)
                return records

        # Phương án 3: Phân đoạn đoạn văn tự nhiên (Paragraph Chunking)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", content) if p.strip()]
        for idx, p in enumerate(paragraphs, start_index):
            if len(p) < 20:
                continue
            first_line = p.splitlines()[0][:80].strip()
            ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(p, p)
            q = f"Thông tin về '{ext_w}' trong {file_path.name}" if ext_w else f"Nội dung từ {file_path.name}: {first_line}"
            from src.data.loaders.base import generate_stable_record_id
            rec_id = generate_stable_record_id(file_path.name, f"{idx}:{first_line}")
            records.append(QARecord(
                record_id=rec_id,
                word=ext_w,
                sheet="TEXT_CHUNKS",
                source=file_path.name,
                level=ext_lvl,
                question=q,
                answer=p,
                normalized_question=normalize_vietnamese_text(q),
            ))

        logger.info("TextLoader: Phân đoạn thành %d bản ghi từ %s", len(records), file_path.name)
        return records
