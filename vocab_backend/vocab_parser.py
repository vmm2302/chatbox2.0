"""Vocabulary parser: Converts raw QA text or knowledge base records into rich structured data.
Also guarantees the required prefix 'Từ bạn tìm kiếm: <từ>' at the beginning of the reply.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Regex patterns matching vocabulary fields
RE_LEVEL = re.compile(r"^\*{0,2}Trình độ\*{0,2}:?\*{0,2}\s*(.*)$", re.IGNORECASE)
RE_PRON = re.compile(r"^\*{0,2}Phát âm\*{0,2}:?\*{0,2}\s*(.*)$", re.IGNORECASE)
RE_BULLET = re.compile(r"^(?:[•]\s*|[-*](?!\*)\s+|(?:Ví dụ|Example):\s*)(.+)$", re.IGNORECASE)

POS_NAMES = (
    r"Danh từ|Động từ|Tính từ|Trạng từ|Giới từ|Liên từ|Thán từ|Mạo từ|Đại từ|"
    r"Noun|Verb|Adjective|Adverb|Preposition|Conjunction|Interjection|Article|Pronoun"
)
POS_REGEX = re.compile(
    rf"^(?:###\s*)?(?:{POS_NAMES})(?:\s*\([^)]+\))?:?$",
    re.IGNORECASE,
)


def ensure_required_search_prefix(
    answer: str,
    word: Optional[str] = None,
    intent: Optional[str] = None,
) -> str:
    """Ensure the text answer begins with 'Từ tiếng Anh phù hợp: <word>' (for TRANSLATE_VIE_TO_ENG)
    or 'Từ bạn tìm kiếm: <word>' (for standard English word lookup) if a word is identified.
    """
    has_vn_accent = bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", (word or "").lower()))
    if not word or not word.strip() or has_vn_accent:
        m_ans = re.search(r"từ (?:bạn tìm kiếm|tiếng anh phù hợp)\s*:\s*([^\n\r]+)", answer, re.IGNORECASE)
        if m_ans:
            word = m_ans.group(1).strip().strip("* ")
        else:
            m_bold = re.search(r"từ \*\*([a-zA-Z0-9_\s\-',]+)\*\*", answer, re.IGNORECASE)
            if m_bold:
                word = m_bold.group(1).strip()

    if not word or not word.strip() or bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", word.lower())):
        return answer

    # Nếu câu trả lời là câu từ chối ngoài phạm vi, hỏi lại mơ hồ, hoặc không tìm thấy dữ liệu:
    # Tuyệt đối không chèn tiền tố để tránh gây hiểu lầm
    low = (answer or "").lower()
    if (
        "nằm ngoài phạm vi" in low
        or "chưa có dữ liệu" in low
        or "chưa tìm thấy dữ liệu" in low
        or "bạn đang muốn hỏi về từ vựng nào" in low
        or "vui lòng cung cấp từ tiếng anh" in low
        or "vui lòng nhập câu hỏi" in low
    ):
        return answer

    clean_word = word.strip()
    is_translation = (intent == "TRANSLATE_VIE_TO_ENG")
    prefix_label = "Từ tiếng Anh phù hợp" if is_translation else "Từ bạn tìm kiếm"
    prefix = f"{prefix_label}: {clean_word}"
    
    # Check if correct prefix already exists at the beginning
    normalized_start = answer.strip()[:80].lower()
    if normalized_start.startswith(f"{prefix_label.lower()}: {clean_word.lower()}"):
        return answer

    # If it starts with the other prefix or "Từ **word**:" or "Từ word:", replace it cleanly
    other_prefix_label = "Từ bạn tìm kiếm" if is_translation else "Từ tiếng Anh phù hợp"
    if (
        normalized_start.startswith(f"{other_prefix_label.lower()}:")
        or normalized_start.startswith(f"từ **{clean_word.lower()}**:")
        or normalized_start.startswith(f"từ {clean_word.lower()}:")
    ):
        first_line_end = answer.find("\n")
        if first_line_end != -1:
            return f"{prefix}\n\n" + answer[first_line_end:].lstrip()
        return prefix

    return f"{prefix}\n\n{answer}"


def parse_vocabulary_text(text: str, default_word: str = "", default_level: str = "A1") -> Optional[Dict[str, Any]]:
    """Parse text from knowledge base or ChatEngine into rich structured card information.
    Returns None if text is an out-of-scope rejection, small-talk, or clarification message.
    """
    if not text or not isinstance(text, str):
        return None

    low = text.lower()
    # Nếu là câu từ chối ngoài phạm vi hoặc yêu cầu làm rõ, không hiển thị dưới dạng VocabCard
    if (
        "nằm ngoài phạm vi" in low
        or "chưa có dữ liệu" in low
        or "chưa tìm thấy dữ liệu" in low
        or "bạn đang muốn hỏi về từ vựng nào" in low
        or "vui lòng cung cấp từ tiếng anh" in low
        or "vui lòng nhập câu hỏi" in low
    ):
        return None

    raw_lines = [line.strip() for line in (text or "").strip().split("\n")]
    
    word = default_word
    level = default_level or "A1"
    ipa = ""
    blocks: List[Dict[str, Any]] = []
    current_block: Optional[Dict[str, Any]] = None
    
    # Try detecting word from first line if "Từ bạn tìm kiếm: ...", "Từ tiếng Anh phù hợp: ...", or "Từ **word**:"
    for line in raw_lines[:5]:
        low_l = line.lower()
        if low_l.startswith("từ bạn tìm kiếm:") or low_l.startswith("từ tiếng anh phù hợp:"):
            detected = line.split(":", 1)[1].strip().strip("*")
            if detected:
                word = detected
        elif low_l.startswith("từ **") and "**:" in line:
            m = re.search(r"từ \*\*(.*?)\*\*:", line, re.IGNORECASE)
            if m:
                word = m.group(1).strip()

    # If word is still empty or contains Vietnamese accents, search deeper in the text
    has_vn_accent = bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", (word or "").lower()))
    if not word or has_vn_accent:
        m_deeper = re.search(r"từ (?:bạn tìm kiếm|tiếng anh phù hợp)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        if m_deeper:
            word = m_deeper.group(1).strip().strip("* ")
        else:
            m_b = re.search(r"từ \*\*([a-zA-Z0-9_\s\-',]+)\*\*", text, re.IGNORECASE)
            if m_b:
                word = m_b.group(1).strip()
            elif has_vn_accent:
                word = ""

    idx = 0
    n = len(raw_lines)
    while idx < n:
        line = raw_lines[idx]
        if not line:
            idx += 1
            continue

        # Ignore prefix line in card parsing
        low_line = line.lower()
        if (
            low_line.startswith("từ bạn tìm kiếm:")
            or low_line.startswith("từ tiếng anh phù hợp:")
            or low_line.startswith("từ **")
            or re.match(r"^(?:\*\*)?(?:\d+[\.\)]\s*)?từ (?:bạn tìm kiếm|tiếng anh phù hợp):", low_line)
        ):
            idx += 1
            continue

        # 1. Trình độ (Level)
        m_lvl = RE_LEVEL.match(line)
        if m_lvl:
            val = m_lvl.group(1).strip()
            # Clean up markdown bold
            val = val.replace("*", "").strip()
            if val:
                level = val
            idx += 1
            continue

        # 2. Phát âm (Pronunciation)
        m_prn = RE_PRON.match(line)
        if m_prn:
            val = m_prn.group(1).strip()
            val = val.replace("*", "").strip()
            if val:
                ipa = val
            idx += 1
            continue

        # 3. Từ loại (Part of Speech)
        clean_pos_line = line.rstrip(":").strip()
        if clean_pos_line.startswith("###"):
            clean_pos_line = clean_pos_line[3:].strip()

        is_pos = bool(POS_REGEX.match(clean_pos_line))
        if not is_pos and ":" in line:
            prefix = line.split(":", 1)[0].strip()
            if POS_REGEX.match(prefix):
                clean_pos_line = prefix
                is_pos = True

        if is_pos:
            current_block = {"pos": clean_pos_line, "meanings": []}
            blocks.append(current_block)
            idx += 1
            continue

        if current_block is None:
            current_block = {"pos": "Định nghĩa chung", "meanings": []}
            blocks.append(current_block)

        # 4. Check for bullet line with example
        m_bul = RE_BULLET.match(line)
        if m_bul:
            ex_txt = m_bul.group(1).strip()
            if current_block["meanings"]:
                current_block["meanings"][-1]["examples"].append(ex_txt)
            else:
                current_block["meanings"].append({
                    "definition": "",
                    "examples": [ex_txt],
                })
            idx += 1
            continue

        # 5. Meaning line
        m_txt = line.strip()
        m_txt = re.sub(r"^(?:\*\*)?\d+[\.\)]\s*(?:\*\*)?", "", m_txt).strip()
        m_txt = re.sub(r"^\*\*(.*?)\*\*$", r"\1", m_txt).strip()
        m_txt = m_txt.strip("* ")

        examples: List[str] = []
        idx += 1

        while idx < n:
            next_line = raw_lines[idx]
            if not next_line:
                idx += 1
                continue

            clean_nl = next_line.rstrip(":").strip().lstrip("#").strip()
            if (
                RE_LEVEL.match(next_line)
                or RE_PRON.match(next_line)
                or POS_REGEX.match(clean_nl)
                or (":" in next_line and POS_REGEX.match(next_line.split(":", 1)[0].strip().lstrip("#").strip()))
                or next_line.startswith("**")
                or re.match(r"^\d+[\.\)]", next_line)
            ):
                break

            m_nbul = RE_BULLET.match(next_line)
            if m_nbul:
                ex_text = m_nbul.group(1).strip().lstrip("•-* \t").strip()
                if ex_text:
                    examples.append(ex_text)
                idx += 1
            elif next_line.startswith(("•", "   •")):
                ex_text = next_line.lstrip("•-* \t").strip()
                if ex_text:
                    examples.append(ex_text)
                idx += 1
            else:
                break

        current_block["meanings"].append({
            "definition": m_txt,
            "examples": examples,
        })

    # Lọc và làm sạch các khối nghĩa, loại bỏ khối "Định nghĩa chung" rỗng hoặc dòng tiền tố thừa
    valid_blocks = []
    for b in blocks:
        filtered_meanings = []
        for m in b.get("meanings", []):
            def_text = (m.get("definition") or "").strip()
            if re.match(r"^(?:\*\*)?(?:\d+[\.\)]\s*)?từ bạn tìm kiếm:", def_text, re.IGNORECASE):
                continue
            clean_def = re.sub(r"^(?:\*\*)?\d+[\.\)]\s*(?:\*\*)?", "", def_text).strip()
            clean_def = re.sub(r"^\*\*(.*?)\*\*$", r"\1", clean_def).strip()
            clean_def = clean_def.strip("* ")
            m["definition"] = clean_def
            if clean_def or m.get("examples"):
                filtered_meanings.append(m)
        if filtered_meanings:
            # Bỏ qua block "Định nghĩa chung" nếu nó không có definition nào thực sự
            if b.get("pos") == "Định nghĩa chung" and not any(m.get("definition") for m in filtered_meanings):
                continue
            b["meanings"] = filtered_meanings
            valid_blocks.append(b)

    blocks = valid_blocks

    # CEFR Level visual attributes (dynamically generated for any level discovered in data)
    level_normalized = (level or "A1").upper().strip()
    KNOWN_METAS = {
        "A1": {"name": "Beginner", "vn": "Khởi đầu", "color": "emerald", "badge": "🌱 A1"},
        "A2": {"name": "Elementary", "vn": "Nền tảng", "color": "sky", "badge": "🌿 A2"},
        "B1": {"name": "Intermediate", "vn": "Trung cấp", "color": "amber", "badge": "🚀 B1"},
        "B2": {"name": "Upper-Intermediate", "vn": "Nâng cao", "color": "purple", "badge": "🌟 B2"},
        "C1": {"name": "Advanced", "vn": "Cao cấp", "color": "rose", "badge": "🔥 C1"},
        "C2": {"name": "Proficiency", "vn": "Thành thạo", "color": "indigo", "badge": "👑 C2"},
    }
    if level_normalized in KNOWN_METAS:
        level_meta = KNOWN_METAS[level_normalized]
    else:
        # Dynamically generate styling for any newly discovered level from data
        PALETTES = ["teal", "cyan", "blue", "violet", "fuchsia", "pink", "orange"]
        palette = PALETTES[sum(ord(c) for c in level_normalized) % len(PALETTES)]
        level_meta = {
            "name": level_normalized,
            "vn": f"Cấp độ {level_normalized}",
            "color": palette,
            "badge": f"🏷️ {level_normalized}",
        }

    # Extract primary definition & example for quick flashcard / bookmark
    primary_pos = blocks[0]["pos"] if blocks else ""
    primary_meaning = ""
    primary_example = ""
    for b in blocks:
        for m in b.get("meanings", []):
            if m.get("definition") and not primary_meaning:
                primary_meaning = m.get("definition")
            if m.get("examples") and not primary_example:
                primary_example = m.get("examples")[0]
            if primary_meaning and primary_example:
                break
        if primary_meaning and primary_example:
            break

    return {
        "word": word or default_word,
        "level": level_normalized,
        "level_meta": level_meta,
        "ipa": ipa,
        "primary_pos": primary_pos,
        "primary_meaning": primary_meaning,
        "primary_example": primary_example,
        "blocks": blocks,
    }
