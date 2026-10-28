"""Unit test for modern vocabulary web backend (vocab_backend)."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text
from vocab_backend.notebook_db import (
    init_notebook_db,
    save_word,
    get_word,
    delete_word,
    update_word_status,
    list_saved_words,
    get_learning_stats,
)


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


def test_notebook_db():
    init_notebook_db()
    test_user = "test_user_unit"
    delete_word("comprehensive", user_id=test_user)
    
    # Save word
    saved = save_word(
        word="comprehensive",
        level="B2",
        ipa="/ˌkɒmprɪˈhensɪv/",
        part_of_speech="Tính từ",
        meaning="Toàn diện, bao hàm",
        example="This is a comprehensive study.",
        user_id=test_user,
    )
    assert saved["word"] == "comprehensive"
    assert saved["level"] == "B2"
    assert saved["status"] == "learning"

    # Get word
    w = get_word("comprehensive", user_id=test_user)
    assert w is not None
    assert w["meaning"] == "Toàn diện, bao hàm"

    # Update status to mastered
    up = update_word_status("comprehensive", "mastered", user_id=test_user, increment_review=True)
    assert up["status"] == "mastered"
    assert up["review_count"] == 1

    # Stats
    stats = get_learning_stats(user_id=test_user)
    assert stats["total_saved"] >= 1
    assert stats["mastered"] >= 1
    assert stats["by_level"]["B2"] >= 1

    # Cleanup
    delete_word("comprehensive", user_id=test_user)
    assert get_word("comprehensive", user_id=test_user) is None


if __name__ == "__main__":
    print("Running test_required_search_prefix...")
    test_required_search_prefix()
    print("Passed: test_required_search_prefix")

    print("Running test_parse_vocabulary_text...")
    test_parse_vocabulary_text()
    print("Passed: test_parse_vocabulary_text")

    print("Running test_notebook_db...")
    test_notebook_db()
    print("Passed: test_notebook_db")

    print("ALL TESTS PASSED SUCCESSFULLY!")
