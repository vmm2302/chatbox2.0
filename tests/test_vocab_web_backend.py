"""Unit test for modern vocabulary web backend (vocab_backend)."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text


def test_required_search_prefix():
    # Test 1: Simple text without prefix
    raw_answer = "Trình độ: A1\nPhát âm: /əˈbaʊt/\nNghĩa: Về..."
    res = ensure_required_search_prefix(raw_answer, "about")
    assert res.startswith("Từ bạn tìm kiếm: about")

    # Test 2: Text that already has older format 'Từ **about**:'
    old_fmt = "Từ **about**:\n\nTrình độ: A1\nPhát âm: /əˈbaʊt/"
    res2 = ensure_required_search_prefix(old_fmt, "about")
    assert res2.startswith("Từ bạn tìm kiếm: about")

    # Test 3: Text that already has the required prefix
    already_fmt = "Từ bạn tìm kiếm: about\n\nTrình độ: A1"
    res3 = ensure_required_search_prefix(already_fmt, "about")
    assert res3 == already_fmt

    # Test 4: Out of scope responses must NOT have prefix
    oos_text = "Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ."
    res4 = ensure_required_search_prefix(oos_text, "sustainable")
    assert not res4.startswith("Từ bạn tìm kiếm:"), "Out of scope text must not have search prefix"
    assert res4 == oos_text


def test_parse_vocabulary_text():
    sample = """Từ bạn tìm kiếm: amazing

Trình độ: A1
Phát âm: /əˈmeɪzɪŋ/

Tính từ (Adjective):
Kinh ngạc, sửng sốt, tuyệt vời, phi thường
   • The view from the top of the mountain was absolutely amazing!
   • She has an amazing ability to learn new languages quickly.
"""
    parsed = parse_vocabulary_text(sample, default_word="amazing")
    assert parsed["word"] == "amazing"
    assert parsed["level"] == "A1"
    assert parsed["ipa"] == "/əˈmeɪzɪŋ/"
    assert parsed["primary_pos"] == "Tính từ (Adjective)"
    assert "Kinh ngạc" in parsed["primary_meaning"]
    assert len(parsed["blocks"]) > 0
    assert len(parsed["blocks"][0]["meanings"][0]["examples"]) == 2

    # Test out-of-scope text should return None instead of creating fake card
    oos = "Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ."
    parsed_oos = parse_vocabulary_text(oos, default_word="sustainable")
    assert parsed_oos is None, "Out-of-scope response must return None for parsed card"


if __name__ == "__main__":
    print("Running test_required_search_prefix...")
    test_required_search_prefix()
    print("Passed: test_required_search_prefix")

    print("Running test_parse_vocabulary_text...")
    test_parse_vocabulary_text()
    print("Passed: test_parse_vocabulary_text")

    print("ALL TESTS PASSED SUCCESSFULLY!")
