import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.core.models import QARecord
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loader import QALoader


class TestBidirectionalQAIngestion(unittest.TestCase):
    def setUp(self):
        self.test_dir = PROJECT_ROOT / f"temp_bidirectional_test_{uuid.uuid4().hex[:6]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.test_jsonl = self.test_dir / "qa_records_test.jsonl"
        self.test_manifest = self.test_dir / "manifest_test.json"
        self.test_chroma = self.test_dir / "chroma_test"

        self.orig_chroma = settings.CHROMA_DIR
        self.orig_jsonl = settings.PROCESSED_JSONL_PATH
        object.__setattr__(settings, "CHROMA_DIR", self.test_chroma)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", self.test_jsonl)

        self.loader = QALoader()
        self.loader.processed_jsonl_path = self.test_jsonl
        self.manager = BatchIngestionManager(loader=self.loader, manifest_path=self.test_manifest)

    def tearDown(self):
        object.__setattr__(settings, "CHROMA_DIR", self.orig_chroma)
        object.__setattr__(settings, "PROCESSED_JSONL_PATH", self.orig_jsonl)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_bidirectional_questions_for_same_word_and_level_accepted(self):
        """Verify En->Vi and Vi->En questions for the same word in the same level are both kept."""
        f_csv = self.test_dir / "vocab_dual_direction.csv"
        with open(f_csv, "w", encoding="utf-8") as f:
            f.write("Từ vựng,Câu hỏi,Câu trả lời,Trình độ\n")
            # Direction 1: En -> Vi
            f.write('"absolutely","absolutely nghĩa là gì?","Từ bạn tìm kiếm: absolutely\\n\\nTrình độ: B1\\nTuyệt đối.","B1"\n')
            # Direction 2: Vi -> En (same word, same level, different question!)
            f.write('"absolutely","Từ ""Tuyệt đối, hoàn toàn"" tiếng Anh là gì?","Từ bạn tìm kiếm: absolutely\\n\\nTrình độ: B1\\nTuyệt đối.","B1"\n')
            # Exact duplicate of Direction 1 (must be skipped)
            f.write('"absolutely","absolutely nghĩa là gì?","Từ bạn tìm kiếm: absolutely\\n\\nTrình độ: B1\\nTuyệt đối.","B1"\n')

        report = self.manager.ingest_batch([f_csv], batch_size=8)
        self.assertEqual(report.total_files, 1)
        self.assertEqual(report.success_count, 1)
        self.assertEqual(report.total_records_added, 2, "Both En->Vi and Vi->En must be added!")
        self.assertEqual(report.total_duplicates_skipped, 1, "Exact duplicate question must be skipped!")

        saved = self.loader.load_from_jsonl()
        self.assertEqual(len(saved), 2)
        questions = {r.question for r in saved}
        self.assertIn("absolutely nghĩa là gì?", questions)
        self.assertIn('Từ "Tuyệt đối, hoàn toàn" tiếng Anh là gì?', questions)


if __name__ == "__main__":
    unittest.main()
