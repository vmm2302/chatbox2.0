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


def test_chat_mandatory_prefix():
    # Test query for a word: "amazing nghĩa là gì?"
    res = client.post(
        "/api/chat",
        json={"query": "amazing nghĩa là gì?", "level": "Tất cả"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    print(f"Bot Reply start: {reply[:80]}")
    
    # Verify the user-mandated requirement:
    # "hãy thêm cho tôi ở đầu câu trả lời, tôi muốn là khi mà tôi hỏi từ bất kì thì chatbot sẽ trả lời lại là:
    # Từ bạn tìm kiếm: từ bất kì nào đó tôi hỏi"
    assert "Từ bạn tìm kiếm: amazing" in reply[:60], f"Prefix missing in reply: {reply[:60]}"
    
    # Verify structured card
    card = data["structured_card"]
    assert card is not None
    assert card["word"] == "amazing"
    assert card["level"] == "A1"
    assert "/əˈmeɪzɪŋ/" in card["ipa"]
    assert len(card["blocks"]) > 0
    assert len(data["suggestions"]) > 0
    print("Chat mandatory prefix test passed!")


def test_search_autocomplete():
    res = client.get("/api/words/search?q=ab&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) > 0
    words = [r["word"] for r in data["results"]]
    print(f"Autocomplete results for 'ab': {words}")
    assert any(w.startswith("ab") for w in words)
    print("Search autocomplete test passed!")


def test_notebook_flow():
    # Save word
    save_res = client.post(
        "/api/notebook",
        json={
            "word": "resilient",
            "level": "B2",
            "ipa": "/rɪˈzɪliənt/",
            "part_of_speech": "Tính từ",
            "meaning": "Kiên cường, mau phục hồi",
            "example": "He is resilient in facing difficulties.",
        },
    )
    assert save_res.status_code == 200
    
    # List notebook
    list_res = client.get("/api/notebook")
    assert list_res.status_code == 200
    saved_list = list_res.json()["saved_words"]
    assert any(item["word"] == "resilient" for item in saved_list)

    # Update status to mastered
    patch_res = client.patch(
        "/api/notebook/resilient/status",
        json={"status": "mastered", "increment_review": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["word"]["status"] == "mastered"

    # Stats
    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_saved"] >= 1
    assert stats["mastered"] >= 1

    # Delete
    del_res = client.delete("/api/notebook/resilient")
    assert del_res.status_code == 200
    print("Notebook flow test passed!")


def test_serve_frontend_spa():
    # Test that root / returns index.html of built frontend
    res = client.get("/")
    assert res.status_code == 200
    assert "Vocab" in res.text or "html" in res.text
    print("Serve frontend SPA test passed!")


if __name__ == "__main__":
    test_health()
    test_chat_mandatory_prefix()
    test_search_autocomplete()
    test_notebook_flow()
    test_serve_frontend_spa()
    print("ALL E2E INTEGRATION TESTS PASSED!")
