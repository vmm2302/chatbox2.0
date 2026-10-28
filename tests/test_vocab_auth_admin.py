"""Integration test for new Auth, Conversations, Streaming, and Admin routes."""

import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vocab_backend.api_server import app
from src.auth.security import hash_password
from src.auth.service import AuthService

client = TestClient(app)
auth_service = AuthService()


def test_auth_and_conversations():
    # 1. System status
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    print("Auth status:", res.json())

    # 2. Register a test user
    test_uname = "learner_unit_test"
    # Ensure cleanup if exists
    existing = auth_service.user_repo.get_by_username(test_uname)
    if existing:
        auth_service.user_repo.delete_user(existing.id)

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
    print("Registered test user:", user_id)

    # 3. Login test
    login_res = client.post(
        "/api/auth/login",
        json={"username": test_uname, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["username"] == test_uname
    print("Login successful!")

    # 4. Create conversation
    conv_res = client.post(
        "/api/conversations",
        json={"user_id": user_id, "title": "Buổi học từ vựng A1"},
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["conversation"]["id"]
    print("Created conversation:", conv_id)

    # 5. List conversations
    list_res = client.get(f"/api/conversations?user_id={user_id}")
    assert list_res.status_code == 200

    # 6. Toggle pin
    pin_res = client.patch(f"/api/conversations/{conv_id}/pin?user_id={user_id}")
    assert pin_res.status_code == 200
    assert pin_res.json()["is_pinned"] is True

    # 7. Rename conversation
    rename_res = client.patch(
        f"/api/conversations/{conv_id}/title",
        json={"user_id": user_id, "title": "Buổi học từ vựng A1 - Đã đổi tên"},
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Buổi học từ vựng A1 - Đã đổi tên"

    # 8. Test Streaming SSE endpoint
    stream_res = client.post(
        "/api/chat/stream",
        json={
            "query": "amazing nghĩa là gì?",
            "level": "A1",
            "conversation_id": conv_id,
            "user_id": user_id,
        },
    )
    assert stream_res.status_code == 200
    sse_text = stream_res.text
    print("SSE TEXT RECEIVED:\n", sse_text[:300])
    assert "data: " in sse_text
    assert "[DONE]" in sse_text
    assert "Từ bạn tìm kiếm: amazing" in sse_text
    print("Streaming SSE endpoint passed!")

    # 9. Get messages
    msgs_res = client.get(f"/api/conversations/{conv_id}/messages?user_id={user_id}")
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()["messages"]
    assert len(msgs) >= 2  # user + assistant
    print("Retrieved messages count:", len(msgs))

    # Clean up conversation and user
    client.delete(f"/api/conversations/{conv_id}?user_id={user_id}")
    auth_service.user_repo.delete_user(user_id)
    print("Cleaned up test data.")


if __name__ == "__main__":
    test_auth_and_conversations()
    print("ALL AUTH & CONVERSATIONS TESTS PASSED!")



def test_admin_endpoints():
    admin_id = 1  # Existing admin user
    user_id = 3   # Existing regular user

    # 1. Non-admin access should be forbidden (403)
    res_forbidden = client.get(f"/api/admin/metrics?user_id={user_id}")
    assert res_forbidden.status_code == 403
    print("Non-admin 403 check passed!")

    # 2. Admin access to metrics (4 storage layers)
    metrics_res = client.get(f"/api/admin/metrics?user_id={admin_id}")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["jsonl_disk_count"] is not None
    assert metrics["engine_records_count"] is not None
    assert metrics["chroma_count"] is not None
    assert metrics["bm25_count"] is not None
    print("Admin storage metrics passed:", metrics)

    # 3. Active sources
    sources_res = client.get(f"/api/admin/sources?user_id={admin_id}")
    assert sources_res.status_code == 200
    print("Admin active sources count:", len(sources_res.json()["sources"]))

    # 4. Telemetry (VRAM, RAM, CPU)
    telemetry_res = client.get(f"/api/admin/telemetry?user_id={admin_id}")
    assert telemetry_res.status_code == 200
    telem = telemetry_res.json()
    assert "vram" in telem
    assert "ram" in telem
    assert "cpu" in telem
    print("Admin telemetry passed:", telem["resource_state"])

    # 5. Ollama status
    ollama_res = client.get(f"/api/admin/ollama?user_id={admin_id}")
    assert ollama_res.status_code == 200
    print("Admin Ollama status passed:", ollama_res.json()["configured_model"])

    # 6. Audit logs
    audit_res = client.get(f"/api/admin/audit-logs?user_id={admin_id}&limit=5")
    assert audit_res.status_code == 200
    assert "logs" in audit_res.json()
    print("Admin audit logs passed:", len(audit_res.json()["logs"]))

    # 7. User Management: Stats
    user_stats_res = client.get(f"/api/admin/users/stats?user_id={admin_id}")
    assert user_stats_res.status_code == 200
    u_stats = user_stats_res.json()
    assert "total" in u_stats
    assert "active_admins" in u_stats
    print("Admin user stats passed:", u_stats)

    # 8. User Management: List with search
    users_list_res = client.get(f"/api/admin/users?user_id={admin_id}&limit=10")
    assert users_list_res.status_code == 200
    u_list = users_list_res.json()
    assert "users" in u_list
    assert len(u_list["users"]) >= 1
    print("Admin user list passed. Total returned:", len(u_list["users"]))

    # 9. User Management: Status and Role update
    # Create temporary user for testing admin actions
    test_u = auth_service.user_repo.create_user(
        username="temp_mgmt_test",
        password_hash=hash_password("Pass123456!"),
        display_name="Temp Test User",
        role="user",
        is_active=True,
    )
    temp_id = test_u.id

    # 9. User Management: Status, Role update, and Protection Rules
    # Toggle status (lock) for regular user -> SUCCESS
    lock_res = client.patch(f"/api/admin/users/{temp_id}/status?user_id={admin_id}", json={"is_active": False})
    assert lock_res.status_code == 200
    assert lock_res.json()["is_active"] is False

    # Unlock regular user -> SUCCESS
    unlock_res = client.patch(f"/api/admin/users/{temp_id}/status?user_id={admin_id}", json={"is_active": True})
    assert unlock_res.status_code == 200
    assert unlock_res.json()["is_active"] is True

    # Promote to admin
    role_res = client.patch(f"/api/admin/users/{temp_id}/role?user_id={admin_id}", json={"role": "admin"})
    assert role_res.status_code == 200
    assert role_res.json()["role"] == "admin"

    # Reset password
    pw_res = client.post(f"/api/admin/users/{temp_id}/reset-password?user_id={admin_id}", json={"new_password": "NewSecretPass789!"})
    assert pw_res.status_code == 200

    # PROTECTED: Attempting to lock an admin account must FAIL with 400
    admin_lock_res = client.patch(f"/api/admin/users/{temp_id}/status?user_id={admin_id}", json={"is_active": False})
    assert admin_lock_res.status_code == 400
    assert "Không thể vô hiệu hóa tài khoản Quản trị viên" in admin_lock_res.json()["detail"]

    # PROTECTED: Attempting to delete an admin account must FAIL with 400
    admin_del_res = client.delete(f"/api/admin/users/{temp_id}?user_id={admin_id}")
    assert admin_del_res.status_code == 400
    assert "Không thể xóa tài khoản Quản trị viên" in admin_del_res.json()["detail"]

    # Demote back to user
    demote_res = client.patch(f"/api/admin/users/{temp_id}/role?user_id={admin_id}", json={"role": "user"})
    assert demote_res.status_code == 200
    assert demote_res.json()["role"] == "user"

    # Delete regular user -> SUCCESS
    del_res = client.delete(f"/api/admin/users/{temp_id}?user_id={admin_id}")
    assert del_res.status_code == 200
    print("Admin user actions & Admin protection rules passed!")

    # 10. Multi-file batch upload & BatchIngestionManager.process_batch alias
    test_multi_file_batch_upload(admin_id)

    # 11. Prevent duplicate raw files on upload (không thêm file trùng vào raw)
    test_duplicate_file_prevention(admin_id)

    # 12. Clear KB deletes all ingested raw files & resets all indices to 0
    test_clear_kb_deletes_all_ingested_data(admin_id)


def test_multi_file_batch_upload(admin_id: int):
    """Kiểm thử tính năng nạp nhiều tệp cùng lúc và phương thức alias process_batch."""
    from src.data.batch_ingestion import BatchIngestionManager
    from vocab_backend.admin_routes import batch_manager

    # 1. Kiểm tra phương thức alias process_batch không ném AttributeError
    assert hasattr(batch_manager, "process_batch")
    assert hasattr(batch_manager, "ingest_batch")

    # Kiểm tra gọi process_batch với file_paths rỗng
    empty_report = batch_manager.process_batch(file_paths=[])
    assert empty_report.total_files == 0
    print("BatchIngestionManager.process_batch alias verified!")

    import time
    ts = int(time.time())
    # 2. Tạo nội dung 2 tệp CSV từ vựng kiểm thử với timestamp duy nhất để tránh bị duplicate hash
    csv1 = f"word,question,answer,level\nsolitary_{ts},solitary_{ts} có nghĩa là gì?,cô độc / một mình,B2\n"
    csv2 = f"word,question,answer,level\nvibrant_{ts},vibrant_{ts} có nghĩa là gì?,sôi động / rực rỡ,B1\n"

    # Gửi cả 2 tệp cùng một lúc qua endpoint /api/admin/upload
    files = [
        ("files", (f"test_multi_vocab_{ts}_1.csv", csv1.encode("utf-8"), "text/csv")),
        ("files", (f"test_multi_vocab_{ts}_2.csv", csv2.encode("utf-8"), "text/csv")),
    ]

    res = client.post(
        "/api/admin/upload",
        data={"user_id": str(admin_id), "mode": "merge"},
        files=files,
    )
    assert res.status_code == 200, f"Upload multi-file failed: {res.text}"
    data = res.json()
    print("Multi-file upload response:", data)
    assert data["status"] == "success"
    assert data["files_processed"] == 2
    assert (data["success_count"] + data["skipped_count"]) >= 2
    assert "file_results" in data
    assert len(data["file_results"]) == 2

    print("Multi-file upload test PASSED with 2 simultaneous files!")


def test_duplicate_file_prevention(admin_id: int):
    """Kiểm thử: khi nạp file trùng thì không thêm vào raw, chỉ thêm đúng 1 loại file đó."""
    from pathlib import Path
    import time
    ts = int(time.time())
    dup_csv_content = f"word,question,answer,level\nzenith_{ts},zenith_{ts} nghĩa là gì?,đỉnh cao / điểm cao nhất,C1\n"

    file_a = f"test_dup_{ts}_A.csv"
    file_b = f"test_dup_{ts}_B.csv"

    # 1. Gửi 2 file có cùng nội dung trong 1 request
    res = client.post(
        "/api/admin/upload",
        data={"user_id": str(admin_id), "mode": "merge"},
        files=[
            ("files", (file_a, dup_csv_content.encode("utf-8"), "text/csv")),
            ("files", (file_b, dup_csv_content.encode("utf-8"), "text/csv")),
        ],
    )
    assert res.status_code == 200, f"Upload duplicate failed: {res.text}"
    data = res.json()
    print("Duplicate upload response:", data)
    assert data["status"] == "success"
    assert data["files_processed"] == 2
    assert data["skipped_count"] >= 1, "Tệp trùng lặp phải được đánh dấu SKIPPED!"

    # Kiểm tra thư mục data/raw:
    # file_a phải được lưu, nhưng file_b KHÔNG được lưu vào raw, và không có tệp tmp_... nào!
    raw_dir = Path("data/raw")
    assert (raw_dir / file_a).exists(), f"{file_a} phải được lưu trong raw"
    assert not (raw_dir / file_b).exists(), f"{file_b} trùng lặp KHÔNG được thêm vào raw"
    tmp_files = list(raw_dir.glob("tmp_*"))
    assert len(tmp_files) == 0, f"Không được sinh tệp tạm tmp_ trong raw: {tmp_files}"

    # 2. Gửi lại file_a đã tồn tại trong raw
    res2 = client.post(
        "/api/admin/upload",
        data={"user_id": str(admin_id), "mode": "merge"},
        files=[
            ("files", (file_a, dup_csv_content.encode("utf-8"), "text/csv")),
        ],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    print("Re-upload existing file response:", data2)
    assert data2["skipped_count"] == 1, "File đã tồn tại phải bị SKIPPED"
    assert data2["success_count"] == 0

    # Kiểm tra không sinh tệp raw_{hash}_... nào trong raw
    raw_hash_files = list(raw_dir.glob("raw_*"))
    assert len(raw_hash_files) == 0, f"Không được sinh tệp raw_xxxx_ trong raw: {raw_hash_files}"
    print("Duplicate file prevention in raw verified 100% PASSED!")


def test_clear_kb_deletes_all_ingested_data(admin_id: int):
    """Kiểm thử: khi xóa dữ liệu thì xóa hết những dữ liệu đã nạp vào raw, ChromaDB, BM25, JSONL."""
    from pathlib import Path
    import tempfile, shutil

    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")

    # Backup các file dữ liệu chuẩn để sau test phục hồi lại
    backup_dir = Path(tempfile.mkdtemp(prefix="kb_test_backup_"))
    try:
        # Backup data/raw
        for f in raw_dir.iterdir():
            if f.is_file() and f.name != "dictionary_en_vi.db":
                shutil.copy2(f, backup_dir / f.name)

        # Backup qa_records.jsonl và sources_manifest.json
        jsonl_path = processed_dir / "qa_records.jsonl"
        manifest_path = processed_dir / "sources_manifest.json"
        if jsonl_path.exists():
            shutil.copy2(jsonl_path, backup_dir / "qa_records.jsonl")
        if manifest_path.exists():
            shutil.copy2(manifest_path, backup_dir / "sources_manifest.json")

        # Gọi endpoint /api/admin/clear-kb
        res = client.post(f"/api/admin/clear-kb?user_id={admin_id}")
        assert res.status_code == 200, f"Clear KB failed: {res.text}"
        data = res.json()
        print("Clear KB response:", data)
        assert data["status"] == "success"

        # 1. Xác minh tất cả các file đã nạp trong data/raw đều đã bị XÓA SẠCH
        remaining_raw = [p.name for p in raw_dir.iterdir() if p.is_file()]
        print("Remaining raw files after clear:", remaining_raw)

        # Chỉ các file hệ thống được giữ lại
        for f_name in remaining_raw:
            assert f_name in [
                ".gitkeep",
                ".gitignore",
                "dictionary_en_vi.db",
                "dictionary_en_vi.db.backup",
                "mau_nhap_lieu_tuvung.xlsx",
            ], f"Tệp không được phép còn lại trong raw: {f_name}"

        # 2. Xác minh các chỉ mục đều về 0
        from vocab_backend.admin_routes import batch_manager
        metrics_res = client.get(f"/api/admin/metrics?user_id={admin_id}")
        assert metrics_res.status_code == 200
        metrics = metrics_res.json()
        print("Storage metrics after clear:", metrics)
        assert metrics["jsonl_disk_count"] == 0, "JSONL phải về 0"
        assert metrics["chroma_count"] == 0, "ChromaDB phải về 0"
        assert metrics["bm25_count"] == 0, "BM25 phải về 0"
        assert len(batch_manager.get_active_sources()) == 0, "Active sources phải về 0"

        print("Clear KB and raw deletion verified 100% PASSED!")
    finally:
        # Phục hồi lại dữ liệu để hệ thống sẵn sàng hoạt động
        for f in backup_dir.iterdir():
            if f.name == "qa_records.jsonl":
                shutil.copy2(f, jsonl_path)
            elif f.name == "sources_manifest.json":
                shutil.copy2(f, manifest_path)
            elif f.is_file():
                shutil.copy2(f, raw_dir / f.name)
        shutil.rmtree(backup_dir, ignore_errors=True)

        # Khôi phục lại chỉ mục ChromaDB & BM25 từ jsonl vừa phục hồi
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
        print("Restored original knowledge base state successfully!")


if __name__ == "__main__":
    test_auth_and_conversations()
    test_admin_endpoints()
    print("ALL ADMIN & MULTI-FILE UPLOAD TESTS PASSED!")
