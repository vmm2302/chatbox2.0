"""Bộ nạp tệp tài liệu PDF (.pdf) sử dụng PyMuPDF / pypdf."""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)


class PDFLoader(BaseFileLoader):
    """Xử lý tệp tài liệu PDF với tính năng trích xuất phân trang (Page-level Metadata)."""

    SUPPORTED_EXTENSIONS = ["pdf"]

    @classmethod
    def _extract_text_by_pages(cls, file_path: Path) -> List[Tuple[int, str]]:
        """Trích xuất văn bản theo từng trang từ PDF qua PyMuPDF hoặc pypdf fallback."""
        pages: List[Tuple[int, str]] = []

        # Thử nghiệm PyMuPDF trước (Tốc độ cao và giữ cấu trúc tốt)
        try:
            import pymupdf  # PyMuPDF
            doc = pymupdf.open(str(file_path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    pages.append((page_num + 1, text.strip()))
            doc.close()
            if pages:
                return pages
        except Exception as e:
            logger.warning("PyMuPDF không thể đọc %s (%s), thử chuyển sang pypdf...", file_path.name, e)

        # Fallback sang pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((page_num, text.strip()))
            if pages:
                return pages
        except Exception as exc:
            raise DataLoadError(f"Không thể trích xuất văn bản từ tệp PDF '{file_path.name}': {exc}") from exc

        if not pages:
            raise DataLoadError(f"Tệp PDF '{file_path.name}' không chứa nội dung văn bản có thể trích xuất (có thể là tệp scan hoặc ảnh).")

        return pages

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        pages_text = self._extract_text_by_pages(file_path)
        records: List[QARecord] = []

        entry_pattern = re.compile(r"^#*\s*([a-zA-Z\s\-]{2,30})\s*[:\-–]\s*(.+)$")

        for page_num, text in pages_text:
            # Phân tách theo dòng / đoạn văn trong trang
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]

            for p in paragraphs:
                if len(p) < 15:
                    continue

                m = entry_pattern.match(p)
                if m:
                    term = m.group(1).strip()
                    meaning = m.group(2).strip()
                    q = f"{term} nghĩa là gì?"
                    ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, meaning)
                    from src.data.loaders.base import generate_stable_record_id
                    rec_id = generate_stable_record_id(file_path.name, q)
                    records.append(QARecord(
                        record_id=rec_id,
                        word=ext_w or term,
                        sheet=f"Trang {page_num}",
                        source=file_path.name,
                        level=ext_lvl,
                        question=q,
                        answer=meaning,
                        normalized_question=normalize_vietnamese_text(q),
                    ))
                else:
                    ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(p, p)
                    first_line = p.splitlines()[0][:80].strip()
                    q = f"Thông tin về '{ext_w}' (Trang {page_num})" if ext_w else f"Nội dung từ {file_path.name} (Trang {page_num}): {first_line}"
                    from src.data.loaders.base import generate_stable_record_id
                    rec_id = generate_stable_record_id(file_path.name, f"Trang {page_num}:{first_line}")
                    records.append(QARecord(
                        record_id=rec_id,
                        word=ext_w,
                        sheet=f"Trang {page_num}",
                        source=file_path.name,
                        level=ext_lvl,
                        question=q,
                        answer=p,
                        normalized_question=normalize_vietnamese_text(q),
                    ))

        logger.info("PDFLoader: Nạp thành công %d bản ghi từ %s qua %d trang", len(records), file_path.name, len(pages_text))
        return records
