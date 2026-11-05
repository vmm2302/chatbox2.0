"""Comprehensive End-to-End Test for Multi-Level Ingestion and Dynamic Discovery Flow.
Simulates:
1. Fresh batch ingestion of a document containing B1, B2, C1 records.
2. Ingesting another document containing the same word in a DIFFERENT level (allowed)
   and the same word in the SAME level (skipped as duplicate).
3. Verifying GET /api/words/levels returns the newly added levels (A1, A2, B1, B2, C1).
4. Verifying GET /api/words/discover?level=B1 returns the new B1 words.
5. Verifying clean teardown so test data does not affect production qa_records.jsonl.
"""

import io
import json
import os
import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path

# Enforce offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader
from vocab_backend.api_server import (
    get_available_levels,
    discover_words,
    reload_records,
)


def create_csv_file(filepath: Path, entries: list):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("Từ vựng,Câu hỏi,Câu trả lời,Trình độ\n")
        for item in entries:
            w, m, lvl = item
            f.write(f'"{w}","{w} nghĩa là gì?","{m}","{lvl}"\n')


def run_test():
    test_dir = PROJECT_ROOT / "temp_e2e_levels_test"
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:6]
    test_jsonl = test_dir / "qa_records_test.jsonl"
    test_manifest = test_dir / "manifest_test.json"
    test_chroma = test_dir / "chroma_test"
    test_chroma.mkdir(parents=True, exist_ok=True)

    # Backup settings
    orig_chroma = settings.CHROMA_DIR
    orig_jsonl = settings.PROCESSED_JSONL_PATH
    object.__setattr__(settings, "CHROMA_DIR", test_chroma)
    object.__setattr__(settings, "PROCESSED_JSONL_PATH", test_jsonl)

    try:
        # Create initial test dataset with A1 and A2 words
        initial_records = [
            QARecord(record_id=f"REC_a1_{uid}", word=f"apple_{uid}", level="A1", question=f"apple_{uid} nghĩa là gì?", answer=f"Trình độ: A1\nQuả táo.", source="init.csv"),
            QARecord(record_id=f"REC_a2_{uid}", word=f"banana_{uid}", level="A2", question=f"banana_{uid} nghĩa là gì?", answer=f"Trình độ: A2\nQuả chuối.", source="init.csv"),
        ]
        loader = QALoader()
        loader.processed_jsonl_path = test_jsonl
        loader.save_to_jsonl(initial_records)

        manager = BatchIngestionManager(loader=loader, manifest_path=test_manifest)

        print("--- Step 1: Ingest higher level document (B1, B2, C1) ---")
        f1 = test_dir / f"higher_levels_{uid}.csv"
        create_csv_file(f1, [
            (f"mitigate_{uid}", "Trình độ: B1\nLàm giảm nhẹ rủi ro.", "B1"),
            (f"sustain_{uid}", "Trình độ: B2\nDuy trì bền vững.", "B2"),
            (f"ephemeral_{uid}", "Trình độ: C1\nChóng tàn, phù du.", "C1"),
        ])

        report1 = manager.ingest_batch([f1], batch_size=8)
        assert report1.total_files == 1
        assert report1.success_count == 1
        assert report1.total_records_added == 3, f"Expected 3 records added, got {report1.total_records_added}"
        assert report1.total_duplicates_skipped == 0
        print(f"Passed Step 1: Added 3 records with levels B1, B2, C1 successfully!")

        print("--- Step 2: Ingest same word in different level vs same level ---")
        f2 = test_dir / f"duplicate_rules_{uid}.csv"
        create_csv_file(f2, [
            # 1. apple in B1 (previously apple was only in A1) -> MUST BE ADDED (same word, different level)
            (f"apple_{uid}", "Trình độ: B1\nQuả táo (ngữ cảnh B1).", "B1"),
            # 2. mitigate in B1 (previously mitigate was already in B1) -> MUST BE SKIPPED (same word, same level)
            (f"mitigate_{uid}", "Trình độ: B1\nLàm giảm nhẹ (trùng B1).", "B1"),
        ])

        report2 = manager.ingest_batch([f2], batch_size=8)
        assert report2.total_files == 1
        assert report2.success_count == 1
        assert report2.total_records_added == 1, f"Expected 1 record added (apple B1), got {report2.total_records_added}"
        assert report2.total_duplicates_skipped == 1, f"Expected 1 record skipped (mitigate B1), got {report2.total_duplicates_skipped}"
        print("Passed Step 2: Same word in different level added, same word in same level skipped!")

        print("--- Step 3: Verify dynamic level discovery from qa_records.jsonl ---")
        reload_records()
        levels_data = get_available_levels()
        expected_levels = {"A1", "A2", "B1", "B2", "C1"}
        actual_levels = set(levels_data["levels"])
        assert expected_levels.issubset(actual_levels), f"Expected levels {expected_levels} to be in {actual_levels}"
        print(f"Passed Step 3: Discovered all levels dynamically: {levels_data['levels']}")
        print(f"Counts per level: {levels_data['counts']}")

        print("--- Step 4: Verify discover_words for new levels (B1, B2) ---")
        disco_b1 = discover_words(level="B1", count=5)
        assert disco_b1["level"] == "B1"
        assert len(disco_b1["words"]) >= 2  # mitigate_uid and apple_uid
        b1_words = [c["word"] for c in disco_b1["words"]]
        assert f"mitigate_{uid}" in b1_words or f"apple_{uid}" in b1_words
        print(f"Passed Step 4: discover_words(B1) returned: {b1_words}")

        print("\n=======================================================")
        print("ALL MULTI-LEVEL E2E INTEGRATION FLOW TESTS PASSED 100%!")
        print("=======================================================")

    finally:
        # Restore settings
        object.__setattr__(settings, "CHROMA_DIR", orig_chroma)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", orig_jsonl)
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
        reload_records()


if __name__ == "__main__":
    run_test()
