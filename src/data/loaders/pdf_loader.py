"""Bộ nạp và trích xuất dữ liệu tệp PDF (.pdf) đáng tin cậy cho RAG cục bộ.

Hỗ trợ:
1. Trích xuất văn bản phân trang bảo toàn cấu trúc (PyMuPDF / pypdf fallback).
2. Tự động nhận diện và trích xuất bảng từ vựng (Table Extraction qua PyMuPDF find_tables).
3. Đánh giá chất lượng văn bản từng trang; tự động phát hiện trang scan/ảnh cần OCR.
4. Tích hợp OCRHandler cục bộ (Tesseract OCR), có hướng dẫn cài đặt nếu chưa có.
5. Chuẩn hóa Unicode NFC, bảo toàn 100% tiếng Việt có dấu, ký hiệu ngữ âm IPA.
6. Phân tích mục từ vựng đa dòng (Multi-line Entry Parser) & chunking an toàn có overlap.
7. Báo cáo thống kê trích xuất minh bạch cho từng phiên nạp.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash, generate_stable_record_id
from src.data.loaders.ocr_handler import OCRHandler

logger = logging.getLogger(__name__)


@dataclass
class PageExtractionResult:
    """Kết quả trích xuất chi tiết của một trang PDF."""
    page_num: int
    text: str = ""
    char_count: int = 0
    tables: List[List[List[str]]] = field(default_factory=list)
    needs_ocr: bool = False
    ocr_attempted: bool = False
    ocr_success: bool = False
    ocr_message: str = ""


class PDFLoader(BaseFileLoader):
    """Xử lý tệp PDF chuyên sâu cho hệ thống tra cứu RAG cục bộ."""

    SUPPORTED_EXTENSIONS = ["pdf"]
    MIN_TEXT_CHARS_PER_PAGE = 20  # Ngưỡng ký tự tối thiểu để coi một trang có text hợp lệ

    def __init__(self):
        self.last_extraction_report: Dict[str, Any] = {}

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Chuẩn hóa văn bản trích xuất:
        - Unicode NFC normalization (giữ toàn vẹn tiếng Việt và IPA).
        - Nối các từ bị ngắt dòng bằng dấu gạch ngang (hyphenation).
        - Chuẩn hóa khoảng trắng không phá vỡ cấu trúc xuống dòng cần thiết.
        """
        if not text:
            return ""

        # 1. Unicode NFC
        normalized = unicodedata.normalize("NFC", text)

        # 2. Xóa khoảng trắng đặc biệt và chuẩn hóa soft-hyphen (\xad)
        normalized = normalized.replace("\xad", "-").replace("\u00a0", " ").replace("\u200b", "")

        # 3. Nối từ bị ngắt dòng bởi dấu gạch nối (ví dụ: infor-\nmation -> information)
        normalized = re.sub(r"(\b[a-zA-Z]+)-\n+([a-zA-Z]+\b)", r"\1\2", normalized)

        # 4. Chuẩn hóa khoảng trắng dư thừa trong từng dòng nhưng giữ cấu trúc dòng
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()]

        # 5. Gộp các dòng trống liên tiếp thành tối đa 2 newline
        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

        return cleaned_text

    @classmethod
    def _extract_pages_content(cls, file_path: Path) -> List[PageExtractionResult]:
        """Trích xuất nội dung văn bản và bảng theo từng trang qua PyMuPDF hoặc pypdf."""
        pages_result: List[PageExtractionResult] = []

        # Thử nghiệm PyMuPDF trước (Tốc độ cao, hỗ trợ bảng và pixmap cho OCR)
        try:
            import pymupdf  # PyMuPDF
            doc = pymupdf.open(str(file_path))
            total_pages = len(doc)

            if total_pages == 0:
                doc.close()
                raise DataLoadError(f"Tệp PDF '{file_path.name}' rỗng (0 trang).")

            for page_num in range(1, total_pages + 1):
                page = doc[page_num - 1]
                p_res = PageExtractionResult(page_num=page_num)

                # 1. Trích xuất bảng nếu có
                try:
                    tabs = page.find_tables()
                    if tabs and tabs.tables:
                        for tab in tabs:
                            extracted_tab = tab.extract()
                            if extracted_tab and len(extracted_tab) > 1:
                                p_res.tables.append(extracted_tab)
                except Exception as tab_err:
                    logger.debug("Không thể trích xuất bảng ở trang %d: %s", page_num, tab_err)

                # 2. Trích xuất text thông thường
                raw_text = page.get_text("text") or ""
                clean_text = cls._normalize_text(raw_text)
                p_res.text = clean_text
                p_res.char_count = len(re.sub(r"\s+", "", clean_text))

                # 3. Kiểm tra chất lượng text: Nếu không có bảng và ký tự < ngưỡng -> Đánh dấu cần OCR
                if not p_res.tables and p_res.char_count < cls.MIN_TEXT_CHARS_PER_PAGE:
                    p_res.needs_ocr = True
                    # Kiểm tra OCR cục bộ
                    ocr_env = OCRHandler.check_environment()
                    if ocr_env["is_ready"]:
                        p_res.ocr_attempted = True
                        try:
                            pix = page.get_pixmap(dpi=150)
                            success, ocr_txt, msg = OCRHandler.ocr_pixmap(pix)
                            p_res.ocr_success = success
                            p_res.ocr_message = msg
                            if success and len(ocr_txt.strip()) >= cls.MIN_TEXT_CHARS_PER_PAGE:
                                p_res.text = cls._normalize_text(ocr_txt)
                                p_res.char_count = len(re.sub(r"\s+", "", p_res.text))
                                p_res.needs_ocr = False
                        except Exception as ocr_err:
                            p_res.ocr_success = False
                            p_res.ocr_message = f"Lỗi thực thi OCR: {ocr_err}"
                    else:
                        p_res.ocr_message = "Chưa cài đặt Tesseract OCR cục bộ."

                pages_result.append(p_res)

            doc.close()
            return pages_result

        except Exception as pymupdf_err:
            logger.warning("PyMuPDF gặp lỗi khi đọc %s (%s), thử chuyển sang pypdf...", file_path.name, pymupdf_err)

        # Fallback sang pypdf nếu PyMuPDF lỗi
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            total_pages = len(reader.pages)

            if total_pages == 0:
                raise DataLoadError(f"Tệp PDF '{file_path.name}' rỗng (0 trang).")

            for page_num, page in enumerate(reader.pages, 1):
                p_res = PageExtractionResult(page_num=page_num)
                raw_text = page.extract_text() or ""
                clean_text = cls._normalize_text(raw_text)
                p_res.text = clean_text
                p_res.char_count = len(re.sub(r"\s+", "", clean_text))
                if p_res.char_count < cls.MIN_TEXT_CHARS_PER_PAGE:
                    p_res.needs_ocr = True
                    p_res.ocr_message = "Trang không có text (pypdf fallback không hỗ trợ OCR)."
                pages_result.append(p_res)

            return pages_result

        except Exception as exc:
            raise DataLoadError(f"Không thể đọc tệp PDF '{file_path.name}': {exc}") from exc

    @classmethod
    def _parse_table_rows(
        cls,
        table: List[List[str]],
        page_num: int,
        source_name: str
    ) -> List[QARecord]:
        """Chuyển đổi dữ liệu bảng thành danh sách QARecord chuẩn hóa."""
        if not table or len(table) < 2:
            return []

        records: List[QARecord] = []
        headers = [h.strip() if h else "" for h in table[0]]
        norm_headers = [normalize_vietnamese_text(h) for h in headers]

        # Ánh xạ cột
        col_map: Dict[str, int] = {}
        for idx, h in enumerate(norm_headers):
            if not h:
                continue
            if any(k in h for k in ["tu vung", "word", "vocab", "tu tieng anh", "term", "tu", "t v ng"]):
                col_map.setdefault("word", idx)
            elif any(k in h for k in ["phat am", "phien am", "ipa", "pronunciation", "sound"]):
                col_map.setdefault("ipa", idx)
            elif any(k in h for k in ["trinh do", "cap do", "level", "cefr", "difficulty"]):
                col_map.setdefault("level", idx)
            elif any(k in h for k in ["tu loai", "pos", "part of speech", "loai tu", "loai", "type"]):
                col_map.setdefault("pos", idx)
            elif any(k in h for k in ["nghia", "nghia tieng viet", "dich", "meaning", "definition", "giai thich"]):
                col_map.setdefault("meaning", idx)
            elif any(k in h for k in ["vi du", "cau vi du", "example", "sentence", "vd"]):
                if "example" not in col_map:
                    col_map["example"] = idx
                elif "example_trans" not in col_map:
                    col_map["example_trans"] = idx
            elif any(k in h for k in ["dich vi du", "nghia vi du", "example translation", "dich vd"]):
                col_map.setdefault("example_trans", idx)

        # Nếu không nhận diện được cột cụ thể nhưng có ít nhất 2 cột
        if "word" not in col_map and len(headers) >= 2:
            col_map["word"] = 0
            col_map["meaning"] = 1
            if len(headers) >= 3:
                col_map["example"] = 2

        def _clean_cell(val: Optional[str]) -> str:
            if not val:
                return ""
            v = str(val).replace("\xad", "-")
            v = re.sub(r"\s*[\r\n]+\s*_\s*$", "", v)
            v = re.sub(r"[\r\n]+", " ", v)
            return re.sub(r"\s+", " ", v).strip()

        for r_idx, row in enumerate(table[1:], 1):
            if not any(cell and str(cell).strip() for cell in row):
                continue

            word = _clean_cell(row[col_map["word"]]) if "word" in col_map and col_map["word"] < len(row) else ""
            meaning = _clean_cell(row[col_map["meaning"]]) if "meaning" in col_map and col_map["meaning"] < len(row) else ""

            if not word and not meaning:
                continue

            # Lấy các trường bổ trợ
            ipa = _clean_cell(row[col_map["ipa"]]) if "ipa" in col_map and col_map["ipa"] < len(row) else ""
            level = _clean_cell(row[col_map["level"]]).upper() if "level" in col_map and col_map["level"] < len(row) else ""
            pos = _clean_cell(row[col_map["pos"]]) if "pos" in col_map and col_map["pos"] < len(row) else ""
            example = _clean_cell(row[col_map["example"]]) if "example" in col_map and col_map["example"] < len(row) else ""
            example_trans = _clean_cell(row[col_map["example_trans"]]) if "example_trans" in col_map and col_map["example_trans"] < len(row) else ""

            # Xây dựng câu trả lời giữ trọn vẹn quan hệ giữa từ vựng, phát âm, nghĩa và ví dụ
            answer_parts = []
            if word:
                answer_parts.append(f"**Từ tiếng Anh:** {word}")
            if ipa:
                answer_parts.append(f"**Phát âm:** {ipa}")
            if level:
                answer_parts.append(f"**Trình độ:** {level}")
            if pos:
                answer_parts.append(f"**Từ loại:** {pos}")
            if meaning:
                answer_parts.append(f"**Ý nghĩa:** {meaning}")
            if example:
                answer_parts.append(f"**Ví dụ:** {example}")
            if example_trans:
                answer_parts.append(f"**Dịch ví dụ:** {example_trans}")

            answer_str = "\n".join(answer_parts) if answer_parts else meaning
            question_str = f"{word} nghĩa là gì?" if word else f"Nội dung bảng (Trang {page_num}): {meaning[:60]}"

            rec_id = generate_stable_record_id(source_name, f"Trang {page_num}:table_{r_idx}:{word or meaning[:30]}")
            records.append(QARecord(
                record_id=rec_id,
                word=word,
                sheet=f"Trang {page_num}",
                source=source_name,
                level=level,
                question=question_str,
                answer=answer_str,
                normalized_question=normalize_vietnamese_text(question_str),
            ))

        return records

    @classmethod
    def _parse_multiline_vocab_entries(
        cls,
        text: str,
        page_num: int,
        source_name: str
    ) -> List[QARecord]:
        """Phân tích các mục từ vựng đa dòng (Dictionary & Vocabulary Blocks)."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []

        records: List[QARecord] = []

        # Nhận diện dòng bắt đầu mục từ:
        # Pattern 1: word (pos) /ipa/ hoặc word /ipa/ (pos) hoặc ## word
        # Pattern 2: word: nghĩa hoặc word - nghĩa
        entry_header_pattern = re.compile(
            r"^(?:##\s*|#\s*)?([a-zA-Z0-9_\s\-]{2,50}?)(?:\s+((?:(?:\(.*?\)|/.*?/|\[.*?\])\s*)+))?\s*(?:[:\-–]\s*(.*))?$"
        )

        entries: List[Tuple[str, str, str, List[str]]] = []  # (word, annotations, inline_meaning, body_lines)
        current_word: Optional[str] = None
        current_annotations: str = ""
        current_inline_meaning: str = ""
        current_body: List[str] = []

        for line in lines:
            # Kiểm tra xem dòng có phải là tiêu đề mục từ vựng mới không
            m = entry_header_pattern.match(line)
            is_new_entry = False

            if m:
                cand_word = m.group(1).strip()
                words_count = len(cand_word.split())
                if 1 <= words_count <= 4 and re.search(r"^[a-zA-Z0-9_\s\-]+$", cand_word):
                    lower_cand = cand_word.lower()
                    if lower_cand not in ["vi du", "nghia", "chuong", "bai", "trang", "table", "figure", "page", "chapter", "unit", "trinh do"]:
                        is_new_entry = True

            if is_new_entry:
                if current_word:
                    entries.append((current_word, current_annotations, current_inline_meaning, current_body))
                current_word = m.group(1).strip()
                current_annotations = m.group(2).strip() if m.group(2) else ""
                current_inline_meaning = m.group(3).strip() if m.group(3) else ""
                current_body = []
            else:
                if current_word:
                    current_body.append(line)
                else:
                    # Text mở đầu trước khi có mục từ
                    pass

        if current_word:
            entries.append((current_word, current_annotations, current_inline_meaning, current_body))

        # Chỉ áp dụng nếu nhận diện được cấu trúc mục từ rõ ràng (ít nhất 1 mục từ có body hoặc 2 mục từ)
        if len(entries) >= 2 or (len(entries) == 1 and (entries[0][1] or entries[0][2] or entries[0][3])):
            for e_idx, (word, annotations, inline_m, body_lines) in enumerate(entries, 1):
                full_body = []
                if annotations:
                    full_body.append(f"Phát âm / Từ loại: {annotations}")
                if inline_m:
                    full_body.append(inline_m)
                full_body.extend(body_lines)
                body_text = "\n".join(full_body).strip()

                if not body_text:
                    continue

                q_str = f"{word} nghĩa là gì?"
                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(q_str, body_text)
                rec_id = generate_stable_record_id(source_name, f"Trang {page_num}:{word}")

                records.append(QARecord(
                    record_id=rec_id,
                    word=word,
                    sheet=f"Trang {page_num}",
                    source=source_name,
                    level=ext_lvl,
                    question=q_str,
                    answer=body_text,
                    normalized_question=normalize_vietnamese_text(q_str),
                ))

        return records

    @classmethod
    def _chunk_general_text(
        cls,
        text: str,
        page_num: int,
        source_name: str,
        max_chunk_chars: int = 500,
        overlap_chars: int = 60
    ) -> List[QARecord]:
        """Phân đoạn văn bản tổng quát thành các chunk có kích thước hợp lý và overlap an toàn."""
        # Tách theo đoạn văn
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        if not raw_paragraphs:
            return []

        records: List[QARecord] = []
        chunk_idx = 1

        for para in raw_paragraphs:
            if len(para) < cls.MIN_TEXT_CHARS_PER_PAGE:
                continue

            # Nếu đoạn văn ngắn hơn ngưỡng chunk tối đa -> Tạo 1 record
            if len(para) <= max_chunk_chars:
                ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(para, para)
                first_line = para.splitlines()[0][:80].strip()
                q_str = (
                    f"Thông tin về '{ext_w}' (Trang {page_num})"
                    if ext_w
                    else f"Nội dung từ {source_name} (Trang {page_num}): {first_line}"
                )
                rec_id = generate_stable_record_id(source_name, f"Trang {page_num}:chunk_{chunk_idx}")
                chunk_idx += 1

                records.append(QARecord(
                    record_id=rec_id,
                    word=ext_w,
                    sheet=f"Trang {page_num}",
                    source=source_name,
                    level=ext_lvl,
                    question=q_str,
                    answer=para,
                    normalized_question=normalize_vietnamese_text(q_str),
                ))
            else:
                # Đoạn văn quá dài -> Cắt thành các sub-chunks có overlap
                start = 0
                para_len = len(para)
                while start < para_len:
                    end = min(start + max_chunk_chars, para_len)
                    sub_text = para[start:end].strip()

                    if len(sub_text) >= cls.MIN_TEXT_CHARS_PER_PAGE:
                        ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(sub_text, sub_text)
                        first_line = sub_text.splitlines()[0][:80].strip()
                        q_str = (
                            f"Thông tin về '{ext_w}' (Trang {page_num})"
                            if ext_w
                            else f"Nội dung từ {source_name} (Trang {page_num}, đoạn {chunk_idx}): {first_line}"
                        )
                        rec_id = generate_stable_record_id(source_name, f"Trang {page_num}:chunk_{chunk_idx}")
                        chunk_idx += 1

                        records.append(QARecord(
                            record_id=rec_id,
                            word=ext_w,
                            sheet=f"Trang {page_num}",
                            source=source_name,
                            level=ext_lvl,
                            question=q_str,
                            answer=sub_text,
                            normalized_question=normalize_vietnamese_text(q_str),
                        ))

                    if end >= para_len:
                        break
                    start += (max_chunk_chars - overlap_chars)

        return records

    def inspect_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Kiểm tra cấu trúc và tính sẵn sàng của file PDF trước khi nạp."""
        if not file_path.exists():
            return {"valid": False, "error": f"Không tìm thấy file: {file_path.name}"}

        try:
            pages = self._extract_pages_content(file_path)
            total_pages = len(pages)
            pages_with_text = sum(1 for p in pages if p.char_count >= self.MIN_TEXT_CHARS_PER_PAGE or p.tables)
            pages_needing_ocr = sum(1 for p in pages if p.needs_ocr)
            total_chars = sum(p.char_count for p in pages)
            ocr_ready = OCRHandler.check_environment()["is_ready"]

            sample_texts = [p.text[:100] for p in pages if p.text][:3]

            return {
                "valid": True,
                "file_name": file_path.name,
                "file_size_kb": round(file_path.stat().st_size / 1024, 2),
                "total_pages": total_pages,
                "pages_with_text": pages_with_text,
                "pages_needing_ocr": pages_needing_ocr,
                "ocr_ready": ocr_ready,
                "total_chars": total_chars,
                "preview_text": "\n---\n".join(sample_texts) if sample_texts else "Không có text xem trước."
            }
        except Exception as err:
            return {"valid": False, "error": str(err)}

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        """Tải, trích xuất và chuẩn hóa toàn bộ dữ liệu từ tệp PDF.

        Args:
            file_path: Đường dẫn tệp PDF.
            file_hash: Mã băm SHA-256 (nếu đã tính).
            start_index: Chỉ số bắt đầu phục vụ định danh.

        Returns:
            List[QARecord]: Danh sách các bản ghi Q&A chuẩn hóa kèm rich metadata.
        """
        f_hash = file_hash or compute_file_hash(file_path)
        pages_content = self._extract_pages_content(file_path)

        records: List[QARecord] = []
        total_pages = len(pages_content)
        pages_with_text = 0
        pages_needing_ocr = 0
        ocr_success_pages = 0
        ocr_failed_pages = 0
        total_chars_extracted = 0

        for p_res in pages_content:
            page_num = p_res.page_num

            if p_res.ocr_attempted:
                if p_res.ocr_success:
                    ocr_success_pages += 1
                else:
                    ocr_failed_pages += 1

            if p_res.needs_ocr:
                pages_needing_ocr += 1

            page_records: List[QARecord] = []

            # 1. Ưu tiên xử lý bảng biểu nếu có
            tab_words = set()
            if p_res.tables:
                for tab in p_res.tables:
                    tab_records = self._parse_table_rows(tab, page_num, file_path.name)
                    for tr in tab_records:
                        if tr.word:
                            tab_words.add(tr.word.lower())
                    page_records.extend(tab_records)

            # 2. Xử lý văn bản trang nếu có
            if p_res.text and p_res.char_count >= self.MIN_TEXT_CHARS_PER_PAGE:
                pages_with_text += 1
                total_chars_extracted += p_res.char_count

                # Nếu trang không có bảng (hoặc bảng không trích xuất được record)
                if not page_records:
                    dict_records = self._parse_multiline_vocab_entries(p_res.text, page_num, file_path.name)
                    if dict_records:
                        page_records.extend(dict_records)
                    else:
                        chunk_records = self._chunk_general_text(p_res.text, page_num, file_path.name)
                        page_records.extend(chunk_records)

            records.extend(page_records)

        # Lưu báo cáo chi tiết cho phiên nạp
        self.last_extraction_report = {
            "file_name": file_path.name,
            "total_pages": total_pages,
            "pages_with_text": pages_with_text,
            "pages_needing_ocr": pages_needing_ocr,
            "ocr_success_pages": ocr_success_pages,
            "ocr_failed_pages": ocr_failed_pages,
            "total_characters_extracted": total_chars_extracted,
            "chunks_created": len(records),
            "sample_words": [r.word for r in records if r.word][:10],
            "sample_preview": [f"[{r.sheet}] {r.question} -> {r.answer[:80]}..." for r in records[:3]]
        }

        # Kiểm tra tính hợp lệ của kết quả
        if not records:
            if pages_needing_ocr > 0 and ocr_success_pages == 0:
                guide = OCRHandler.get_tesseract_install_guide()
                raise DataLoadError(
                    f"Tệp PDF '{file_path.name}' gồm {total_pages} trang nhưng không chứa text có thể trích xuất "
                    f"(các trang là ảnh/scan và hệ thống chưa có Tesseract OCR).\n\n{guide}"
                )
            raise DataLoadError(
                f"Tệp PDF '{file_path.name}' không trích xuất được bất kỳ bản ghi văn bản hoặc bảng nào hợp lệ."
            )

        logger.info(
            "PDFLoader: Đã nạp thành công %d bản ghi từ %s (%d trang, %d trang có text, %d trang cần OCR)",
            len(records), file_path.name, total_pages, pages_with_text, pages_needing_ocr
        )
        return records
