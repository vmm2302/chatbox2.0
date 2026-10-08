"""Module tải, kiểm tra và chuẩn hóa dữ liệu Q&A.

Hỗ trợ đọc trực tiếp tệp Excel (.xlsx) thông qua thư viện chuẩn Python (zipfile + XML),
tự động nhận diện cấu trúc (4 sheets mặc định hoặc sheet tùy chỉnh người dùng tải lên),
trích xuất rich metadata (record_id, word, sheet, source, level) phục vụ ChromaDB và LangChain.
"""

import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from langchain_core.documents import Document

from config.settings import settings
from src.core.exceptions import DataLoadError
from src.core.models import QARecord

logger = logging.getLogger(__name__)

# Namespace chuẩn của tệp OpenXML Spreadsheet
XML_NS = {
    "ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def normalize_vietnamese_text(text: str) -> str:
    """Loại bỏ dấu tiếng Việt, dấu câu và đưa về chữ thường phục vụ so khớp từ khóa."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text)
    no_accent = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    no_accent = no_accent.replace("đ", "d").replace("Đ", "D")
    clean_text = re.sub(r"[^\w\s]", " ", no_accent)
    return " ".join(clean_text.lower().split())


def normalize_query_text(query: str) -> Tuple[str, str]:
    """Chuẩn hóa câu truy vấn người dùng:
    - Unicode NFC normalization
    - Strip khoảng trắng đầu/cuối
    - Chuẩn hóa nhiều khoảng trắng liên tiếp thành một khoảng trắng đơn

    Returns:
        Tuple[str, str]:
            - clean_query: Chuỗi gốc sau khi chuẩn hóa NFC và khoảng trắng (giữ nguyên hoa/thường)
            - normalized_query: Chuỗi lowercased phục vụ routing/intent matching
    """
    if not query:
        return "", ""
    nfc_text = unicodedata.normalize("NFC", query)
    clean_query = re.sub(r"\s+", " ", nfc_text).strip()
    normalized_query = clean_query.lower()
    return clean_query, normalized_query


def col_to_idx(col_letters: str) -> int:
    """Chuyển đổi ký tự cột Excel (A, B, AA, ...) thành chỉ số 0-indexed."""
    idx = 0
    for char in col_letters.upper():
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


class QALoader:
    """Lớp chịu trách nhiệm đọc và kiểm tra chất lượng tệp dữ liệu Q&A từ Excel hoặc JSONL."""

    def __init__(self, raw_excel_path: Optional[Path] = None, processed_jsonl_path: Optional[Path] = None):
        self.raw_excel_path = raw_excel_path or settings.RAW_EXCEL_PATH
        self.processed_jsonl_path = processed_jsonl_path or settings.PROCESSED_JSONL_PATH

    @staticmethod
    def _read_shared_strings(z: zipfile.ZipFile) -> List[str]:
        """Đọc bảng chuỗi dùng chung (sharedStrings.xml) trong tệp Excel."""
        sst: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("ns:si", XML_NS):
                text_pieces = [t.text for t in si.findall(".//ns:t", XML_NS) if t.text]
                sst.append("".join(text_pieces))
        return sst

    @classmethod
    def _get_sheet_info(cls, z: zipfile.ZipFile) -> List[Tuple[str, str]]:
        """Lấy danh sách (tên_sheet, đường_dẫn_xml) từ tệp Excel OpenXML."""
        rel_map: Dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in z.namelist():
            rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            for r in rels_root:
                rel_id = r.attrib.get("Id", "")
                target = r.attrib.get("Target", "")
                if rel_id and target:
                    if not target.startswith("xl/"):
                        target = "xl/" + target.lstrip("/")
                    rel_map[rel_id] = target

        sheets: List[Tuple[str, str]] = []
        if "xl/workbook.xml" in z.namelist():
            wb_root = ET.fromstring(z.read("xl/workbook.xml"))
            for s in wb_root.findall(".//ns:sheet", XML_NS):
                name = s.attrib.get("name", "")
                r_id = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
                target = rel_map.get(r_id, "")
                if target and target in z.namelist():
                    sheets.append((name, target))

        # Dự phòng nếu không đọc được từ workbook.xml
        if not sheets:
            sheet_files = sorted([n for n in z.namelist() if re.match(r"^xl/worksheets/sheet\d+\.xml$", n)])
            for idx, sf in enumerate(sheet_files, 1):
                sheets.append((f"Sheet{idx}", sf))

        return sheets

    @classmethod
    def _parse_sheet_rows(cls, z: zipfile.ZipFile, sheet_path: str, sst: List[str]) -> List[List[str]]:
        """Phân tích các hàng dữ liệu trong một sheet XML, tự động căn chỉnh vị trí ô theo cột."""
        sheet_xml = ET.fromstring(z.read(sheet_path))
        parsed_rows: List[List[str]] = []

        for row in sheet_xml.findall(".//ns:row", XML_NS):
            row_cells: Dict[int, str] = {}
            for c in row.findall("ns:c", XML_NS):
                r_attr = c.attrib.get("r", "")
                col_match = re.match(r"^([A-Za-z]+)", r_attr)
                col_idx = col_to_idx(col_match.group(1)) if col_match else len(row_cells)

                t = c.attrib.get("t")
                v = c.find("ns:v", XML_NS)
                val = ""
                if t == "s" and v is not None and v.text and v.text.isdigit():
                    idx = int(v.text)
                    val = sst[idx] if idx < len(sst) else ""
                elif t == "inlineStr":
                    is_node = c.find("ns:is", XML_NS)
                    if is_node is not None:
                        val = "".join(t_el.text or "" for t_el in is_node.findall(".//ns:t", XML_NS))
                elif v is not None and v.text:
                    val = v.text

                row_cells[col_idx] = val.strip()

            if row_cells:
                max_col = max(row_cells.keys())
                row_data = [row_cells.get(i, "") for i in range(max_col + 1)]
                # Bỏ bớt các ô trống thừa ở cuối hàng
                while row_data and not row_data[-1]:
                    row_data.pop()
                if any(row_data):
                    parsed_rows.append(row_data)

        return parsed_rows

    @classmethod
    def _detect_column_mapping(cls, header_row: List[str]) -> Optional[Dict[str, int]]:
        """Xác định vị trí các cột nghiệp vụ dựa trên tên tiêu đề cột."""
        col_map: Dict[str, int] = {}
        normalized = [normalize_vietnamese_text(h) for h in header_row]

        for idx, h in enumerate(normalized):
            if not h:
                continue
            if any(kw in h for kw in ["cau hoi", "question", "hoi", "prompt"]):
                if "question" not in col_map:
                    col_map["question"] = idx
            elif any(kw in h for kw in ["cau tra loi", "tra loi", "answer", "thong tin", "nghia", "dich", "giai thich"]):
                if "answer" not in col_map:
                    col_map["answer"] = idx
            elif any(kw in h for kw in ["tu vung", "tu tieng anh", "word", "vocab"]):
                if "word" not in col_map:
                    col_map["word"] = idx
            elif any(kw in h for kw in ["trinh do", "cap do", "level", "cefr", "difficulty"]):
                if "level" not in col_map:
                    col_map["level"] = idx
            elif any(kw in h for kw in ["nguon", "source", "tai lieu"]):
                if "source" not in col_map:
                    col_map["source"] = idx
            elif any(kw in h for kw in ["record_id", "record id", "recordid", "id", "stt", "ma", "ma ban ghi"]):
                if "record_id" not in col_map:
                    col_map["record_id"] = idx

        if "question" in col_map and "answer" in col_map:
            return col_map
        return None

    @classmethod
    def _extract_word_and_level_fallback(cls, question: str, answer: str) -> Tuple[str, str]:
        """Tự động trích xuất từ vựng và trình độ CEFR từ nội dung câu hỏi/câu trả lời nếu cột bị thiếu."""
        word = ""
        level = ""

        q_clean = question.strip()
        first_q_line = q_clean.splitlines()[0].strip() if q_clean else ""

        # Trích xuất từ vựng
        w_match1 = re.match(r"^([a-zA-Z0-9_\s,\-]+)\s+nghĩa là gì", first_q_line, re.IGNORECASE)
        w_match4 = re.match(r"^#*\s*([a-zA-Z0-9_\s\-]{2,50})\s*[:\-–]", first_q_line)
        w_match2 = re.search(r"\btừ\s+([a-zA-Z0-9_\-]+)", q_clean, re.IGNORECASE)
        w_match3 = re.search(r"-\s*Từ tiếng Anh\s*:\s*([^\n\r]+)", answer, re.IGNORECASE)

        if w_match1:
            word = w_match1.group(1).strip()
        elif w_match4:
            word = w_match4.group(1).strip()
        elif w_match2:
            word = w_match2.group(1).strip()
        elif w_match3:
            word = w_match3.group(1).strip()
        elif re.fullmatch(r"^[a-zA-Z0-9_\s\-]{2,50}$", first_q_line):
            word = first_q_line

        # Trích xuất trình độ CEFR
        lvl_match1 = re.search(r"trình độ\s*:?\s*([A-Za-z0-9]+)", answer, re.IGNORECASE)
        lvl_match2 = re.search(r"trình độ\s*([A-Za-z0-9]+)", question, re.IGNORECASE)
        lvl_match3 = re.search(r"\b([A-B][1-2]|C[1-2])\b", answer)

        if lvl_match1:
            level = lvl_match1.group(1).upper()
        elif lvl_match2:
            level = lvl_match2.group(1).upper()
        elif lvl_match3:
            level = lvl_match3.group(1).upper()

        return word, level

    def _parse_custom_sheet(
        self,
        rows: List[List[str]],
        sheet_name: str,
        source_default: str,
        start_index: int
    ) -> List[QARecord]:
        """Phân tích một sheet tùy chỉnh với khả năng tự thích ứng cấu trúc cột."""
        if not rows:
            return []

        records: List[QARecord] = []
        first_row = rows[0]
        col_map = self._detect_column_mapping(first_row)

        data_rows = rows[1:] if col_map is not None else rows

        # Nếu không có header, suy luận theo thứ tự cột mặc định
        if col_map is None:
            if len(first_row) >= 2:
                # Cột 0: Câu hỏi, Cột 1: Câu trả lời
                col_map = {"question": 0, "answer": 1}
                if len(first_row) >= 3:
                    col_map["word"] = 2
                if len(first_row) >= 4:
                    col_map["level"] = 3
                if len(first_row) >= 5:
                    col_map["source"] = 4
            else:
                return []

        for row in data_rows:
            q_idx = col_map.get("question", 0)
            a_idx = col_map.get("answer", 1)

            if len(row) <= max(q_idx, a_idx):
                continue

            question = row[q_idx].strip()
            answer = row[a_idx].strip()

            if not question or not answer:
                continue

            # Bỏ qua nếu dòng dữ liệu trùng lặp với tiêu đề cột
            if normalize_vietnamese_text(question) in ["cau hoi", "question"]:
                continue

            word = ""
            if "word" in col_map and col_map["word"] < len(row):
                word = row[col_map["word"]].strip()

            level = ""
            if "level" in col_map and col_map["level"] < len(row):
                level = row[col_map["level"]].strip().upper()

            source = source_default
            if "source" in col_map and col_map["source"] < len(row):
                src_val = row[col_map["source"]].strip()
                if src_val:
                    source = src_val

            # Nếu thiếu word hoặc level, tự động trích xuất bằng regex
            extracted_word, extracted_level = self._extract_word_and_level_fallback(question, answer)
            if not word:
                word = extracted_word
            if not level:
                level = extracted_level

            custom_id = ""
            if "record_id" in col_map and col_map["record_id"] < len(row):
                custom_id = row[col_map["record_id"]].strip()

            from src.data.loaders.base import generate_stable_record_id
            rec_id = generate_stable_record_id(source_default, question, custom_id=custom_id or None)
            records.append(QARecord(
                record_id=rec_id,
                word=word,
                sheet=sheet_name,
                source=source,
                level=level,
                question=question,
                answer=answer,
                normalized_question=normalize_vietnamese_text(question),
            ))

        return records

    def load_from_excel(self, excel_path: Optional[Path] = None) -> List[QARecord]:
        """Đọc và chuẩn hóa toàn bộ các sheet từ tệp Excel (hỗ trợ cả dataset gốc lẫn tệp mới)."""
        target_path = excel_path or self.raw_excel_path
        if not target_path.exists():
            raise DataLoadError(f"Không tìm thấy tệp dữ liệu tại: {target_path}")

        records: List[QARecord] = []

        try:
            with zipfile.ZipFile(target_path, "r") as z:
                sst = self._read_shared_strings(z)
                sheets = self._get_sheet_info(z)

                for sheet_name, sheet_xml_path in sheets:
                    rows = self._parse_sheet_rows(z, sheet_xml_path, sst)
                    if not rows:
                        continue

                    # 1. Sheet 1 gốc: danhsachtutienganhA1-B2
                    if sheet_name == "danhsachtutienganhA1-B2":
                        for row in rows[1:]:
                            if len(row) >= 3:
                                question, answer = row[1].strip(), row[2].strip()
                                source = row[3].strip() if len(row) > 3 and row[3].strip() else "Cambridge Dictionary"
                                if question and answer:
                                    rec_id = f"ENG_VOCAB_{len(records) + 1:04d}"
                                    w_match = re.match(r"^([a-zA-Z\s,\-]+)\s+nghĩa là gì", question, re.IGNORECASE)
                                    word = w_match.group(1).strip() if w_match else ""
                                    lvl_match = re.search(r"trình độ\s*:\s*([A-Za-z0-9]+)", answer, re.IGNORECASE)
                                    level = lvl_match.group(1).upper() if lvl_match else ""

                                    records.append(QARecord(
                                        record_id=rec_id,
                                        word=word,
                                        sheet=sheet_name,
                                        source=source,
                                        level=level,
                                        question=question,
                                        answer=answer,
                                        normalized_question=normalize_vietnamese_text(question),
                                    ))

                    # 2. Sheet 2 gốc: danhsachtheotrinhdoA1-B2
                    elif sheet_name == "danhsachtheotrinhdoA1-B2":
                        for row in rows:
                            if len(row) >= 2:
                                question, answer = row[0].strip(), row[1].strip()
                                if question and answer:
                                    rec_id = f"LEVEL_LIST_{len(records) + 1:04d}"
                                    lvl_match = re.search(r"trình độ\s*([A-Za-z0-9]+)", question, re.IGNORECASE)
                                    level = lvl_match.group(1).upper() if lvl_match else ""

                                    records.append(QARecord(
                                        record_id=rec_id,
                                        word="list",
                                        sheet=sheet_name,
                                        source="CEFR A1-B2 Framework",
                                        level=level,
                                        question=question,
                                        answer=answer,
                                        normalized_question=normalize_vietnamese_text(question),
                                    ))

                    # 3. Sheet 3 gốc: tiengvietsangtienganh
                    elif sheet_name == "tiengvietsangtienganh":
                        for row in rows[1:]:
                            if len(row) >= 2:
                                question, answer = row[0].strip(), row[1].strip()
                                if question and answer:
                                    rec_id = f"VIE_ENG_{len(records) + 1:04d}"
                                    w_match = re.search(r"-\s*Từ tiếng Anh\s*:\s*([^\n\r]+)", answer, re.IGNORECASE)
                                    word = w_match.group(1).strip() if w_match else ""
                                    lvl_match = re.search(r"-\s*Trình độ\s*:\s*([A-Za-z0-9]+)", answer, re.IGNORECASE)
                                    level = lvl_match.group(1).upper() if lvl_match else ""

                                    records.append(QARecord(
                                        record_id=rec_id,
                                        word=word,
                                        sheet=sheet_name,
                                        source="Vietnamese-English Dictionary",
                                        level=level,
                                        question=question,
                                        answer=answer,
                                        normalized_question=normalize_vietnamese_text(question),
                                    ))

                    # 4. Sheet 4 gốc: danhsachcauhoicotutrongcau
                    elif sheet_name == "danhsachcauhoicotutrongcau":
                        for row in rows[1:]:
                            if len(row) >= 2:
                                question, answer = row[0].strip(), row[1].strip()
                                if question and answer:
                                    rec_id = f"EXAMPLE_{len(records) + 1:04d}"
                                    w_match = re.search(r"từ\s+([a-zA-Z\-]+)", question, re.IGNORECASE)
                                    word = w_match.group(1).strip() if w_match else ""

                                    records.append(QARecord(
                                        record_id=rec_id,
                                        word=word,
                                        sheet=sheet_name,
                                        source="Vocabulary In Use Examples",
                                        level="",
                                        question=question,
                                        answer=answer,
                                        normalized_question=normalize_vietnamese_text(question),
                                    ))

                    # 5. Sheet tùy chỉnh do người dùng đưa vào
                    else:
                        custom_recs = self._parse_custom_sheet(
                            rows=rows,
                            sheet_name=sheet_name,
                            source_default=f"Tệp tải lên: {target_path.name}",
                            start_index=len(records)
                        )
                        records.extend(custom_recs)

        except Exception as exc:
            raise DataLoadError(f"Lỗi khi đọc tệp Excel '{target_path.name}': {exc}") from exc

        logger.info("Đã nạp thành công %d bản ghi từ %s.", len(records), target_path.name)
        return records

    def load_from_raw_excel(self) -> List[QARecord]:
        """Tương thích ngược: tải từ tệp raw excel mặc định."""
        return self.load_from_excel(self.raw_excel_path)

    @classmethod
    def merge_records(
        cls,
        existing_records: List[QARecord],
        incoming_records: List[QARecord],
        return_updated: bool = False
    ) -> Tuple:
        """Hợp nhất các bản ghi mới vào tập hiện có theo Stable Record ID:
        - Nếu ID đã tồn tại trong KB: UPDATE / OVERWRITE dữ liệu mới.
        - Nếu ID chưa tồn tại nhưng trùng hoàn toàn (question, answer): Bỏ qua duplicate.
        - Nếu ID chưa tồn tại và nội dung mới: ADD.

        Returns:
            Nếu return_updated=True: Tuple[List[QARecord], int, int, int] (merged, added, updated, dupes)
            Mặc định: Tuple[List[QARecord], int, int] (merged, added, dupes) để tương thích ngược.
        """
        existing_by_id: Dict[str, Tuple[int, QARecord]] = {
            r.record_id: (idx, r) for idx, r in enumerate(existing_records) if r.record_id
        }
        existing_signatures: Dict[Tuple[str, str], str] = {
            (r.question.strip().lower(), r.answer.strip().lower()): r.record_id
            for r in existing_records
        }

        merged: List[QARecord] = list(existing_records)
        added_count = 0
        updated_count = 0
        duplicate_count = 0

        for inc in incoming_records:
            # 1. Nếu ID đã tồn tại trong KB -> UPDATE / OVERWRITE
            if inc.record_id and inc.record_id in existing_by_id:
                old_idx, old_rec = existing_by_id[inc.record_id]
                # Xóa signature cũ nếu có
                old_sig = (old_rec.question.strip().lower(), old_rec.answer.strip().lower())
                existing_signatures.pop(old_sig, None)

                merged[old_idx] = inc
                new_sig = (inc.question.strip().lower(), inc.answer.strip().lower())
                existing_signatures[new_sig] = inc.record_id
                existing_by_id[inc.record_id] = (old_idx, inc)
                updated_count += 1
                continue

            # 2. Kiểm tra trùng lặp nội dung
            sig = (inc.question.strip().lower(), inc.answer.strip().lower())
            if sig in existing_signatures:
                duplicate_count += 1
                continue

            # 3. ID mới và nội dung mới -> ADD
            new_idx = len(merged)
            existing_signatures[sig] = inc.record_id
            if inc.record_id:
                existing_by_id[inc.record_id] = (new_idx, inc)
            merged.append(inc)
            added_count += 1

        if return_updated:
            return merged, added_count, updated_count, duplicate_count
        return merged, added_count, duplicate_count

    def save_to_jsonl(self, records: List[QARecord]) -> None:
        """Lưu danh sách bản ghi chuẩn hóa ra định dạng JSONL."""
        self.processed_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.processed_jsonl_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Đã lưu %d bản ghi vào %s", len(records), self.processed_jsonl_path)

    def load_from_jsonl(self) -> List[QARecord]:
        """Tải các bản ghi đã chuẩn hóa từ tệp JSONL. Trả về rỗng nếu tệp chưa tồn tại."""
        if not self.processed_jsonl_path.exists():
            return []

        records: List[QARecord] = []
        with open(self.processed_jsonl_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                clean_line = line.strip()
                if clean_line:
                    try:
                        data = json.loads(clean_line)
                        records.append(QARecord.from_dict(data))
                    except json.JSONDecodeError as err:
                        logger.warning("Bỏ qua dòng %d bị lỗi định dạng JSON: %s", line_idx, err)

        return records

    def get_or_create_records(self, force_refresh: bool = False) -> List[QARecord]:
        """Lấy dữ liệu từ JSONL hoặc trích xuất từ Excel thô (nếu có). An toàn khi rỗng."""
        if not force_refresh and self.processed_jsonl_path.exists():
            records = self.load_from_jsonl()
            if records:
                return records

        if self.raw_excel_path.exists():
            logger.info("Bắt đầu trích xuất từ Excel thô: %s...", self.raw_excel_path)
            try:
                records = self.load_from_excel(self.raw_excel_path)
                self.save_to_jsonl(records)
                return records
            except Exception as err:
                logger.warning("Không thể nạp từ file mẫu thô: %s", err)

        logger.info("Khởi tạo kho tri thức ở trạng thái rỗng (0 bản ghi).")
        return []

    @staticmethod
    def to_langchain_documents(records: List[QARecord]) -> List[Document]:
        """Chuyển đổi danh sách QARecord thành LangChain Document objects."""
        docs: List[Document] = []
        for r in records:
            content = f"Câu hỏi: {r.question}\nNội dung: {r.answer}"
            metadata = {
                "record_id": r.record_id,
                "word": r.word,
                "sheet": r.sheet,
                "source": r.source,
                "level": r.level,
            }
            docs.append(Document(page_content=content, metadata=metadata))
        return docs
