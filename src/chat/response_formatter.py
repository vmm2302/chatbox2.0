"""Module chuẩn hóa và định dạng câu trả lời từ vựng tiếng Anh (Vocabulary Response Formatter).

Đảm bảo tuân thủ nghiêm ngặt các quy tắc format bắt buộc:
1. Mỗi từ loại bắt đầu ở một dòng riêng (### Part of Speech).
2. Mỗi meaning nằm ở một dòng riêng (**1. Meaning**).
3. Example nằm ở dòng NGAY BÊN DƯỚI meaning tương ứng (• Example).
4. Giữa các meaning có một dòng trống để dễ đọc.
5. Nếu một meaning có nhiều example: mỗi example xuống dòng riêng.
6. Không gộp: 'Meaning • Example' thành một dòng duy nhất.
7. Giữ nguyên 100% nội dung nghĩa và example được lấy từ Knowledge Base.
8. Hoàn toàn không dùng bảng Markdown cho phần meaning/example.
"""

import re
from typing import Dict, List, Optional, Tuple


# Danh sách các từ loại tiếng Việt và tiếng Anh phổ biến
POS_NAMES = (
    r"Danh từ|Động từ|Tính từ|Trạng từ|Giới từ|Liên từ|Thán từ|Mạo từ|Đại từ|"
    r"Noun|Verb|Adjective|Adverb|Preposition|Conjunction|Interjection|Article|Pronoun"
)
POS_REGEX = re.compile(
    rf"^(?:###\s*)?(?:{POS_NAMES})(?:\s*\([^)]+\))?:?$",
    re.IGNORECASE
)

RE_LEVEL = re.compile(r"^(?:\*\*)?Trình độ:(?:\*\*)?\s*(.*)$", re.IGNORECASE)
RE_PRON = re.compile(r"^(?:\*\*)?Phát âm:(?:\*\*)?\s*(.*)$", re.IGNORECASE)
RE_BULLET = re.compile(r"^(?:[•\-\*]\s*|(?:Ví dụ|Example):\s*)(.+)$", re.IGNORECASE)


