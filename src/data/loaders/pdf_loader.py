"""Bộ nạp tệp tài liệu PDF (.pdf) nâng cao sử dụng PyMuPDF / pypdf.

Tính năng:
- Bóc tách theo từng trang (Page-level Metadata: sheet="Trang X").
- Nhận diện và sắp xếp thứ tự đọc tự nhiên cho tài liệu 2 cột và nhiều cột (Multi-column reading order).
- Phân biệt trang Text, trang Scan/Ảnh, và PDF kết hợp (Mixed text + scan).
- Hỗ trợ OCR local khi cần (pytesseract) kèm thông báo cảnh báo rõ ràng nếu thiếu engine OCR.
- Tuyệt đối không drop âm thầm trang scan, bảng biểu, hay các đoạn text ngắn (<15 ký tự).
- Nhận diện Oxford 3000 hoàn toàn dựa trên cấu trúc nội dung, không phụ thuộc tên tệp.
"""

import io
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash, generate_stable_record_id

logger = logging.getLogger(__name__)


class PDFLoader(BaseFileLoader):
    """Xử lý tệp tài liệu PDF với tính năng trích xuất đa cột, phân trang và OCR fallback."""

    SUPPORTED_EXTENSIONS = ["pdf"]

    @classmethod
    def _sort_page_blocks(cls, blocks: list, page_width: float) -> str:
        """Sắp xếp các khối văn bản theo thứ tự đọc tự nhiên cho tài liệu 1 cột, 2 cột và nhiều cột."""
        text_blocks = [b for b in blocks if len(b) > 4 and b[4].strip() and (len(b) <= 6 or b[6] == 0)]
        if not text_blocks:
            return ""

        mid = page_width / 2.0
        full_width = []
        left_col = []
        right_col = []

        for b in text_blocks:
            x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
            # Nếu khối văn bản trải dài qua cả 2 nửa trang -> Khối toàn trang (tiêu đề, phân cách)
            if x0 < mid - 40 and x1 > mid + 40:
                full_width.append(b)
            elif x1 <= mid + 20:
                left_col.append(b)
            elif x0 >= mid - 20:
                right_col.append(b)
            else:
                # Gần ranh giới giữa: phân chia theo trọng tâm
                if (x0 + x1) / 2.0 < mid:
                    left_col.append(b)
                else:
                    right_col.append(b)

        # Kiểm tra xem trang có cấu trúc 2 cột rõ rệt không
        has_two_columns = (
            len(left_col) > 0
            and len(right_col) > 0
            and (len(left_col) + len(right_col) >= len(text_blocks) * 0.6)
        )

        if has_two_columns:
            min_col_y = min(min(b[1] for b in left_col), min(b[1] for b in right_col))
            max_col_y = max(max(b[3] for b in left_col), max(b[3] for b in right_col))

            top_headers = sorted([b for b in full_width if b[3] <= min_col_y + 10], key=lambda b: (b[1], b[0]))
            bottom_footers = sorted([b for b in full_width if b[1] >= max_col_y - 10], key=lambda b: (b[1], b[0]))
            mid_headers = sorted(
                [b for b in full_width if b not in top_headers and b not in bottom_footers],
                key=lambda b: (b[1], b[0])
            )

            left_sorted = sorted(left_col, key=lambda b: (b[1], b[0]))
            right_sorted = sorted(right_col, key=lambda b: (b[1], b[0]))

            ordered_blocks = top_headers + mid_headers + left_sorted + right_sorted + bottom_footers
            return "\n\n".join(b[4].strip() for b in ordered_blocks if b[4].strip())

        # Nếu là 1 cột thông thường hoặc bố cục tự do: sắp xếp top-to-bottom, left-to-right
        ordered_blocks = sorted(text_blocks, key=lambda b: (b[1], b[0]))
        return "\n\n".join(b[4].strip() for b in ordered_blocks if b[4].strip())

    @classmethod
    def _try_ocr_page(cls, page, page_num: int, file_name: str) -> str:
        """Thử trích xuất văn bản từ trang scan/ảnh bằng OCR local (pytesseract)."""
        try:
            import pytesseract
            from PIL import Image

            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang="vie+eng")
            if text and text.strip():
                logger.info("PDFLoader: OCR thành công trang %d của '%s' (%d ký tự)", page_num, file_name, len(text.strip()))
                return text.strip()
        except ImportError:
            pass
        except Exception as ocr_err:
            logger.debug("PDFLoader: OCR không khả dụng cho trang %d của '%s': %s", page_num, file_name, ocr_err)
        return ""

    @classmethod
    def _extract_text_by_pages(cls, file_path: Path) -> List[Tuple[int, str]]:
        """Trích xuất văn bản theo từng trang từ PDF qua PyMuPDF hoặc pypdf fallback.

        Xử lý trang text thường, trang nhiều cột, trang scan có OCR hoặc cảnh báo thiếu OCR engine.
        """
        pages: List[Tuple[int, str]] = []
        scanned_pages_without_ocr: List[int] = []

        # 1. Thử nghiệm PyMuPDF trước (Tốc độ cao, hỗ trợ phân tích block đa cột & trích xuất ảnh)
        try:
            import pymupdf  # PyMuPDF
            doc = pymupdf.open(str(file_path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("blocks")
                page_text = cls._sort_page_blocks(blocks, page.rect.width)

                if page_text.strip():
                    pages.append((page_num + 1, page_text.strip()))
                else:
                    # Trang không có lớp văn bản (Text Layer) -> Thử OCR
                    ocr_res = cls._try_ocr_page(page, page_num + 1, file_path.name)
                    if ocr_res.strip():
                        pages.append((page_num + 1, ocr_res.strip()))
                    else:
                        scanned_pages_without_ocr.append(page_num + 1)
                        # Không bỏ qua âm thầm! Lưu giữ placeholder rõ ràng kèm số trang
                        note = (
                            f"[Trang {page_num + 1}: Trang tài liệu dạng scan/hình ảnh. "
                            "Chưa cấu hình công cụ OCR local (Tesseract OCR) để trích xuất tự động]"
                        )
                        pages.append((page_num + 1, note))
            doc.close()

            if scanned_pages_without_ocr:
                logger.warning(
                    "PDFLoader: Tệp '%s' có %d trang scan/ảnh (Trang: %s) chưa được OCR "
                    "do thiếu công cụ Tesseract OCR trên máy.",
                    file_path.name,
                    len(scanned_pages_without_ocr),
                    ", ".join(map(str, scanned_pages_without_ocr))
                )

            # Nếu tất cả các trang đều là scan và không có OCR
            if pages and len(scanned_pages_without_ocr) == len(pages):
                raise DataLoadError(
                    f"Tệp PDF '{file_path.name}' chỉ chứa trang scan/hình ảnh nhưng hệ thống "
                    "chưa cài đặt công cụ OCR local (Tesseract OCR). Vui lòng cài đặt Tesseract để trích xuất tự động."
                )

            if pages:
                return pages
        except DataLoadError:
            raise
        except Exception as e:
            logger.warning("PyMuPDF không thể đọc %s (%s), thử chuyển sang pypdf...", file_path.name, e)

        # 2. Fallback sang pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((page_num, text.strip()))
                else:
                    note = f"[Trang {page_num}: Trang tài liệu dạng scan/hình ảnh]"
                    pages.append((page_num, note))
            if pages:
                return pages
        except Exception as exc:
            raise DataLoadError(f"Không thể trích xuất văn bản từ tệp PDF '{file_path.name}': {exc}") from exc

        if not pages:
            raise DataLoadError(f"Tệp PDF '{file_path.name}' không chứa nội dung văn bản có thể trích xuất.")

        return pages

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        file_path = Path(file_path)
        f_hash = file_hash or compute_file_hash(file_path)

        # 1. Trích xuất văn bản theo từng trang
        pages_text = self._extract_text_by_pages(file_path)

        # 2. Nhận diện tài liệu Oxford 3000 hoàn toàn dựa trên cấu trúc nội dung (Content-based detection)
        # Tuyệt đối không chuyển hướng sang Oxford parser chỉ vì tên tệp chứa chữ 'oxford'
        if pages_text:
            first_pages_sample = " ".join(p[1].lower() for p in pages_text[:3])
            has_oxford_brand = ("oxford 3000" in first_pages_sample or "the oxford 3000" in first_pages_sample or "oxford 5000" in first_pages_sample)
            has_cefr_levels = any(re.search(rf"\b{lvl}\b", first_pages_sample) for lvl in ["a1", "a2", "b1", "b2", "c1", "c2"])
            if has_oxford_brand and has_cefr_levels:
                logger.info("PDFLoader: Phát hiện tài liệu danh mục Oxford 3000 theo nội dung trong '%s'", file_path.name)
                from src.data.loaders.oxford_pdf_loader import OxfordPDFParser
                return OxfordPDFParser().load(file_path, f_hash, start_index)

        records: List[QARecord] = []
        seen_rec_ids: set = set()

        entry_pattern = re.compile(r"^#*\s*([a-zA-Z\s\-]{2,30})\s*[:\-–]\s*(.+)$")

        for page_num, text in pages_text:
            # Phân tách theo đoạn văn hoặc dòng định nghĩa trong trang
            raw_chunks = [c.strip() for c in re.split(r"\n\s*\n+", text) if c.strip()]
            paragraphs = []
            for chunk in raw_chunks:
                lines = [l.strip() for l in chunk.splitlines() if l.strip()]
                if len(lines) > 1 and any(entry_pattern.match(l) for l in lines):
                    paragraphs.extend(lines)
                else:
                    paragraphs.append(chunk)

            for p_idx, p in enumerate(paragraphs, 1):
                # Không bỏ qua âm thầm các đoạn ngắn, bảng biểu hay tiêu đề
                if not p:
                    continue

                m = entry_pattern.match(p)
                if m:
                    term = m.group(1).strip()
                    meaning = m.group(2).strip()
                    q = f"{term} nghĩa là gì?"
                    ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q, meaning)
                    rec_id = generate_stable_record_id(file_path.name, q)
                    if rec_id in seen_rec_ids:
                        rec_id = generate_stable_record_id(file_path.name, f"{q} (Trang {page_num} #{p_idx})")
                    seen_rec_ids.add(rec_id)

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
                    if ext_w:
                        q = f"Thông tin về '{ext_w}' (Trang {page_num})"
                    else:
                        q = f"Nội dung từ {file_path.name} (Trang {page_num}): {first_line}"

                    rec_id = generate_stable_record_id(file_path.name, f"Trang {page_num}:{p_idx}:{first_line}")
                    if rec_id in seen_rec_ids:
                        rec_id = generate_stable_record_id(file_path.name, f"Trang {page_num}:{p_idx}:{first_line}_{len(records)}")
                    seen_rec_ids.add(rec_id)

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
