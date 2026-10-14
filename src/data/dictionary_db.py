"""Module kết nối và tra cứu cơ sở dữ liệu từ điển Anh - Việt (dictionary_en_vi.db).

Hỗ trợ:
- Tải chỉ mục từ vựng vào bộ nhớ (In-memory Indexing) giúp tra cứu hơn 3.000 từ trong < 0.5s.
- Lấy phiên âm chuẩn quốc tế (IPA), ưu tiên giọng Anh - Anh (BrE/UK).
- Lấy định nghĩa tiếng Việt kèm phân loại từ loại (POS) và câu ví dụ minh họa thực tế.
- Định dạng câu trả lời chuẩn hóa theo cấu trúc của qa_records.jsonl.
"""

import logging
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config.settings import settings

logger = logging.getLogger(__name__)

# Ánh xạ mã từ loại (POS code) từ database sang tiêu đề chuẩn tiếng Việt / tiếng Anh
DB_POS_MAP: Dict[str, str] = {
    "N": "Danh từ (Noun)",
    "V": "Động từ (Verb)",
    "A": "Tính từ (Adjective)",
    "D": "Trạng từ (Adverb)",
    "E": "Giới từ (Preposition)",
    "C": "Liên từ (Conjunction)",
    "P": "Đại từ (Pronoun)",
    "M": "Số từ (Number)",
    "O": "Thán từ (Exclamation)",
    "noun": "Danh từ (Noun)",
    "verb": "Động từ (Verb)",
    "adj": "Tính từ (Adjective)",
    "adv": "Trạng từ (Adverb)",
    "pron": "Đại từ (Pronoun)",
    "idiom": "Thành ngữ (Idiom)",
}

# Ánh xạ từ loại viết tắt từ tệp Oxford 3000 PDF
OXFORD_POS_MAP: Dict[str, str] = {
    "n.": "Danh từ (Noun)",
    "n": "Danh từ (Noun)",
    "v.": "Động từ (Verb)",
    "v": "Động từ (Verb)",
    "adj.": "Tính từ (Adjective)",
    "adj": "Tính từ (Adjective)",
    "adv.": "Trạng từ (Adverb)",
    "adv": "Trạng từ (Adverb)",
    "prep.": "Giới từ (Preposition)",
    "prep": "Giới từ (Preposition)",
    "conj.": "Liên từ (Conjunction)",
    "conj": "Liên từ (Conjunction)",
    "pron.": "Đại từ (Pronoun)",
    "pron": "Đại từ (Pronoun)",
    "det.": "Từ hạn định (Determiner)",
    "det": "Từ hạn định (Determiner)",
    "number": "Số từ (Number)",
    "exclam.": "Thán từ (Exclamation)",
    "exclam": "Thán từ (Exclamation)",
    "modal v.": "Động từ khuyết thiếu (Modal Verb)",
    "auxiliary": "Trợ động từ (Auxiliary Verb)",
    "auxiliary v.": "Trợ động từ (Auxiliary Verb)",
    "infinitive marker": "Đầu từ nguyên mẫu (Infinitive Marker)",
    "indefinite article": "Mạo từ (Article)",
    "definite article": "Mạo từ (Article)",
    "article": "Mạo từ (Article)",
}


