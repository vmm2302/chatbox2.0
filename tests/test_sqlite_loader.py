"""Bộ kiểm thử toàn diện cho Bộ Nạp Cơ Sở Dữ Liệu SQLite (.db, .sqlite) của Chatbox 2.0.

Bao gồm 13 kịch bản kiểm định theo yêu cầu:
1. SQLite hợp lệ có một bảng.
2. SQLite có nhiều bảng và nhiều kiểu dữ liệu.
3. SQLite có bảng từ vựng liên quan qua khóa ngoại (Relational Join không Cartesian duplicate).
4. SQLite có dữ liệu hỏi–đáp (Q&A mode).
5. Database không phải SQLite nhưng mang phần mở rộng .db (Reject invalid magic header).
6. Database bị hỏng hoặc không thể mở (Corrupt integrity check).
7. Bảng không có cột phù hợp với schema chuẩn hóa (Raise DataLoadError).
8. Dữ liệu có NULL và kiểu dữ liệu không mong đợi (Safe conversion & skip metrics).
9. Database có nhiều bản ghi và cần đọc theo batch (fetch_batch_size & max_records limit).
10. Nạp lại cùng tệp và xác minh không tạo bản sao vật lý (SHA-256 deduplication).
11. ADD và REPLACE có lỗi, xác minh dữ liệu cũ được bảo toàn theo chính sách Rollback.
12. Dữ liệu đã nạp có thể được truy xuất và sử dụng khi tra cứu (BM25 / Retrieval test).
13. Tên nguồn đúng trong Active Sources sau khi khởi động lại ứng dụng (Persistence test).
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from config.settings import settings
from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.batch_ingestion import (
    BatchIngestionManager,
    BatchStatus,
    FileStatus,
)
from src.data.loader import QALoader
from src.data.loaders.router import FileLoaderRouter
from src.data.loaders.sqlite_loader import (
    SQLiteLoader,
    SQLiteMappingConfig,
    SQLiteMappingMode,
)
from src.retriever.bm25_retriever import BM25Retriever


class TestSQLiteLoaderComprehensive(unittest.TestCase):
    """Kiểm định 13 kịch bản toàn diện cho bộ nạp SQLite."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_sqlite_loader_"))
        self.raw_dir = self.temp_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.temp_dir / "qa_records.jsonl"
        self.manifest_path = self.temp_dir / "sources_manifest.json"

        self.loader = QALoader()
        self.loader.processed_jsonl_path = self.jsonl_path
        self.router = FileLoaderRouter()
        self.manager = BatchIngestionManager(
            router=self.router,
            loader=self.loader,
            manifest_path=self.manifest_path
        )
        self.sqlite_loader = SQLiteLoader(fetch_batch_size=100, max_records_limit=5000)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. SQLite hợp lệ có một bảng
    # --------------------------------------------------------------------------
    def test_1_valid_single_table_sqlite(self):
        """1. Kiểm tra SQLite hợp lệ có một bảng đơn giản."""
        db_path = self.temp_dir / "single_vocab.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE vocab (id INTEGER PRIMARY KEY, word TEXT, definition TEXT, level TEXT);")
        conn.execute("INSERT INTO vocab VALUES (1, 'apple', 'Quả táo', 'A1');")
        conn.execute("INSERT INTO vocab VALUES (2, 'banana', 'Quả chuối', 'A1');")
        conn.commit()
        conn.close()

        val = self.sqlite_loader.validate(db_path)
        self.assertTrue(val.is_valid, f"Validate thất bại: {val.error_message}")
        self.assertEqual(val.metadata.get("table_count"), 1)

        schema = self.sqlite_loader.inspect_schema(db_path)
        self.assertTrue(schema.is_valid)
        self.assertIn("vocab", schema.tables)
        self.assertEqual(schema.tables["vocab"].row_count, 2)

        records = self.sqlite_loader.load(db_path)
        self.assertEqual(len(records), 2)
        words = [r.word for r in records]
        self.assertIn("apple", words)
        self.assertIn("banana", words)
        self.assertIn("Quả táo", records[0].answer)
        self.assertEqual(records[0].source, "single_vocab.db")
        self.assertEqual(records[0].sheet, "vocab")

    # --------------------------------------------------------------------------
    # 2. SQLite có nhiều bảng và nhiều kiểu dữ liệu
    # --------------------------------------------------------------------------
    def test_2_multi_table_and_data_types(self):
        """2. Kiểm tra SQLite có nhiều bảng và các kiểu dữ liệu khác nhau (TEXT, REAL, INT, BLOB)."""
        db_path = self.temp_dir / "complex_types.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE terms (
                id INTEGER PRIMARY KEY,
                word TEXT,
                definition TEXT,
                score REAL,
                count NUMERIC,
                raw_bytes BLOB
            );
        """)
        conn.execute("CREATE TABLE categories (cat_id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("CREATE TABLE audit_logs (log_id INTEGER PRIMARY KEY, event TEXT);")

        conn.execute(
            "INSERT INTO terms VALUES (1, 'matrix', 'Ma trận số học', 4.85, 100, ?);",
            (b"\x01\x02\x03\x04",)
        )
        conn.execute("INSERT INTO categories VALUES (1, 'Toán học');")
        conn.commit()
        conn.close()

        schema = self.sqlite_loader.inspect_schema(db_path)
        self.assertTrue(schema.is_valid)
        self.assertEqual(len(schema.tables), 3)
        self.assertIn("terms", schema.tables)
        self.assertIn("categories", schema.tables)
        self.assertIn("audit_logs", schema.tables)

        # Kiểm tra kiểu dữ liệu các cột
        col_types = {c.name: c.data_type for c in schema.tables["terms"].columns}
        self.assertEqual(col_types["score"], "REAL")
        self.assertEqual(col_types["raw_bytes"], "BLOB")

        # Nạp dữ liệu với cấu hình ánh xạ
        cfg = SQLiteMappingConfig(
            mode=SQLiteMappingMode.VOCAB,
            primary_table="terms",
            word_col="word",
            definition_col="definition",
        )
        records = self.sqlite_loader.load(db_path, mapping_config=cfg)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].word, "matrix")
        self.assertIn("Ma trận số học", records[0].answer)

    # --------------------------------------------------------------------------
    # 3. SQLite có bảng từ vựng liên quan qua khóa ngoại
    # --------------------------------------------------------------------------
    def test_3_vocab_tables_with_foreign_keys(self):
        """3. Kiểm tra SQLite có bảng từ vựng và bảng định nghĩa liên kết qua khóa ngoại."""
        db_path = self.temp_dir / "relational_dict.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE words (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                ipa TEXT,
                level TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE definitions (
                id INTEGER PRIMARY KEY,
                word_id INTEGER NOT NULL,
                pos TEXT,
                definition TEXT NOT NULL,
                example TEXT,
                FOREIGN KEY (word_id) REFERENCES words(id)
            );
        """)

        # Từ 'abandon' có 2 định nghĩa (động từ và danh từ)
        conn.execute("INSERT INTO words VALUES (10, 'abandon', '/əˈbændən/', 'B2');")
        conn.execute("INSERT INTO definitions VALUES (101, 10, 'Động từ', 'Từ bỏ hoặc rời bỏ một nơi', 'They abandoned the car.');")
        conn.execute("INSERT INTO definitions VALUES (102, 10, 'Danh từ', 'Sự buông thả không kiềm chế', 'He danced with abandon.');")
        conn.commit()
        conn.close()

        schema = self.sqlite_loader.inspect_schema(db_path)
        defs_fks = schema.tables["definitions"].foreign_keys
        self.assertEqual(len(defs_fks), 1)
        self.assertEqual(defs_fks[0].table, "words")
        self.assertEqual(defs_fks[0].from_col, "word_id")

        cfg = SQLiteMappingConfig(
            mode=SQLiteMappingMode.RELATIONAL,
            primary_table="words",
            related_table="definitions",
            foreign_key_child_col="word_id",
            foreign_key_parent_col="id",
            word_col="word",
            definition_col="definition",
            pos_col="pos",
            example_col="example",
            ipa_col="ipa",
            level_col="level",
        )
        records = self.sqlite_loader.load(db_path, mapping_config=cfg)

        # Đảm bảo KHÔNG nhân bản: gom nhóm thành 1 bản ghi duy nhất cho từ 'abandon'
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.word, "abandon")
        self.assertEqual(rec.level, "B2")
        self.assertIn("/əˈbændən/", rec.answer)
        self.assertIn("Từ bỏ hoặc rời bỏ một nơi", rec.answer)
        self.assertIn("Sự buông thả không kiềm chế", rec.answer)
        self.assertIn("They abandoned the car.", rec.answer)

    # --------------------------------------------------------------------------
    # 4. SQLite có dữ liệu hỏi–đáp
    # --------------------------------------------------------------------------
    def test_4_qa_data_sqlite(self):
        """4. Kiểm tra nạp database dạng Hỏi - Đáp (Q&A mode)."""
        db_path = self.temp_dir / "qa_faq.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE faq (
                qa_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                topic TEXT,
                level TEXT
            );
        """)
        conn.execute("""
            INSERT INTO faq VALUES (
                'FAQ_001',
                'Chatbox 2.0 sử dụng mô hình nào?',
                'Hệ thống sử dụng PhoBERT, BGE-M3 và Qwen2.5:7B chạy offline qua Ollama.',
                'Architecture',
                'B1'
            );
        """)
        conn.commit()
        conn.close()

        # Kiểm tra tự động nhận diện Q&A mode
        schema = self.sqlite_loader.inspect_schema(db_path)
        auto_cfg = self.sqlite_loader.auto_detect_mapping(schema)
        self.assertIsNotNone(auto_cfg)
        self.assertEqual(auto_cfg.mode, SQLiteMappingMode.QA)

        records = self.sqlite_loader.load(db_path)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.question, "Chatbox 2.0 sử dụng mô hình nào?")
        self.assertIn("PhoBERT", rec.answer)
        self.assertEqual(rec.record_id, "FAQ_001")
        self.assertEqual(rec.level, "B1")

    # --------------------------------------------------------------------------
    # 5. Database không phải SQLite nhưng mang phần mở rộng .db
    # --------------------------------------------------------------------------
    def test_5_fake_sqlite_db_rejected(self):
        """5. Tệp không phải SQLite nhưng có phần mở rộng .db phải bị từ chối rõ ràng."""
        fake_db = self.temp_dir / "corrupted_text.db"
        with open(fake_db, "w", encoding="utf-8") as f:
            f.write("Đây là một tệp văn bản bình thường đổi tên thành .db!")

        val = self.sqlite_loader.validate(fake_db)
        self.assertFalse(val.is_valid)
        self.assertIn("Header magic bytes không khớp", val.error_message)

        with self.assertRaises(DataLoadError) as ctx:
            self.sqlite_loader.load(fake_db)
        self.assertIn("không phải là cơ sở dữ liệu SQLite hợp lệ", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 6. Database bị hỏng hoặc không thể mở
    # --------------------------------------------------------------------------
    def test_6_corrupted_sqlite_rejected(self):
        """6. Tệp có header SQLite nhưng nội dung bị hỏng phải bị phát hiện qua quick_check."""
        corrupt_db = self.temp_dir / "truncated.sqlite"
        # Ghi header chuẩn nhưng cắt cụt không có page database hợp lệ
        with open(corrupt_db, "wb") as f:
            f.write(b"SQLite format 3\x00" + b"\x00" * 40)

        val = self.sqlite_loader.validate(corrupt_db)
        self.assertFalse(val.is_valid)
        self.assertIn("Không thể mở cơ sở dữ liệu SQLite", val.error_message)

    # --------------------------------------------------------------------------
    # 7. Bảng không có cột phù hợp với schema chuẩn hóa
    # --------------------------------------------------------------------------
    def test_7_table_without_matching_columns(self):
        """7. Bảng không có cột phù hợp phải báo lỗi và không tự ý nạp dữ liệu sai."""
        db_path = self.temp_dir / "non_standard.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sensors (sensor_id INT, temperature REAL, timestamp TEXT);")
        conn.execute("INSERT INTO sensors VALUES (1, 28.5, '2026-10-17');")
        conn.commit()
        conn.close()

        schema = self.sqlite_loader.inspect_schema(db_path)
        auto_cfg = self.sqlite_loader.auto_detect_mapping(schema)
        # Không tự động nạp khi schema không phải từ vựng hay Q&A
        self.assertIsNone(auto_cfg)

        with self.assertRaises(DataLoadError) as ctx:
            self.sqlite_loader.load(db_path)
        self.assertIn("Không thể tự động nhận diện cấu trúc", str(ctx.exception))

        # Nếu cấu hình sai tên cột cũng phải báo lỗi cụ thể
        bad_cfg = SQLiteMappingConfig(
            mode=SQLiteMappingMode.QA,
            primary_table="sensors",
            question_col="non_existing_col",
            answer_col="temperature",
        )
        with self.assertRaises(DataLoadError) as ctx:
            self.sqlite_loader.load(db_path, mapping_config=bad_cfg)
        self.assertIn("không tồn tại trong bảng", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 8. Dữ liệu có NULL và kiểu dữ liệu không mong đợi
    # --------------------------------------------------------------------------
    def test_8_null_and_unexpected_types_handling(self):
        """8. Xử lý dữ liệu có NULL, số thực, số nguyên, bỏ qua dòng rỗng và thống kê chi tiết."""
        db_path = self.temp_dir / "null_data.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_data (id INT, q TEXT, a TEXT);")
        # Row 1: Hợp lệ
        conn.execute("INSERT INTO test_data VALUES (1, 'Câu hỏi 1', 'Trả lời 1');")
        # Row 2: Câu hỏi NULL
        conn.execute("INSERT INTO test_data VALUES (2, NULL, 'Trả lời 2');")
        # Row 3: Câu trả lời NULL
        conn.execute("INSERT INTO test_data VALUES (3, 'Câu hỏi 3', NULL);")
        # Row 4: Câu hỏi và trả lời dạng số (INTEGER / REAL) -> Phải chuyển thành chuỗi an toàn
        conn.execute("INSERT INTO test_data VALUES (4, '12345', '67890');")
        # Row 5: Chuỗi rỗng
        conn.execute("INSERT INTO test_data VALUES (5, '   ', 'Trả lời 5');")
        conn.commit()
        conn.close()

        cfg = SQLiteMappingConfig(
            mode=SQLiteMappingMode.QA,
            primary_table="test_data",
            question_col="q",
            answer_col="a",
            id_col="id"
        )
        records = self.sqlite_loader.load(db_path, mapping_config=cfg)

        # Chỉ có Row 1 và Row 4 là hợp lệ (2 dòng)
        self.assertEqual(len(records), 2)
        stats = self.sqlite_loader.last_stats
        self.assertIsNotNone(stats)
        self.assertEqual(stats.total_rows_read, 5)
        self.assertEqual(stats.valid_records, 2)
        self.assertEqual(stats.skipped_records, 3)
        self.assertGreaterEqual(stats.skip_reasons.get("Trường câu hỏi hoặc câu trả lời bị rỗng/NULL", 0), 3)

    # --------------------------------------------------------------------------
    # 9. Database có nhiều bản ghi và cần đọc theo batch
    # --------------------------------------------------------------------------
    def test_9_large_database_batch_reading(self):
        """9. Đọc database lớn theo batch và tuân thủ giới hạn max_records."""
        db_path = self.temp_dir / "large_vocab.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE vocab (id INTEGER PRIMARY KEY, word TEXT, definition TEXT);")

        bulk_data = [(i, f"word_{i}", f"Định nghĩa cho từ {i}") for i in range(1, 351)]
        conn.executemany("INSERT INTO vocab VALUES (?, ?, ?);", bulk_data)
        conn.commit()
        conn.close()

        # Giới hạn batch size 50 và max_records 200
        custom_loader = SQLiteLoader(fetch_batch_size=50, max_records_limit=200)
        cfg = SQLiteMappingConfig(
            mode=SQLiteMappingMode.VOCAB,
            primary_table="vocab",
            word_col="word",
            definition_col="definition",
            max_records=200
        )
        records = custom_loader.load(db_path, mapping_config=cfg)
        self.assertEqual(len(records), 200)
        self.assertEqual(records[0].word, "word_1")
        self.assertEqual(records[-1].word, "word_200")

    # --------------------------------------------------------------------------
    # 10. Nạp lại cùng tệp và xác minh không tạo bản sao vật lý
    # --------------------------------------------------------------------------
    def test_10_duplicate_sqlite_file_deduplication(self):
        """10. Nạp tệp SQLite trùng nội dung phải bị bỏ qua và dọn dẹp bản sao dư thừa an toàn."""
        db_path = self.raw_dir / "source_vocab.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE vocab (id INT, word TEXT, definition TEXT);")
        conn.execute("INSERT INTO vocab VALUES (1, 'candid', 'Thẳng thắn, bộc trực');")
        conn.commit()
        conn.close()

        # Lần nạp 1: Thành công
        with patch.object(self.manager, "_cleanup_batch_duplicate_files") as mock_clean:
            mock_clean.side_effect = lambda res, hashes, mf: None
            with patch("src.retriever.bge_chroma.BGEChromaRetriever.build_or_load_collection"), \
                 patch("src.retriever.bge_chroma.BGEChromaRetriever.upsert_records"), \
                 patch("src.retriever.bge_chroma.BGEChromaRetriever.get_collection_count", return_value=1):
                rep1 = self.manager.ingest_batch([db_path], mode="add")
                self.assertEqual(rep1.success_count, 1)

        # Lần nạp 2: Tệp trùng nội dung với tên tạm thời 'tmp_abcdef12_source_vocab.db'
        dup_copy_path = self.raw_dir / "tmp_abcdef12_source_vocab.db"
        shutil.copy2(db_path, dup_copy_path)
        self.assertTrue(dup_copy_path.exists())

        rep2 = self.manager.ingest_batch([dup_copy_path], mode="add")
        self.assertEqual(rep2.skipped_count, 1)
        self.assertIn("Duplicate file", rep2.file_results[0].reason)

        # Bản sao dư thừa phải được dọn dẹp an toàn, bản gốc được bảo toàn
        self.assertFalse(dup_copy_path.exists(), "Bản sao tạm dư thừa phải bị xóa")
        self.assertTrue(db_path.exists(), "Tệp gốc canonical phải được bảo toàn")

    # --------------------------------------------------------------------------
    # 11. ADD và REPLACE có lỗi, xác minh dữ liệu cũ được bảo toàn theo chính sách Rollback
    # --------------------------------------------------------------------------
    def test_11_rollback_preserves_data_on_sqlite_error(self):
        """11. Khi xảy ra sự cố trong quá trình nạp SQLite, dữ liệu cũ phải được phục hồi nguyên vẹn."""
        # Tạo dữ liệu ban đầu
        initial_records = [
            QARecord(record_id="REC_OLD1", word="cat", question="Nghĩa của từ cat là gì?", answer="Con mèo", source="old.xlsx")
        ]
        self.loader.save_to_jsonl(initial_records)
        self.manager.save_manifest({
            "sources": {
                "SRC_OLD1": {"source_id": "SRC_OLD1", "file_name": "old.xlsx", "source_name": "old.xlsx", "status": "ACTIVE", "record_count": 1}
            }
        })

        # Tạo tệp SQLite mới để nạp
        new_db = self.temp_dir / "new_vocab.db"
        conn = sqlite3.connect(new_db)
        conn.execute("CREATE TABLE vocab (id INT, word TEXT, definition TEXT);")
        conn.execute("INSERT INTO vocab VALUES (1, 'dog', 'Con chó');")
        conn.commit()
        conn.close()

        # Giả lập lỗi ở bước lập chỉ mục vector (Chroma error)
        with patch("src.data.batch_ingestion.BGEChromaRetriever.upsert_records", side_effect=RuntimeError("Mô phỏng lỗi ChromaDB")), \
             patch("src.retriever.bge_chroma.BGEChromaRetriever.upsert_records", side_effect=RuntimeError("Mô phỏng lỗi ChromaDB")):
            rep = self.manager.ingest_batch([new_db], mode="add")
            self.assertEqual(rep.batch_status, BatchStatus.FAILED)

        # Kiểm tra Rollback: JSONL và Manifest phải giữ nguyên dữ liệu cũ
        current_records = self.loader.load_from_jsonl()
        self.assertEqual(len(current_records), 1)
        self.assertEqual(current_records[0].word, "cat")

        manifest = self.manager.load_manifest()
        self.assertIn("SRC_OLD1", manifest["sources"])
        from src.data.loaders.base import compute_file_hash
        self.assertNotIn(f"SRC_{compute_file_hash(new_db)[:12]}", manifest["sources"])

    # --------------------------------------------------------------------------
    # 12. Dữ liệu đã nạp có thể được truy xuất và sử dụng khi trả lời câu hỏi
    # --------------------------------------------------------------------------
    def test_12_ingested_sqlite_retrieval(self):
        """12. Dữ liệu nạp từ SQLite được lập chỉ mục BM25 và có thể truy xuất chính xác."""
        db_path = self.temp_dir / "retrieval_vocab.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE vocab (word TEXT, definition TEXT, level TEXT);")
        conn.execute("INSERT INTO vocab VALUES ('serendipity', 'Sự tình cờ phát hiện ra điều may mắn', 'C1');")
        conn.execute("INSERT INTO vocab VALUES ('ephemeral', 'Tồn tại trong thời gian rất ngắn', 'C2');")
        conn.execute("INSERT INTO vocab VALUES ('resilient', 'Kiên cường bền bỉ', 'B2');")
        conn.execute("INSERT INTO vocab VALUES ('ubiquitous', 'Có mặt ở khắp mọi nơi phổ biến', 'C1');")
        conn.execute("INSERT INTO vocab VALUES ('pragmatic', 'Thực dụng thực tế', 'C1');")
        conn.commit()
        conn.close()

        records = self.sqlite_loader.load(db_path)
        self.assertEqual(len(records), 5)

        # Khởi tạo bộ tìm kiếm BM25 trên các bản ghi SQLite này
        retriever = BM25Retriever(records)
        results = retriever.search("serendipity là gì", top_k=1)
        self.assertGreater(len(results), 0)
        top_rec = results[0][0]
        self.assertEqual(top_rec.word, "serendipity")
        self.assertIn("Sự tình cờ phát hiện", top_rec.answer)
        self.assertEqual(top_rec.source, "retrieval_vocab.db")

    # --------------------------------------------------------------------------
    # 13. Tên nguồn đúng trong Active Sources sau khi khởi động lại ứng dụng
    # --------------------------------------------------------------------------
    def test_13_active_sources_after_restart(self):
        """13. Active Sources hiển thị chính xác tên tệp gốc SQLite và số bản ghi sau khi khởi động lại."""
        db_path = self.raw_dir / "Oxford_Advanced_Learner.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE vocab (id INT, word TEXT, definition TEXT);")
        conn.execute("INSERT INTO vocab VALUES (1, 'resilient', 'Kiên cường, có khả năng phục hồi');")
        conn.commit()
        conn.close()

        # Nạp tệp với mock ChromaDB
        with patch("src.retriever.bge_chroma.BGEChromaRetriever.build_or_load_collection"), \
             patch("src.retriever.bge_chroma.BGEChromaRetriever.upsert_records"), \
             patch("src.retriever.bge_chroma.BGEChromaRetriever.get_collection_count", return_value=1):
            rep = self.manager.ingest_batch([db_path], mode="add")
            self.assertEqual(rep.success_count, 1)

        # Giả lập khởi động lại ứng dụng bằng cách tạo mới BatchIngestionManager đọc manifest trên đĩa
        restarted_manager = BatchIngestionManager(
            router=FileLoaderRouter(),
            loader=self.loader,
            manifest_path=self.manifest_path
        )
        active_srcs = restarted_manager.get_active_sources()
        self.assertEqual(len(active_srcs), 1)
        src = active_srcs[0]

        # Kiểm tra metadata chuẩn xác: không UUID, không N/A, đúng định dạng tệp gốc
        self.assertEqual(src.get("source_name"), "Oxford_Advanced_Learner.sqlite")
        self.assertEqual(src.get("file_name"), "Oxford_Advanced_Learner.sqlite")
        self.assertEqual(src.get("file_type"), "sqlite")
        self.assertEqual(src.get("record_count"), 1)
        self.assertEqual(src.get("status"), "ACTIVE")
        self.assertTrue(len(src.get("file_hash", "")) == 64)


if __name__ == "__main__":
    unittest.main()
