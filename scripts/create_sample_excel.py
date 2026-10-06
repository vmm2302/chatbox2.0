"""Script tạo tệp Excel mẫu để người dùng tham khảo cấu trúc nhập liệu từ vựng."""

import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# Đảm bảo đường dẫn gốc
project_root = Path(__file__).resolve().parent.parent
output_path = project_root / "data" / "mau_nhap_lieu_tuvung.xlsx"


def create_sample_excel(target_file: Path):
    zbuf = io.BytesIO()

    headers = ["Từ vựng", "Câu hỏi", "Câu trả lời", "Trình độ", "Nguồn"]
    rows = [
        [
            "resilient",
            "resilient nghĩa là gì?",
            "Phát âm: /rɪˈzɪl.jənt/\nTính từ:\n- Có khả năng phục hồi nhanh chóng sau khó khăn, nghịch cảnh.\nVí dụ: He is remarkably resilient in face of challenges.\nTrình độ: B2",
            "B2",
            "Cambridge Dictionary"
        ],
        [
            "serendipity",
            "serendipity nghĩa là gì?",
            "Phát âm: /ˌser.ənˈdɪp.ə.ti/\nDanh từ:\n- Sự may mắn tình cờ, cơ duyên ngẫu nhiên tìm thấy điều tốt đẹp.\nVí dụ: Finding this quiet cafe was pure serendipity.\nTrình độ: C1",
            "C1",
            "Oxford Learner's Dictionary"
        ],
        [
            "ubiquitous",
            "ubiquitous nghĩa là gì?",
            "Phát âm: /juːˈbɪk.wə.təs/\nTính từ:\n- Có mặt ở khắp nơi, nhan nhản, vô cùng phổ biến.\nVí dụ: Smartphones have become ubiquitous in modern society.\nTrình độ: C1",
            "C1",
            "Cambridge Dictionary"
        ]
    ]

    all_data = [headers] + rows
    unique_strings = []
    str_map = {}

    for row in all_data:
        for cell in row:
            s = str(cell)
            if s not in str_map:
                str_map[s] = len(unique_strings)
                unique_strings.append(s)

    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        ct = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""
        z.writestr("[Content_Types].xml", ct)

        # _rels/.rels
        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
        z.writestr("_rels/.rels", rels)

        # xl/_rels/workbook.xml.rels
        wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)

        # xl/workbook.xml
        wb = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="TuVungMau" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""
        z.writestr("xl/workbook.xml", wb)

        # xl/sharedStrings.xml
        sst_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(unique_strings)}" uniqueCount="{len(unique_strings)}">'
        ]
        for s in unique_strings:
            escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sst_parts.append(f"<si><t>{escaped}</t></si>")
        sst_parts.append("</sst>")
        z.writestr("xl/sharedStrings.xml", "".join(sst_parts))

        # xl/worksheets/sheet1.xml
        def idx_to_col(i):
            res = ""
            i += 1
            while i > 0:
                i, rem = divmod(i - 1, 26)
                res = chr(65 + rem) + res
            return res

        sh_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
            "<sheetData>"
        ]
        for r_idx, row in enumerate(all_data, 1):
            sh_parts.append(f'<row r="{r_idx}">')
            for c_idx, cell in enumerate(row):
                col_name = idx_to_col(c_idx)
                s_idx = str_map[str(cell)]
                sh_parts.append(f'<c r="{col_name}{r_idx}" t="s"><v>{s_idx}</v></c>')
            sh_parts.append("</row>")
        sh_parts.append("</sheetData></worksheet>")
        z.writestr("xl/worksheets/sheet1.xml", "".join(sh_parts))

    target_file.parent.mkdir(parents=True, exist_ok=True)
    with open(target_file, "wb") as f:
        f.write(zbuf.getvalue())
    print(f"[OK] Đã tạo thành công tệp Excel mẫu tại: {target_file}")


if __name__ == "__main__":
    create_sample_excel(output_path)
