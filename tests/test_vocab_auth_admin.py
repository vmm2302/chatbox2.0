"""Integration test for Auth Access Tokens, RBAC/IDOR protection, Conversations, Streaming, and Admin routes."""

import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.api_server import app
from vocab_backend.dependencies import auth_service
from src.auth.security import hash_password

client = TestClient(app)


def _create_ephemeral_user(username: str, password: str, role: str = "user"):
    existing = auth_service.user_repo.get_by_username(username)
    if existing:
        if existing.role == "admin":
            auth_service.user_repo.set_role(existing.id, "user")
        auth_service.user_repo.delete_user(existing.id)
    return auth_service.user_repo.create_user(
        username=username,
        password_hash=hash_password(password),
        display_name=username,
        role=role,
        is_active=True,
    )


def _delete_ephemeral_user(user_id: int):
    u = auth_service.user_repo.get_by_id(user_id)
    if not u:
        return
    if u.role == "admin":
        auth_service.user_repo.set_role(user_id, "user")
    auth_service.user_repo.delete_user(user_id)


def _login_headers(username: str, password: str):
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    token = data["access_token"]
    assert data["token_type"] == "bearer"
    return {"Authorization": f"Bearer {token}"}, data["user"], token


def test_auth_and_conversations():
    # 1. System status (public)
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    print("Auth status:", res.json())

    # 1b. Unauthenticated requests to protected endpoints must return 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/conversations").status_code == 401
    assert client.get("/api/admin/metrics").status_code == 401
    assert client.post("/api/chat", json={"query": "amazing"}).status_code == 401

    # 2. Register test users
    test_uname = "learner_unit_test"
    other_uname = "learner_unit_other"
    for uname in (test_uname, other_uname):
        existing = auth_service.user_repo.get_by_username(uname)
        if existing:
            _delete_ephemeral_user(existing.id)

    reg_res = client.post(
        "/api/auth/register",
        json={
            "username": test_uname,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "display_name": "Learner Unit",
        },
    )
    assert reg_res.status_code == 200
    user_data = reg_res.json()["user"]
    user_id = user_data["id"]

    reg_other = client.post(
        "/api/auth/register",
        json={
            "username": other_uname,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "display_name": "Other Learner",
        },
    )
    assert reg_other.status_code == 200
    other_id = reg_other.json()["user"]["id"]

    try:
        # 3. Login test & token issuance
        headers, logged_user, token = _login_headers(test_uname, "Password123!")
        assert logged_user["username"] == test_uname
        other_headers, _, _ = _login_headers(other_uname, "Password123!")

        # Verify /api/auth/me with valid token, and reject IDOR ?user_id=other_id
        me_res = client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["user"]["id"] == user_id
        assert client.get(f"/api/auth/me?user_id={other_id}", headers=headers).status_code == 403

        # 4. Create conversation
        conv_res = client.post(
            "/api/conversations",
            headers=headers,
            json={"user_id": user_id, "title": "Buổi học từ vựng A1"},
        )
        assert conv_res.status_code == 200
        conv_id = conv_res.json()["conversation"]["id"]

        # 5. List conversations & IDOR check
        list_res = client.get("/api/conversations", headers=headers)
        assert list_res.status_code == 200
        assert client.get(f"/api/conversations?user_id={other_id}", headers=headers).status_code == 403
        assert client.get(f"/api/conversations/{conv_id}/messages", headers=other_headers).status_code == 404

        # 6. Toggle pin
        pin_res = client.patch(f"/api/conversations/{conv_id}/pin", headers=headers)
        assert pin_res.status_code == 200
        assert pin_res.json()["is_pinned"] is True

        # 7. Rename conversation
        rename_res = client.patch(
            f"/api/conversations/{conv_id}/title",
            headers=headers,
            json={"title": "Buổi học từ vựng A1 - Đã đổi tên"},
        )
        assert rename_res.status_code == 200
        assert rename_res.json()["title"] == "Buổi học từ vựng A1 - Đã đổi tên"

        # 8. Test Streaming SSE endpoint (and block cross-user conversation_id write)
        cross_stream = client.post(
            "/api/chat/stream",
            headers=other_headers,
            json={"query": "amazing", "conversation_id": conv_id},
        )
        assert cross_stream.status_code == 403

        stream_res = client.post(
            "/api/chat/stream",
            headers=headers,
            json={
                "query": "amazing nghĩa là gì?",
                "level": "A1",
                "conversation_id": conv_id,
                "user_id": user_id,
            },
        )
        assert stream_res.status_code == 200
        sse_text = stream_res.text
        assert "data: " in sse_text
        assert "[DONE]" in sse_text
        assert "Từ bạn tìm kiếm: amazing" in sse_text

        # 9. Get messages
        msgs_res = client.get(f"/api/conversations/{conv_id}/messages", headers=headers)
        assert msgs_res.status_code == 200
        msgs = msgs_res.json()["messages"]
        assert len(msgs) >= 2  # user + assistant

        # 10. Change password revokes old token and returns fresh token
        cp_res = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "Password123!",
                "new_password": "Password456!",
                "confirm_password": "Password456!",
            },
        )
        assert cp_res.status_code == 200, f"Change password failed: {cp_res.text}"
        new_token = cp_res.json()["access_token"]
        assert new_token != token
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        new_headers = {"Authorization": f"Bearer {new_token}"}
        assert client.get("/api/auth/me", headers=new_headers).status_code == 200

        # 11. Logout revokes active token
        logout_res = client.post("/api/auth/logout", headers=new_headers)
        assert logout_res.status_code == 200
        assert client.get("/api/auth/me", headers=new_headers).status_code == 401

        # Clean up conversation
        relogin_headers, _, _ = _login_headers(test_uname, "Password456!")
        client.delete(f"/api/conversations/{conv_id}", headers=relogin_headers)
    finally:
        _delete_ephemeral_user(user_id)
        _delete_ephemeral_user(other_id)