def format_vocabulary_response(text: str) -> str:
    """Chuẩn hóa và định dạng văn bản câu trả lời từ vựng theo cấu trúc Markdown rõ ràng.

    Args:
        text: Nội dung văn bản câu trả lời từ Knowledge Base hoặc LLM.

    Returns:
        str: Nội dung đã được định dạng chuẩn với xuống dòng và thụt lề hợp lý.
    """
    if not text or not isinstance(text, str):
        return text

    raw_lines = [line.strip() for line in text.strip().split("\n")]
    if not raw_lines:
        return text

    # Kiểm tra xem văn bản có chứa các trường thông tin từ vựng không
    has_vocab_feature = any(
        RE_LEVEL.match(line)
        or RE_PRON.match(line)
        or POS_REGEX.match(line.rstrip(":").strip())
        or (":" in line and POS_REGEX.match(line.split(":", 1)[0].strip()))
        for line in raw_lines
    )
    if not has_vocab_feature:
        # Nếu là câu xã giao, từ chối ngoài phạm vi, hoặc văn bản tự do không theo khuôn từ điển
        return text

    headers: List[str] = []
    # blocks: danh sách các từ loại, mỗi khối chứa danh sách tuples: (meaning, [examples])
    blocks: List[Dict[str, any]] = []

    idx = 0
    n = len(raw_lines)

    while idx < n:
        line = raw_lines[idx]
        if not line:
            idx += 1
            continue

        # 1. Trình độ (Level)
        m_lvl = RE_LEVEL.match(line)
        if m_lvl:
            lvl_val = m_lvl.group(1).strip()
            headers.append(f"**Trình độ:** {lvl_val}")
            idx += 1
            continue

        # 2. Phát âm (Pronunciation)
        m_prn = RE_PRON.match(line)
        if m_prn:
            prn_val = m_prn.group(1).strip()
            headers.append(f"**Phát âm:** {prn_val}")
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
            blocks.append({"title": clean_pos_line, "meanings": []})
            idx += 1
            continue

        # Nếu chưa có block từ loại nào mà đã có nội dung giải nghĩa
        if not blocks:
            blocks.append({"title": None, "meanings": []})

        # 4. Kiểm tra trường hợp dòng bị gộp: "Meaning • Example 1 [• Example 2]"
        if (" • " in line or " - " in line) and not line.startswith(("•", "-", "*")):
            # Tách meaning và các example
            parts = re.split(r"\s+[•\-]\s+", line)
            if len(parts) >= 2:
                m_txt = parts[0].strip()
                ex_list = [p.strip() for p in parts[1:] if p.strip()]
                # Làm sạch số thứ tự hoặc in đậm cũ nếu có
                m_txt = re.sub(r"^(?:\*\*)?\d+[\.\)]\s*(?:\*\*)?", "", m_txt).strip()
                m_txt = re.sub(r"^\*\*(.*?)\*\*$", r"\1", m_txt).strip()
                blocks[-1]["meanings"].append((m_txt, ex_list))
                idx += 1
                continue

        # 5. Nếu dòng bắt đầu bằng bullet example đứng độc lập
        m_bul = RE_BULLET.match(line)
        if m_bul:
            ex_txt = m_bul.group(1).strip()
            if blocks[-1]["meanings"]:
                blocks[-1]["meanings"][-1][1].append(ex_txt)
            else:
                blocks[-1]["meanings"].append(("", [ex_txt]))
            idx += 1
            continue

        # 6. Dòng là một Meaning thông thường
        m_txt = line.strip()
        m_txt = re.sub(r"^(?:\*\*)?\d+[\.\)]\s*(?:\*\*)?", "", m_txt).strip()
        m_txt = re.sub(r"^\*\*(.*?)\*\*$", r"\1", m_txt).strip()

        examples: List[str] = []
        idx += 1

        while idx < n:
            next_line = raw_lines[idx]
            if not next_line:
                idx += 1
                continue

            # Nếu next_line là header hoặc từ loại mới -> ngắt meaning hiện tại
            if (
                RE_LEVEL.match(next_line)
                or RE_PRON.match(next_line)
                or POS_REGEX.match(next_line.rstrip(":").strip())
                or (":" in next_line and POS_REGEX.match(next_line.split(":", 1)[0].strip()))
            ):
                break

            # Nếu next_line là bullet example
            m_nbul = RE_BULLET.match(next_line)
            if m_nbul:
                ex_content = m_nbul.group(1).strip()
                # Kiểm tra nếu trong next_line có nhiều bullet gộp: "• Ex1 • Ex2"
                if " • " in ex_content:
                    for sub_ex in ex_content.split(" • "):
                        sub_clean = sub_ex.strip()
                        if sub_clean:
                            examples.append(sub_clean)
                else:
                    examples.append(ex_content)
                idx += 1
            elif " • " in next_line and next_line.startswith(("•", "-", "*", "   •")):
                sub_parts = next_line.split(" • ")
                for sp in sub_parts:
                    sp_clean = sp.lstrip("•-* \t").strip()
                    if sp_clean:
                        examples.append(sp_clean)
                idx += 1
            else:
                # Gặp meaning tiếp theo
                break

        blocks[-1]["meanings"].append((m_txt, examples))

    # Ghép lại thành chuỗi Markdown hoàn chỉnh
    paragraphs: List[str] = []

    # Thêm phần Header (Trình độ, Phát âm)
    if headers:
        paragraphs.extend(headers)

    # Thêm từng khối Từ loại và các Nghĩa / Ví dụ
    for block in blocks:
        pos_title = block.get("title")
        if pos_title:
            paragraphs.append(f"### {pos_title}")

        meanings = block.get("meanings", [])
        for m_idx, (m_text, exs) in enumerate(meanings, 1):
            m_lines: List[str] = []
            if m_text:
                # In đậm meaning và thêm 2 dấu cách cuối dòng để tạo thẻ <br> trong Markdown
                m_lines.append(f"**{m_idx}. {m_text}**  ")

            for ex in exs:
                # Mỗi example nằm ở dòng NGAY BÊN DƯỚI meaning
                m_lines.append(f"• {ex}  ")

            if m_lines:
                # Loại bỏ 2 dấu cách thừa ở dòng cuối cùng của meaning block
                m_lines[-1] = m_lines[-1].rstrip()
                paragraphs.append("\n".join(m_lines))

    return "\n\n".join(paragraphs)
