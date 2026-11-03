"""End-to-End integration test for the Vocabulary Web Application (Backend & API)."""

import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.api_server import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["total_records"] > 0
    print(f"Health test passed. Total records: {data['total_records']}")


def test_chat_mandatory_prefix_and_no_suggestions():
    # Test query for an A1 word: "amazing nghĩa là gì?"
    res = client.post(
        "/api/chat",
        json={"query": "amazing nghĩa là gì?", "level": "Tất cả"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    print(f"Bot Reply start: {reply[:80]}")

    # Verify the user-mandated requirement:
    # "Từ bạn tìm kiếm: amazing"
    assert "Từ bạn tìm kiếm: amazing" in reply[:60], f"Prefix missing in reply: {reply[:60]}"

    # Verify structured card
    card = data["structured_card"]
    assert card is not None
    assert card["word"] == "amazing"
    assert card["level"] in ("A1", "A2")

    # Verify suggestion chips have been removed from the API response
    assert "suggestions" not in data, "suggestions field must be removed from API response"
    print("Chat mandatory prefix and no suggestions test passed!")


def test_search_autocomplete_a1_a2_only():
    res = client.get("/api/words/search?q=ab&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) > 0
    words = [r["word"] for r in data["results"]]
    levels = [r.get("level") for r in data["results"]]
    print(f"Autocomplete results for 'ab': {words}, levels: {levels}")
    assert any(w.startswith("ab") for w in words)
    for lvl in levels:
        assert lvl in ("A1", "A2"), f"Search autocomplete returned non-A1/A2 level: {lvl}"
    print("Search autocomplete test passed!")


def test_out_of_scope_levels():
    # Test explicit B1/B2 query
    res = client.post(
        "/api/chat",
        json={"query": "Các từ vựng B2 thường gặp trong IELTS", "level": "Tất cả"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    print(f"Out of scope reply: {reply}")
    assert "ngoài phạm vi" in reply.lower() or "a1" in reply.lower(), "B2 queries must be answered with out-of-scope"

    # Test A1 word detail is 200
    a1_res = client.get("/api/words/detail/amazing")
    assert a1_res.status_code == 200, "amazing (A1) must return 200"
    assert a1_res.json()["level"] in ("A1", "A2")

    # Test non-A1/A2 word detail is 404
    word_res = client.get("/api/words/detail/mitigate")
    assert word_res.status_code == 404, "mitigate (B2/C1) must return 404 in A1-A2 dictionary"
    print("Out-of-scope levels test passed!")


def test_serve_frontend_spa():
    # Test that root / returns index.html of built frontend
    res = client.get("/")
    assert res.status_code == 200
    assert "Chatbot cho từ vựng A1 - A2" in res.text or "html" in res.text
    print("Serve frontend SPA test passed!")


if __name__ == "__main__":
    test_health()
    test_chat_mandatory_prefix_and_no_suggestions()
    test_search_autocomplete_a1_a2_only()
    test_out_of_scope_levels()
    test_serve_frontend_spa()
    print("ALL E2E INTEGRATION TESTS PASSED!")