class DictionaryDBService:
    """Dịch vụ tra cứu từ điển SQLite từ tệp dictionary_en_vi.db."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else settings.DICTIONARY_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self._word_id_cache: Optional[Dict[str, int]] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Khởi tạo và giữ kết nối SQLite tái sử dụng an toàn."""
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Không tìm thấy cơ sở dữ liệu từ điển tại: {self.db_path}")
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        return self._conn

    def _ensure_cache_loaded(self) -> None:
        """Tải toàn bộ bảng words vào bộ nhớ để tra cứu O(1)."""
        if self._word_id_cache is not None:
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, lower(word) FROM words WHERE word IS NOT NULL;")
        rows = cursor.fetchall()
        self._word_id_cache = {w.strip(): wid for wid, w in rows if w}
        logger.info("DictionaryDBService: Đã tải %d từ vào bộ nhớ đệm.", len(self._word_id_cache))

    def lookup(self, word: str) -> Optional[Dict[str, Any]]:
        """Tra cứu thông tin từ vựng: IPA, định nghĩa theo từ loại, ví dụ.
        
        Args:
            word: Từ vựng tiếng Anh cần tra cứu.

        Returns:
            Dict chứa chi tiết phiên âm và nghĩa, hoặc None nếu không tìm thấy.
        """
        if not word:
            return None

        self._ensure_cache_loaded()
        clean_w = unicodedata.normalize("NFC", word).strip().lower()
        # Chuẩn hóa dấu nháy đơn
        clean_w = clean_w.replace("’", "'").replace("`", "'")

        wid = self._word_id_cache.get(clean_w)
        # Thử tìm theo biến thể dấu gạch nối hoặc dấu phẩy/gạch chéo
        if wid is None and "/" in clean_w:
            wid = self._word_id_cache.get(clean_w.split("/")[0].strip())
        if wid is None and "," in clean_w:
            wid = self._word_id_cache.get(clean_w.split(",")[0].strip())
        if wid is None and " " in clean_w:
            wid = self._word_id_cache.get(clean_w.replace(" ", "-"))

        if wid is None:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        # 1. Lấy phát âm IPA
        cursor.execute("SELECT ipa, region FROM pronunciations WHERE word_id = ?", (wid,))
        pron_rows = cursor.fetchall()
        ipa_str = ""
        for ipa, region in pron_rows:
            if not ipa:
                continue
            clean_ipa = ipa.strip()
            # Ưu tiên giọng BrE / UK
            if region and region.upper() in ("BRE", "UK"):
                ipa_str = clean_ipa
                break
            if not ipa_str:
                ipa_str = clean_ipa

        # 2. Lấy định nghĩa và ví dụ ghép theo từ loại (POS)
        query = """
            SELECT d.pos, d.sub_pos, d.definition, wd.example
            FROM word_definitions wd
            JOIN definitions d ON wd.definition_id = d.id
            WHERE wd.word_id = ?
            ORDER BY d.pos, d.id
        """
        cursor.execute(query, (wid,))
        def_rows = cursor.fetchall()

        defs_by_pos: Dict[str, List[Dict[str, Any]]] = {}
        for pos, sub_pos, definition, example in def_rows:
            if not definition:
                continue
            pos_key = pos or "OTHER"
            if pos_key not in defs_by_pos:
                defs_by_pos[pos_key] = []
            
            clean_def = definition.strip()
            # Bỏ dấu chấm thừa ở cuối nếu có
            if clean_def.endswith("."):
                clean_def = clean_def[:-1].strip()

            defs_by_pos[pos_key].append({
                "definition": clean_def,
                "example": example.strip() if example else None,
                "sub_pos": sub_pos,
            })

        return {
            "word_id": wid,
            "word": word,
            "ipa": ipa_str,
            "definitions_by_pos": defs_by_pos,
        }

    def format_answer(
        self,
        word: str,
        level: str,
        lookup_data: Optional[Dict[str, Any]] = None,
        oxford_pos_tokens: Optional[List[str]] = None,
    ) -> str:
        """Định dạng cấu trúc câu trả lời chuẩn xác cho qa_records.jsonl.

        Cấu trúc chuẩn:
        Trình độ: A1

        Phát âm: /əˈbaʊt/

        Giới từ (Preposition):

        Về
           • Do you know much about this old city?

        Trạng từ (Adverb):
        ...
        """
        parts: List[str] = []
        if level:
            parts.append(f"Trình độ: {level.upper()}")

        if lookup_data and lookup_data.get("ipa"):
            ipa_val = lookup_data["ipa"].strip()
            if not ipa_val.startswith("/"):
                ipa_val = f"/{ipa_val}"
            if not ipa_val.endswith("/"):
                ipa_val = f"{ipa_val}/"
            parts.append(f"Phát âm: {ipa_val}")

        # Trường hợp có dữ liệu định nghĩa từ DB
        if lookup_data and lookup_data.get("definitions_by_pos"):
            defs_by_pos = lookup_data["definitions_by_pos"]
            for pos_code, def_items in defs_by_pos.items():
                pos_title = DB_POS_MAP.get(pos_code, f"Từ loại ({pos_code})")
                section_lines = [f"{pos_title}:"]

                # Lấy tối đa 4 định nghĩa tiêu biểu nhất cho mỗi từ loại để câu trả lời cô đọng
                for item in def_items[:4]:
                    d_text = item["definition"]
                    ex_text = item.get("example")
                    if ex_text:
                        section_lines.append(f"{d_text}\n   • {ex_text}")
                    else:
                        section_lines.append(d_text)

                parts.append("\n\n".join(section_lines))

        # Trường hợp từ không có trong DB nhưng có thông tin từ Oxford PDF
        elif oxford_pos_tokens:
            pos_headers = []
            for token in oxford_pos_tokens:
                token_clean = token.lower().strip()
                header = OXFORD_POS_MAP.get(token_clean)
                if header and header not in pos_headers:
                    pos_headers.append(header)

            if pos_headers:
                for ph in pos_headers:
                    parts.append(f"{ph}:\n\nTừ vựng thuộc danh mục Oxford 3000 (Trình độ {level.upper()}).")
            else:
                parts.append(f"Từ vựng tiếng Anh thuộc danh mục Oxford 3000 (Trình độ {level.upper()}).")
        else:
            parts.append(f"Từ vựng tiếng Anh thuộc danh mục Oxford 3000 (Trình độ {level.upper()}).")

        return "\n\n".join(parts)

    def close(self) -> None:
        """Đóng kết nối cơ sở dữ liệu khi không còn sử dụng."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
