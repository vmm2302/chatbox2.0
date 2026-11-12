"""End-to-End integration test for the Vocabulary Web Application (Backend & API)."""

import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.api_server import app
from vocab_backend.dependencies import auth_service

client = TestClient(app)


def _create_and_login_test_user():
    uname = f"e2e_user_{int(time.time() * 1000)}"
    existing = auth_service.user_repo.get_by_username(uname)
    if existing:
        auth_service.user_repo.delete_user(existing.id)

    reg = client.post(
        "/api/auth/register",
        json={
            "username": uname,
            "password": "E2ePassword123!",
            "confirm_password": "E2ePassword123!",
            "display_name": "E2E Tester",
        },
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user"]["id"]

    login = client.post(
        "/api/auth/login",
        json={"username": uname, "password": "E2ePassword123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["total_records"] > 0
    print(f"Health test passed. Total records: {data['total_records']}")


def test_unauthenticated_endpoints_blocked():
    assert client.post("/api/chat", json={"query": "amazing"}).status_code == 401
    assert client.get("/api/words/search?q=ab").status_code == 401
    assert client.get("/api/words/detail/amazing").status_code == 401
    assert client.get("/api/words/levels").status_code == 401
    assert client.get("/api/words/discover").status_code == 401


def test_chat_mandatory_prefix_and_no_suggestions(auth_headers):
    res = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"query": "amazing nghĩa là gì?", "level": "Tất cả"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    assert "Từ bạn tìm kiếm: amazing" in reply[:60], f"Prefix missing in reply: {reply[:60]}"

    card = data["structured_card"]
    assert card is not None
    assert card["word"] == "amazing"
    assert card["level"] in ("A1", "A2")
    assert "suggestions" not in data, "suggestions field must be removed from API response"
    print("Chat mandatory prefix and no suggestions test passed!")


def test_search_autocomplete_a1_a2_only(auth_headers):
    res = client.get("/api/words/search?q=ab&limit=5", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) > 0
    words = [r["word"] for r in data["results"]]
    levels = [r.get("level") for r in data["results"]]
    assert any(w.startswith("ab") for w in words)
    for lvl in levels:
        assert lvl in ("A1", "A2"), f"Search autocomplete returned non-A1/A2 level: {lvl}"
    print("Search autocomplete test passed!")


def test_out_of_scope_levels(auth_headers):
    res = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"query": "Các từ vựng B2 thường gặp trong IELTS", "level": "Tất cả"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    assert "ngoài phạm vi" in reply.lower() or "a1" in reply.lower()

    a1_res = client.get("/api/words/detail/amazing", headers=auth_headers)
    assert a1_res.status_code == 200
    assert a1_res.json()["level"] in ("A1", "A2")

    word_res = client.get("/api/words/detail/mitigate", headers=auth_headers)
    assert word_res.status_code == 404
    print("Out-of-scope levels test passed!")


def test_serve_frontend_spa():
    res = client.get("/")
    assert res.status_code == 200
    assert "Chatbot cho từ vựng A1 - A2" in res.text or "html" in res.text
    print("Serve frontend SPA test passed!")


if __name__ == "__main__":
    test_health()
    test_unauthenticated_endpoints_blocked()
    uid, headers = _create_and_login_test_user()
    try:
        test_chat_mandatory_prefix_and_no_suggestions(headers)
        test_search_autocomplete_a1_a2_only(headers)
        test_out_of_scope_levels(headers)
    finally:
        auth_service.user_repo.delete_user(uid)
    test_serve_frontend_spa()
    print("ALL E2E INTEGRATION TESTS PASSED!")
