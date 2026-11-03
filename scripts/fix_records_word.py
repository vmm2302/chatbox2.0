"""Migration script: Fix missing word fields in data/processed/qa_records.jsonl."""

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import QALoader

jsonl_path = Path("data/processed/qa_records.jsonl")
backup_path = Path("data/processed/qa_records.jsonl.bak_missing_words")

if not backup_path.exists():
    shutil.copy2(jsonl_path, backup_path)
    print(f"Backed up {jsonl_path} to {backup_path}")

loader = QALoader()
updated_count = 0
total_count = 0

fixed_lines = []
with open(jsonl_path, "r", encoding="utf-8") as f:
    for line in f:
        clean = line.strip()
        if not clean:
            continue
        total_count += 1
        data = json.loads(clean)
        word = (data.get("word") or "").strip()
        if not word:
            rec_word, rec_lvl = loader._extract_word_and_level_fallback(
                data.get("question", ""), data.get("answer", "")
            )
            if rec_word:
                data["word"] = rec_word
                updated_count += 1
            if not data.get("level") and rec_lvl:
                data["level"] = rec_lvl
        fixed_lines.append(json.dumps(data, ensure_ascii=False) + "\n")

with open(jsonl_path, "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print(f"Migration completed: Total {total_count} records. Updated {updated_count} records with recovered words.")
