"""Bộ nạp tệp dữ liệu cấu trúc JSON (.json) và JSONL (.jsonl)."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader, normalize_vietnamese_text
from src.data.loaders.base import BaseFileLoader, compute_file_hash

logger = logging.getLogger(__name__)


class JSONLoader(BaseFileLoader):
    """Xử lý tệp cấu trúc JSON và JSONL với đa dạng lược đồ dữ liệu."""

    SUPPORTED_EXTENSIONS = ["json", "jsonl"]

    @staticmethod
    def _parse_dict_to_record(
        item: Dict[str, Any],
        file_path: Path,
        idx: int
    ) -> Optional[QARecord]:
        """Chuyển đổi một dictionary JSON thành QARecord."""
        # Tìm trường câu hỏi
        question = ""
        for k in ["question", "cau_hoi", "câu_hỏi", "prompt", "query", "term", "tu_vung"]:
            if k in item and str(item[k]).strip():
                question = str(item[k]).strip()
                break

        # Tìm trường câu trả lời
        answer = ""
        for k in ["answer", "cau_tra_loi", "câu_trả_lời", "definition", "meaning", "nghia", "content", "response"]:
            if k in item and str(item[k]).strip():
                answer = str(item[k]).strip()
                break

        if not question or not answer:
            return None

        # Trích xuất từ vựng
        word = str(item.get("word", item.get("tu_vung", ""))).strip()
        level = str(item.get("level", item.get("trinh_do", ""))).strip().upper()
        source = str(item.get("source", item.get("nguon", file_path.name))).strip()

        ext_w, ext_lvl = QALoader._extract_word_and_level_fallback(question, answer)
        if not word:
            word = ext_w
        if not level:
            level = ext_lvl

        rec_id = item.get("record_id", f"JSON_{file_path.stem[:8]}_{idx:04d}")

        return QARecord(
            record_id=rec_id,
            word=word,
            sheet=file_path.suffix.upper().lstrip("."),
            source=source or file_path.name,
            level=level,
            question=question,
            answer=answer,
            normalized_question=normalize_vietnamese_text(question),
        )

    def load(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        start_index: int = 1
    ) -> List[QARecord]:
        f_hash = file_hash or compute_file_hash(file_path)
        ext = file_path.suffix.lower().lstrip(".")
        records: List[QARecord] = []

        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        raw_text = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw_text = f.read()
                break
            except Exception:
                continue

        if raw_text is None:
            raise DataLoadError(f"Không thể đọc tệp JSON '{file_path.name}'.")

        # 1. Định dạng JSONL
        if ext == "jsonl":
            for line_idx, line in enumerate(raw_text.splitlines(), start_index):
                clean_l = line.strip()
                if clean_l:
                    try:
                        data = json.loads(clean_l)
                        if isinstance(data, dict):
                            rec = self._parse_dict_to_record(data, file_path, line_idx)
                            if rec:
                                records.append(rec)
                    except json.JSONDecodeError as err:
                        logger.warning("Bỏ qua dòng %d trong %s lỗi cú pháp JSON: %s", line_idx, file_path.name, err)

        # 2. Định dạng JSON
        else:
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as err:
                raise DataLoadError(f"Tệp JSON '{file_path.name}' bị lỗi cú pháp: {err}") from err

            # Trường hợp 1: Danh sách các dict
            if isinstance(data, list):
                for idx, item in enumerate(data, start_index):
                    if isinstance(item, dict):
                        rec = self._parse_dict_to_record(item, file_path, idx)
                        if rec:
                            records.append(rec)

            # Trường hợp 2: Dict glossary { "word": "definition", ... } hoặc { "data": [...] }
            elif isinstance(data, dict):
                # Nếu có key chứa danh sách con
                inner_list = None
                for key in ["records", "data", "items", "vocabulary", "words", "qa_list"]:
                    if key in data and isinstance(data[key], list):
                        inner_list = data[key]
                        break

                if inner_list is not None:
                    for idx, item in enumerate(inner_list, start_index):
                        if isinstance(item, dict):
                            rec = self._parse_dict_to_record(item, file_path, idx)
                            if rec:
                                records.append(rec)
                else:
                    # Coi dict như glossary { "word_or_question": "answer_or_definition" }
                    for idx, (k, v) in enumerate(data.items(), start_index):
                        if isinstance(v, (str, dict, list)):
                            ans_str = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                            q_str = f"{k} nghĩa là gì?" if not k.endswith("?") else k
                            rec = self._parse_dict_to_record({
                                "question": q_str,
                                "answer": ans_str,
                                "word": k
                            }, file_path, idx)
                            if rec:
                                records.append(rec)

        logger.info("JSONLoader: Nạp thành công %d bản ghi từ %s", len(records), file_path.name)
        return records
