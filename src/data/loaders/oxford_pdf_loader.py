"""Bộ bóc tách chuyên biệt cho danh sách từ vựng Oxford 3000 theo cấp độ CEFR (.pdf).

Phân tích chính xác cấu trúc tệp The_Oxford_3000_by_CEFR_level.pdf:
- Nhận diện các phân vùng cấp độ CEFR: A1, A2, B1, B2.
- Ghép nối các dòng ngắt/xuống hàng giữa các từ loại (wrapped lines).
- Làm sạch các chú thích đồng âm (lie1 -> lie), dấu nháy đơn unicode (o’clock -> o'clock).
- Kết hợp với DictionaryDBService để tự động tra cứu phiên âm IPA, giải nghĩa tiếng Việt,
  từ loại và câu ví dụ minh họa, tạo thành các bản ghi QARecord chuẩn mực.
"""

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.dictionary_db import DictionaryDBService
from src.data.loader import normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash, generate_stable_record_id

logger = logging.getLogger(__name__)

# Tiêu đề nhận diện tài liệu Oxford 3000 / 5000 và số trang
HEADER_PATTERNS = [
    re.compile(r"©\s*Oxford\s*University\s*Press.*", re.IGNORECASE),
    re.compile(r"The\s*Oxford\s*(?:3000|5000|\d+).*", re.IGNORECASE),
    re.compile(r"Oxford\s*(?:3000|5000|\d+).*", re.IGNORECASE),
    re.compile(r"^\d+\s*/\s*\d+$"),
]

# Regex nhận diện phần từ loại ở cuối dòng
POS_REGEX = re.compile(
    r"\s+((?:(?:n|v|adj|adv|prep|pron|conj|det|exclam|number|modal v|auxiliary|auxiliary v|infinitive marker|indefinite article|definite article|article)(?:\.|\b)(?:\s*[,/]\s*)?)+)$",
    re.IGNORECASE
)

LEVEL_PATTERN = re.compile(r"^(A1|A2|B1|B2|C1|C2)$")