def test_admin_endpoints():
    ts = int(time.time())
    admin_user = _create_ephemeral_user(f"temp_admin_{ts}", "AdminPass123!", role="admin")
    regular_user = _create_ephemeral_user(f"temp_user_{ts}", "UserPass123!", role="user")
    admin_id = admin_user.id
    user_id = regular_user.id

    try:
        admin_headers, _, _ = _login_headers(admin_user.username, "AdminPass123!")
        user_headers, _, _ = _login_headers(regular_user.username, "UserPass123!")

        # 1. Non-admin access should be forbidden (403), even if spoofing ?user_id=<admin_id>
        res_forbidden = client.get(f"/api/admin/metrics?user_id={admin_id}", headers=user_headers)
        assert res_forbidden.status_code == 403
        res_forbidden_plain = client.get("/api/admin/metrics", headers=user_headers)
        assert res_forbidden_plain.status_code == 403
        print("Non-admin 403 & anti-spoofing check passed!")

        # 2. Admin access to metrics (4 storage layers)
        metrics_res = client.get("/api/admin/metrics", headers=admin_headers)
        assert metrics_res.status_code == 200
        metrics = metrics_res.json()
        assert metrics["jsonl_disk_count"] is not None
        assert metrics["engine_records_count"] is not None
        assert metrics["chroma_count"] is not None
        assert metrics["bm25_count"] is not None

        # 3. Active sources
        sources_res = client.get("/api/admin/sources", headers=admin_headers)
        assert sources_res.status_code == 200

        # 4. Telemetry (VRAM, RAM, CPU)
        telemetry_res = client.get("/api/admin/telemetry", headers=admin_headers)
        assert telemetry_res.status_code == 200
        telem = telemetry_res.json()
        assert "vram" in telem and "ram" in telem and "cpu" in telem

        # 5. Ollama status
        ollama_res = client.get("/api/admin/ollama", headers=admin_headers)
        assert ollama_res.status_code == 200

        # 6. Audit logs
        audit_res = client.get("/api/admin/audit-logs?limit=5", headers=admin_headers)
        assert audit_res.status_code == 200
        assert "logs" in audit_res.json()

        # 7. User Management: Stats & List
        user_stats_res = client.get("/api/admin/users/stats", headers=admin_headers)
        assert user_stats_res.status_code == 200
        u_stats = user_stats_res.json()
        assert "total" in u_stats and "active_admins" in u_stats

        users_list_res = client.get("/api/admin/users?limit=10", headers=admin_headers)
        assert users_list_res.status_code == 200
        assert len(users_list_res.json()["users"]) >= 1

        # 8. User Management: Lock/Unlock revokes token, Role update, Reset password, Protection Rules
        test_u = _create_ephemeral_user(f"temp_mgmt_{ts}", "Pass123456!", role="user")
        temp_id = test_u.id
        temp_headers, _, _ = _login_headers(test_u.username, "Pass123456!")
        assert client.get("/api/auth/me", headers=temp_headers).status_code == 200

        # Lock user -> revokes user's active token!
        lock_res = client.patch(f"/api/admin/users/{temp_id}/status", headers=admin_headers, json={"is_active": False})
        assert lock_res.status_code == 200
        assert lock_res.json()["is_active"] is False
        assert client.get("/api/auth/me", headers=temp_headers).status_code == 401

        # Unlock user -> SUCCESS
        unlock_res = client.patch(f"/api/admin/users/{temp_id}/status", headers=admin_headers, json={"is_active": True})
        assert unlock_res.status_code == 200
        assert unlock_res.json()["is_active"] is True

        # Promote to admin
        role_res = client.patch(f"/api/admin/users/{temp_id}/role", headers=admin_headers, json={"role": "admin"})
        assert role_res.status_code == 200
        assert role_res.json()["role"] == "admin"

        # Reset password
        pw_res = client.post(
            f"/api/admin/users/{temp_id}/reset-password",
            headers=admin_headers,
            json={"new_password": "NewSecretPass789!"},
        )
        assert pw_res.status_code == 200

        # PROTECTED: Attempting to lock an admin account must FAIL with 400
        admin_lock_res = client.patch(
            f"/api/admin/users/{temp_id}/status",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert admin_lock_res.status_code == 400
        assert "Không thể vô hiệu hóa tài khoản Quản trị viên" in admin_lock_res.json()["detail"]

        # PROTECTED: Attempting to delete an admin account must FAIL with 400
        admin_del_res = client.delete(f"/api/admin/users/{temp_id}", headers=admin_headers)
        assert admin_del_res.status_code == 400
        assert "Không thể xóa tài khoản Quản trị viên" in admin_del_res.json()["detail"]

        # Demote back to user & delete
        demote_res = client.patch(f"/api/admin/users/{temp_id}/role", headers=admin_headers, json={"role": "user"})
        assert demote_res.status_code == 200
        del_res = client.delete(f"/api/admin/users/{temp_id}", headers=admin_headers)
        assert del_res.status_code == 200

        # 9. Multi-file batch upload, duplicate prevention & clear KB
        test_multi_file_batch_upload(admin_headers)
        test_duplicate_file_prevention(admin_headers)
        test_clear_kb_deletes_all_ingested_data(admin_headers)
    finally:
        _delete_ephemeral_user(user_id)
        _delete_ephemeral_user(admin_id)


def test_multi_file_batch_upload(admin_headers: dict):
    """Kiểm thử tính năng nạp nhiều tệp cùng lúc và phương thức alias process_batch."""
    from vocab_backend.admin_routes import batch_manager

    assert hasattr(batch_manager, "process_batch")
    assert hasattr(batch_manager, "ingest_batch")

    empty_report = batch_manager.process_batch(file_paths=[])
    assert empty_report.total_files == 0

    ts = int(time.time())
    csv1 = f"word,question,answer,level\nsolitary_{ts},solitary_{ts} có nghĩa là gì?,cô độc / một mình,B2\n"
    csv2 = f"word,question,answer,level\nvibrant_{ts},vibrant_{ts} có nghĩa là gì?,sôi động / rực rỡ,B1\n"

    files = [
        ("files", (f"test_multi_vocab_{ts}_1.csv", csv1.encode("utf-8"), "text/csv")),
        ("files", (f"test_multi_vocab_{ts}_2.csv", csv2.encode("utf-8"), "text/csv")),
    ]

    res = client.post(
        "/api/admin/upload",
        headers=admin_headers,
        data={"mode": "merge"},
        files=files,
    )
    assert res.status_code == 200, f"Upload multi-file failed: {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert data["files_processed"] == 2
    assert (data["success_count"] + data["skipped_count"]) >= 2
    assert len(data["file_results"]) == 2


def test_duplicate_file_prevention(admin_headers: dict):
    """Kiểm thử: khi nạp file trùng thì không thêm vào raw, chỉ thêm đúng 1 loại file đó."""
    ts = int(time.time())
    dup_csv_content = f"word,question,answer,level\nzenith_{ts},zenith_{ts} nghĩa là gì?,đỉnh cao / điểm cao nhất,C1\n"

    file_a = f"test_dup_{ts}_A.csv"
    file_b = f"test_dup_{ts}_B.csv"

    res = client.post(
        "/api/admin/upload",
        headers=admin_headers,
        data={"mode": "merge"},
        files=[
            ("files", (file_a, dup_csv_content.encode("utf-8"), "text/csv")),
            ("files", (file_b, dup_csv_content.encode("utf-8"), "text/csv")),
        ],
    )
    assert res.status_code == 200, f"Upload duplicate failed: {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert data["files_processed"] == 2
    assert data["skipped_count"] >= 1

    raw_dir = Path("data/raw")
    assert (raw_dir / file_a).exists()
    assert not (raw_dir / file_b).exists()
    assert len(list(raw_dir.glob("tmp_*"))) == 0

    res2 = client.post(
        "/api/admin/upload",
        headers=admin_headers,
        data={"mode": "merge"},
        files=[("files", (file_a, dup_csv_content.encode("utf-8"), "text/csv"))],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["skipped_count"] == 1
    assert data2["success_count"] == 0
    assert len(list(raw_dir.glob("raw_*"))) == 0


def test_clear_kb_deletes_all_ingested_data(admin_headers: dict):
    """Kiểm thử: khi xóa dữ liệu thì xóa hết những dữ liệu đã nạp vào raw, ChromaDB, BM25, JSONL."""
    import tempfile, shutil

    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    backup_dir = Path(tempfile.mkdtemp(prefix="kb_test_backup_"))
    jsonl_path = processed_dir / "qa_records.jsonl"
    manifest_path = processed_dir / "sources_manifest.json"

    try:
        for f in raw_dir.iterdir():
            if f.is_file() and f.name != "dictionary_en_vi.db":
                shutil.copy2(f, backup_dir / f.name)

        if jsonl_path.exists():
            shutil.copy2(jsonl_path, backup_dir / "qa_records.jsonl")
        if manifest_path.exists():
            shutil.copy2(manifest_path, backup_dir / "sources_manifest.json")

        res = client.post("/api/admin/clear-kb", headers=admin_headers)
        assert res.status_code == 200, f"Clear KB failed: {res.text}"
        assert res.json()["status"] == "success"

        remaining_raw = [p.name for p in raw_dir.iterdir() if p.is_file()]
        for f_name in remaining_raw:
            assert f_name in [
                ".gitkeep",
                ".gitignore",
                "dictionary_en_vi.db",
                "dictionary_en_vi.db.backup",
                "mau_nhap_lieu_tuvung.xlsx",
            ], f"Tệp không được phép còn lại trong raw: {f_name}"

        from vocab_backend.admin_routes import batch_manager
        metrics_res = client.get("/api/admin/metrics", headers=admin_headers)
        assert metrics_res.status_code == 200
        metrics = metrics_res.json()
        assert metrics["jsonl_disk_count"] == 0
        assert metrics["chroma_count"] == 0
        assert metrics["bm25_count"] == 0
        assert len(batch_manager.get_active_sources()) == 0
    finally:
        for f in backup_dir.iterdir():
            if f.name == "qa_records.jsonl":
                shutil.copy2(f, jsonl_path)
            elif f.name == "sources_manifest.json":
                shutil.copy2(f, manifest_path)
            elif f.is_file():
                shutil.copy2(f, raw_dir / f.name)
        shutil.rmtree(backup_dir, ignore_errors=True)

        from vocab_backend.admin_routes import batch_manager
        from src.retriever.bge_chroma import BGEChromaRetriever
        from src.retriever.bm25_retriever import BM25Retriever
        recs = batch_manager.loader.load_from_jsonl() or []
        if recs:
            BGEChromaRetriever([]).upsert_records(recs)
            BM25Retriever(recs)
            from vocab_backend.api_server import get_chat_engine
            engine = get_chat_engine()
            if engine:
                engine.update_knowledge_base(recs)


if __name__ == "__main__":
    test_auth_and_conversations()
    print("ALL AUTH & CONVERSATIONS TESTS PASSED!")
    test_admin_endpoints()
    print("ALL ADMIN & MULTI-FILE UPLOAD TESTS PASSED!")
