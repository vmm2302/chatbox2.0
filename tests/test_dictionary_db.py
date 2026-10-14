"""Unit test cho Module DictionaryDBService (tra cứu cơ sở dữ liệu từ điển Anh - Việt)."""

import unittest
from pathlib import Path

from config.settings import settings
from src.data.dictionary_db import DictionaryDBService


class TestDictionaryDBService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = settings.DICTIONARY_DB_PATH
        if not cls.db_path.exists():
            raise unittest.SkipTest(f"Không tìm thấy file DB tại {cls.db_path}")
        cls.service = DictionaryDBService(db_path=cls.db_path)

    @classmethod
    def tearDownClass(cls):
        cls.service.close()

    def test_lookup_common_word(self):
        """Kiểm tra tra cứu từ cơ bản 'about'."""
        res = self.service.lookup("about")
        self.assertIsNotNone(res)
        self.assertEqual(res["word"], "about")
        self.assertTrue(len(res["ipa"]) > 0)
        self.assertIn("D", res["definitions_by_pos"])
        self.assertIn("E", res["definitions_by_pos"])

    def test_lookup_word_with_apostrophe(self):
        """Kiểm tra tra cứu từ có dấu nháy đơn unicode."""
        res = self.service.lookup("o’clock")
        self.assertIsNotNone(res)

    def test_format_answer_structure(self):
        """Kiểm tra cấu trúc câu trả lời sinh ra tuân thủ format chuẩn."""
        res = self.service.lookup("abandon")
        self.assertIsNotNone(res)
        formatted = self.service.format_answer(
            word="abandon",
            level="B2",
            lookup_data=res,
            oxford_pos_tokens=["v."],
        )
        self.assertIn("Trình độ: B2", formatted)
        self.assertIn("Phát âm:", formatted)
        self.assertIn("Động từ (Verb):", formatted)

    def test_pruned_database_size_and_integrity(self):
        """Kiểm tra kích thước tệp sau thu gọn < 10 MB và tính toàn vẹn SQLite."""
        file_size = self.db_path.stat().st_size
        self.assertLess(file_size, 10 * 1024 * 1024, "Dung lượng DB phải nhỏ hơn 10 MB sau khi thu gọn")
        conn = self.service._get_connection()
        integrity = conn.execute("PRAGMA integrity_check;").fetchall()
        self.assertEqual(integrity, [("ok",)], "Database phải vượt qua integrity check")

    def test_lookup_cefr_levels_coverage(self):
        """Kiểm tra các từ vựng tiêu biểu trải dài từ A1 đến B2 vẫn tra cứu đầy đủ."""
        words_to_check = ["apple", "about", "profile", "concentrate", "abandon", "wealthy"]
        for w in words_to_check:
            res = self.service.lookup(w)
            self.assertIsNotNone(res, f"Từ '{w}' phải tồn tại trong cơ sở dữ liệu A1-B2 đã thu gọn")
            self.assertTrue(len(res["ipa"]) > 0, f"Từ '{w}' phải có phiên âm IPA")
            self.assertTrue(len(res["definitions_by_pos"]) > 0, f"Từ '{w}' phải có định nghĩa tiếng Việt")


if __name__ == "__main__":
    unittest.main()
