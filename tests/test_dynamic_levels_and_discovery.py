"""Tests for Dynamic Levels and Multi-Level Discovery.
Verifies:
1. Dynamic level discovery directly from qa_records.jsonl.
2. GET /api/words/levels returns actual levels and correct counts.
3. GET /api/words/discover filters and returns cards for requested level.
4. Dynamic level visual attributes (badge, colors) generated without hardcoding.
"""

import os
import sys
from pathlib import Path

# Enforce offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.api_server import (
    get_available_levels,
    discover_words,
    search_words,
    get_records,
    reload_records,
)
from vocab_backend.vocab_parser import parse_vocabulary_text


def test_get_available_levels():
    print("Testing get_available_levels()...")
    res = get_available_levels()
    assert "levels" in res, "Missing 'levels' in response"
    assert "counts" in res, "Missing 'counts' in response"
    assert isinstance(res["levels"], list)
    assert len(res["levels"]) > 0, "No levels found in database"
    for lvl in res["levels"]:
        assert lvl in res["counts"], f"Missing count for level {lvl}"
        assert res["counts"][lvl] >= 0
    print(f"Passed: get_available_levels() -> levels: {res['levels']}, counts: {res['counts']}")


def test_discover_words_levels():
    print("Testing discover_words()...")
    # 1. Level A1
    res_a1 = discover_words(level="A1", count=4)
    assert res_a1["level"] == "A1"
    assert len(res_a1["words"]) <= 4
    for card in res_a1["words"]:
        assert card["level"] == "A1"
    print(f"Passed: discover_words(A1) -> {len(res_a1['words'])} words")

    # 2. Level A2
    res_a2 = discover_words(level="A2", count=4)
    assert res_a2["level"] == "A2"
    assert len(res_a2["words"]) <= 4
    for card in res_a2["words"]:
        assert card["level"] == "A2"
    print(f"Passed: discover_words(A2) -> {len(res_a2['words'])} words")

    # 3. Arbitrary level that has no records yet (e.g. C2)
    res_c2 = discover_words(level="C2", count=4)
    assert res_c2["level"] == "C2"
    print(f"Passed: discover_words(C2) -> handled gracefully with {len(res_c2['words'])} words")


def test_search_words_multi_level():
    print("Testing search_words() with level filtering...")
    # Search all
    res_all = search_words(q="ab", level="Tất cả", limit=5)
    assert len(res_all["results"]) > 0

    # Search filtered by A1
    res_a1 = search_words(q="ab", level="A1", limit=5)
    for item in res_a1["results"]:
        assert item["level"] == "A1"
    print(f"Passed: search_words() multi-level filtering passed")


def test_dynamic_level_metadata():
    print("Testing dynamic level styling and badge generation...")
    # Known CEFR presets
    card_b1 = parse_vocabulary_text("Trình độ: B1\nPhát âm: /test/\nNghĩa: Thử\n• Example.", default_word="test", default_level="B1")
    assert card_b1["level"] == "B1"
    assert "B1" in card_b1["level_meta"]["badge"]

    card_c1 = parse_vocabulary_text("Trình độ: C1\nPhát âm: /test/\nNghĩa: Cao cấp\n• Example.", default_word="test", default_level="C1")
    assert card_c1["level"] == "C1"
    assert "C1" in card_c1["level_meta"]["badge"]

    # Custom level discovered in data without hardcoding
    card_custom = parse_vocabulary_text("Trình độ: IELTS\nPhát âm: /test/\nNghĩa: Học thuật\n• Example.", default_word="test", default_level="IELTS")
    assert card_custom["level"] == "IELTS"
    assert "IELTS" in card_custom["level_meta"]["badge"]
    print("Passed: dynamic level styling generated successfully without hardcoding")


if __name__ == "__main__":
    test_get_available_levels()
    test_discover_words_levels()
    test_search_words_multi_level()
    test_dynamic_level_metadata()
    print("ALL DYNAMIC LEVELS AND DISCOVERY TESTS PASSED SUCCESSFULLY!")
