"""Bộ kiểm thử xác thực Format câu trả lời từ vựng tiếng Anh (Vocabulary Response Formatting).

Kiểm tra:
1. Kiểm thử đơn vị hàm format_vocabulary_response:
   - Tách từ loại thành header riêng (### Part of Speech)
   - Tách từng meaning thành dòng riêng (**index. Meaning**)
   - Đặt example ở dòng NGAY BÊN DƯỚI meaning (• Example)
   - Giữ dòng trống giữa các meaning
   - Xử lý và tách triệt để các trường hợp bị gộp dòng (Meaning • Example)
   - Hỗ trợ nhiều example dưới cùng một meaning
   - Bảo toàn văn bản không phải từ vựng (Small Talk, Out of Scope)
2. Kiểm thử tích hợp 6 câu hỏi bắt buộc cho từ 'about':
   1. about trong tiếng Việt có nghĩa là gì?
   2. about trong Tiếng Việt có nghĩa là gì?
   3. ABOUT trong TIẾNG VIỆT có nghĩa là gì?
   4. about nghĩa là gì?
   5. nghĩa của about?
   6. What does about mean in Vietnamese?
3. Kiểm thử từ vựng phức tạp khác (ví dụ: 'address', 'above') có nhiều từ loại, nhiều nghĩa, nhiều ví dụ.
"""

import os
import sys
import unittest
from pathlib import Path

# Đảm bảo môi trường offline
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chat.engine import ChatEngine
from src.chat.response_formatter import format_vocabulary_response
from src.data.loader import QALoader


class TestResponseFormatterUnits(unittest.TestCase):
    """Kiểm thử đơn vị cho hàm format_vocabulary_response."""

    def test_raw_vocabulary_formatting(self):
        raw = (
            "Trình độ: A1\n\n"
            "Phát âm: /əˈbaʊt/\n\n"
            "Giới từ (Preposition):\n\n"
            "Về\n"
            "   • Do you know much about this old city?\n\n"
            "Quanh quất, quanh quẩn đây đó, rải rác\n"
            "   • She walked about the garden for an hour.\n"
        )
        res = format_vocabulary_response(raw)

        # 1. Kiểm tra header Trình độ & Phát âm
        self.assertIn("**Trình độ:** A1", res)
        self.assertIn("**Phát âm:** /əˈbaʊt/", res)

        # 2. Kiểm tra Header từ loại
        self.assertIn("### Giới từ (Preposition)", res)

        # 3. Kiểm tra meanings được đánh số và in đậm
        self.assertIn("**1. Về**", res)
        self.assertIn("**2. Quanh quất, quanh quẩn đây đó, rải rác**", res)

        # 4. Kiểm tra example nằm ngay bên dưới meaning
        self.assertIn("• Do you know much about this old city?", res)
        self.assertIn("• She walked about the garden for an hour.", res)

        # 5. Đảm bảo meaning và example không bị gộp cùng 1 dòng
        lines = [line.strip() for line in res.split("\n") if line.strip()]
        for line in lines:
            if line.startswith("**1. Về**"):
                self.assertNotIn("Do you know much", line)
            if "Do you know much" in line:
                self.assertTrue(line.startswith("•"))

    def test_split_merged_meaning_example_line(self):
        """Kiểm tra xử lý lỗi khi dữ liệu bị gộp thành 'Meaning • Example' trên cùng 1 dòng."""
        merged_raw = (
            "Trình độ: A1\n"
            "Phát âm: /test/\n"
            "Danh từ (Noun):\n"
            "Bài kiểm tra • We have a test tomorrow.\n"
            "Sự thử thách • Life is a test."
        )
        res = format_vocabulary_response(merged_raw)

        # Kiểm tra đã tách thành các dòng riêng biệt
        self.assertIn("**1. Bài kiểm tra**", res)
        self.assertIn("• We have a test tomorrow.", res)
        self.assertIn("**2. Sự thử thách**", res)
        self.assertIn("• Life is a test.", res)

        # Không được chứa 'Bài kiểm tra • We have' trên cùng 1 dòng
        lines = [l.strip() for l in res.split("\n")]
        self.assertFalse(any("Bài kiểm tra •" in l for l in lines))

    def test_multiple_examples_per_meaning(self):
        """Kiểm tra một meaning có nhiều example thì mỗi example xuống dòng riêng."""
        raw = (
            "Trình độ: A2\n"
            "Phát âm: /ˈpræk.tɪs/\n"
            "Danh từ (Noun):\n"
            "Thực hành, rèn luyện\n"
            "   • Practice makes perfect.\n"
            "   • It takes a lot of practice to play the violin well."
        )
        res = format_vocabulary_response(raw)

        self.assertIn("**1. Thực hành, rèn luyện**", res)
        self.assertIn("• Practice makes perfect.", res)
        self.assertIn("• It takes a lot of practice to play the violin well.", res)

        lines = [l.strip() for l in res.split("\n") if l.strip()]
        ex_lines = [l for l in lines if l.startswith("•")]
        self.assertEqual(len(ex_lines), 2)

    def test_non_vocabulary_text_preserved(self):
        """Kiểm tra văn bản thông thường không bị biến đổi sai lệch."""
        plain = "Xin chào! Tôi là chatbot hỗ trợ bạn học và tra cứu từ vựng tiếng Anh."
        self.assertEqual(format_vocabulary_response(plain), plain)

        oos = "Hiện tại cơ sở tri thức chưa có dữ liệu phù hợp để trả lời câu hỏi này."
        self.assertEqual(format_vocabulary_response(oos), oos)