class OxfordPDFParser(BaseFileLoader):
    """Trích xuất và chuẩn hóa từ vựng từ tệp PDF The Oxford 3000 by CEFR level."""

    SUPPORTED_EXTENSIONS = ["pdf"]

    def __init__(self, dict_service: Optional[DictionaryDBService] = None):
        self.dict_service = dict_service or DictionaryDBService()

    @classmethod
    def _extract_raw_lines_by_page(cls, file_path: Path) -> List[Tuple[int, List[str]]]:
        """Trích xuất danh sách dòng theo từng trang bằng PyMuPDF hoặc pypdf."""
        pages_lines: List[Tuple[int, List[str]]] = []

        # 1. Thử PyMuPDF trước
        try:
            import pymupdf
            doc = pymupdf.open(str(file_path))
            for page_idx in range(len(doc)):
                text = doc[page_idx].get_text("text")
                lines = [l.replace("\xa0", " ").strip() for l in text.splitlines() if l.strip()]
                pages_lines.append((page_idx + 1, lines))
            doc.close()
            if pages_lines:
                return pages_lines
        except Exception as e:
            logger.warning("PyMuPDF không khả dụng (%s), chuyển sang pypdf...", e)

        # 2. Fallback sang pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            for page_idx, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                lines = [l.replace("\xa0", " ").strip() for l in text.splitlines() if l.strip()]
                pages_lines.append((page_idx, lines))
            if pages_lines:
                return pages_lines
        except Exception as exc:
            raise DataLoadError(f"Không thể đọc tệp PDF Oxford '{file_path.name}': {exc}") from exc

        return pages_lines

    @classmethod
    def parse_oxford_entries(cls, file_path: Path) -> List[Dict[str, Any]]:
        """Phân tích toàn bộ các mục từ vựng, tự động xác định level CEFR và nối dòng ngắt."""
        pages_lines = cls._extract_raw_lines_by_page(file_path)
        all_raw_lines: List[Tuple[str, str]] = []

        current_level = "A1"
        for _, lines in pages_lines:
            for l in lines:
                if not l:
                    continue
                # Bỏ qua các dòng tiêu đề cố định của nhà xuất bản Oxford
                if any(hp.search(l) for hp in HEADER_PATTERNS):
                    continue
                # Cập nhật cấp độ CEFR
                if LEVEL_PATTERN.match(l):
                    current_level = l
                    continue
                all_raw_lines.append((current_level, l))

        # Hợp nhất các dòng bị ngắt xuống dòng giữa từ loại
        merged_entries: List[Tuple[str, str]] = []
        idx = 0
        total = len(all_raw_lines)
        continuation_tokens = ("adj.", "number", "n.", "v.", "adv.", "prep.", "conj.", "det.")

        while idx < total:
            lvl, line = all_raw_lines[idx]
            idx += 1
            if idx < total:
                _, next_line = all_raw_lines[idx]
                if (
                    next_line in continuation_tokens
                    or line.endswith(",")
                    or line.endswith("/")
                    or line.endswith("det./")
                    or line.endswith("adj.,")
                    or line.endswith("n.,")
                ):
                    line = f"{line} {next_line}".strip()
                    idx += 1
            merged_entries.append((lvl, line))

        entries: List[Dict[str, Any]] = []
        valid_pos_abbrs = {"n.", "v.", "adj.", "adv.", "prep.", "conj.", "pron.", "det.", "exclam.", "number", "modal v.", "auxiliary", "article"}
        for lvl, line_text in merged_entries:
            m = POS_REGEX.search(line_text)
            if m:
                raw_word = line_text[:m.start()].strip()
                pos_str = m.group(1).strip()
            else:
                tokens = line_text.split()
                # Kiểm tra xem có token nào là POS hợp lệ không (tránh đọc nhầm đoạn văn giới thiệu/chú thích)
                if tokens and len(tokens) >= 2 and any(t.rstrip(",/").lower() in valid_pos_abbrs for t in tokens[1:]):
                    raw_word = tokens[0]
                    pos_str = " ".join(tokens[1:])
                else:
                    continue

            if not raw_word:
                continue

            # Tách các thẻ POS
            pos_tokens = [p.strip() for p in re.split(r"[,/]", pos_str) if p.strip()]

            # Làm sạch từ để tra cứu DB
            # 1. Bỏ số đồng âm: lie1 -> lie, wind2 -> wind
            clean_word = re.sub(r"\d+$", "", raw_word).strip()
            # 2. Chuẩn hóa dấu nháy đơn unicode
            clean_word = clean_word.replace("’", "'").replace("`", "'")
            # 3. Chuẩn hóa unicode NFC
            clean_word = unicodedata.normalize("NFC", clean_word)

            # Tách nghĩa ngữ cảnh phụ (ví dụ: bank (money) -> bank)
            base_word = re.sub(r"\s*\([^)]*\)", "", clean_word).strip()

            if not clean_word or not re.search(r"[a-zA-Z]", clean_word):
                continue

            entries.append({
                "level": lvl,
                "raw_word": raw_word,
                "clean_word": clean_word,
                "base_word": base_word or clean_word,
                "pos_str": pos_str,
                "pos_tokens": pos_tokens,
                "raw_entry": line_text,
            })

        logger.info("OxfordPDFParser: Đã trích xuất thành công %d mục từ vựng từ %s", len(entries), file_path.name)
        return entries

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1,
    ) -> List[QARecord]:
        """Tải toàn bộ từ vựng Oxford 3000 và kết hợp tra cứu từ điển SQLite tạo QARecord."""
        f_hash = file_hash or compute_file_hash(file_path)
        raw_entries = self.parse_oxford_entries(file_path)

        records: List[QARecord] = []
        seen_rec_ids: set = set()
        for item in raw_entries:
            level = item["level"]
            clean_word = item["clean_word"]
            base_word = item["base_word"]
            pos_tokens = item["pos_tokens"]

            # Tạo Stable ID duy nhất theo từ và cấp độ
            rec_id = generate_stable_record_id(file_path.name, f"{clean_word}_{level}")
            if rec_id in seen_rec_ids:
                continue
            seen_rec_ids.add(rec_id)

            # Tra cứu từ điển: thử base_word trước, nếu không được thử clean_word
            lookup_data = self.dict_service.lookup(base_word)
            if not lookup_data and clean_word != base_word:
                lookup_data = self.dict_service.lookup(clean_word)

            # Tạo câu hỏi và câu trả lời chuẩn
            question = f"{clean_word} nghĩa là gì?"
            answer = self.dict_service.format_answer(
                word=clean_word,
                level=level,
                lookup_data=lookup_data,
                oxford_pos_tokens=pos_tokens,
            )

            records.append(QARecord(
                record_id=rec_id,
                word=clean_word,
                sheet=level,
                source=file_path.name,
                level=level,
                question=question,
                answer=answer,
                normalized_question=normalize_vietnamese_text(question),
            ))

        logger.info("OxfordPDFParser: Hoàn tất chuyển đổi %d bản ghi QARecord từ %s", len(records), file_path.name)
        return records