class TestChatEngineVocabularyFormatting(unittest.TestCase):
    """Kiểm thử tích hợp ChatEngine với 6 câu hỏi bắt buộc cho 'about' và từ vựng phức tạp."""

    @classmethod
    def setUpClass(cls):
        loader = QALoader()
        cls.records = loader.get_or_create_records()
        cls.engine = ChatEngine(records=cls.records)
        cls.engine.warm_up()

    def setUp(self):
        self.engine.tracker.active_word = None
        self.engine.tracker.history.clear()

    def test_about_six_variations_consistent_formatting(self):
        """Kiểm thử toàn bộ 6 câu hỏi bắt buộc cho từ 'about'."""
        queries = [
            "about trong tiếng Việt có nghĩa là gì?",
            "about trong Tiếng Việt có nghĩa là gì?",
            "ABOUT trong TIẾNG VIỆT có nghĩa là gì?",
            "about nghĩa là gì?",
            "nghĩa của about?",
            "What does about mean in Vietnamese?",
        ]

        expected_elements = [
            "**Trình độ:** A1",
            "**Phát âm:** /əˈbaʊt/",
            "### Giới từ (Preposition)",
            "**1. Về**",
            "• Do you know much about this old city?",
            "### Trạng từ (Adverb)",
            "### Động từ (Verb)",
        ]

        first_answer = None

        for idx, q in enumerate(queries, 1):
            with self.subTest(query=q):
                self.engine.tracker.active_word = None
                self.engine.tracker.history.clear()

                resp = self.engine.ask(q)

                self.assertNotEqual(resp.mode, "NO_MATCH", f"Query '{q}' bị trả về NO_MATCH")
                self.assertEqual(resp.word, "about", f"Query '{q}' không khớp từ 'about'")

                # Kiểm tra tất cả các phần tử cấu trúc bắt buộc có mặt
                for elem in expected_elements:
                    self.assertIn(elem, resp.answer, f"Query '{q}' thiếu phần tử '{elem}' trong câu trả lời")

                # Kiểm tra không có dòng nào gộp 'Meaning • Example'
                lines = [l.strip() for l in resp.answer.split("\n") if l.strip()]
                for l in lines:
                    self.assertFalse(
                        l.startswith("**") and "•" in l,
                        f"Dòng bị gộp meaning và example: '{l}'"
                    )

                # Cả 6 câu hỏi phải trả lời giống hệt nhau
                if first_answer is None:
                    first_answer = resp.answer
                else:
                    self.assertEqual(resp.answer, first_answer, f"Câu trả lời cho '{q}' không đồng nhất với câu 1")

    def test_complex_word_address_formatting(self):
        """Kiểm thử từ vựng phức tạp 'address' có nhiều từ loại, nhiều nghĩa, nhiều ví dụ."""
        resp = self.engine.ask("address trong tiếng Việt có nghĩa là gì?")

        self.assertNotEqual(resp.mode, "NO_MATCH")
        self.assertEqual(resp.word, "address")

        self.assertIn("**Trình độ:** A1", resp.answer)
        self.assertIn("**Phát âm:** /əˈdres/", resp.answer)
        self.assertIn("### Danh từ (Noun)", resp.answer)
        self.assertIn("### Động từ (Verb)", resp.answer)

        # Kiểm tra các nghĩa của Danh từ
        self.assertIn("**1. Địa chỉ**", resp.answer)
        self.assertIn("• Please write your address on the form.", resp.answer)

        # Kiểm tra các nghĩa của Động từ
        self.assertIn("**1. Gửi**", resp.answer)
        self.assertIn("• I will address the package to my sister.", resp.answer)

        # Đảm bảo không dùng bảng Markdown
        self.assertNotIn("|---", resp.answer)
        self.assertNotIn("| --- |", resp.answer)


if __name__ == "__main__":
    unittest.main()
