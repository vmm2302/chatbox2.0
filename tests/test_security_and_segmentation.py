"""Bộ kiểm thử chuyên sâu cho 4 hạng mục mới:
1. Cơ chế Access Token HMAC-SHA256, bảng user_sessions, thu hồi & kiểm tra phân quyền RBAC/IDOR.
2. Khóa phiên gắn với người dùng xác thực trong vocab_backend/api_server.py.
3. Không dừng tiến trình trong run_vocab_web.py / run_vocab_web.ps1, chỉ yêu cầu đổi cổng.
4. Bộ tách từ tiếng Việt (pyvi + fallback) trong src/nlp/phobert_intent.py trước khi đưa vào prototype.
"""

import shutil
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import run_vocab_web
from src.auth.security import create_access_token, decode_and_verify_access_token, hash_password
from src.auth.service import AuthService
from src.data.app_db import AppDatabase
from src.data.audit_repository import AuditRepository
from src.data.session_repository import SessionRepository
from src.data.user_repository import UserRepository
from src.nlp.phobert_intent import (
    INTENT_PROTOTYPES,
    PhoBERTIntentClassifier,
    segment_vietnamese_text,
)
from vocab_backend.api_server import (
    app,
    build_user_session_key,
    clear_user_trackers,
    get_or_create_tracker,
)
from vocab_backend.dependencies import auth_service as backend_auth_service


class TestAccessTokenAndRevocation(unittest.TestCase):
    """Kiểm tra tạo, xác minh, hết hạn, giả mạo và thu hồi Access Token trên DB cô lập."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="token_sec_test_")
        self.db_path = Path(self.temp_dir) / "test_tokens.db"
        self.db = AppDatabase(db_path=self.db_path)
        self.user_repo = UserRepository(db=self.db)
        self.audit_repo = AuditRepository(db=self.db)
        self.session_repo = SessionRepository(db=self.db)
        self.auth_svc = AuthService(
            user_repo=self.user_repo,
            audit_repo=self.audit_repo,
            db=self.db,
            session_repo=self.session_repo,
        )

        self.admin = self.user_repo.create_user(
            username="sec_admin",
            password_hash=hash_password("AdminPass123!"),
            display_name="Sec Admin",
            role="admin",
            is_active=True,
        )
        self.user = self.user_repo.create_user(
            username="sec_user",
            password_hash=hash_password("UserPass123!"),
            display_name="Sec User",
            role="user",
            is_active=True,
        )

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_issue_and_verify_token_reads_live_db_role(self):
        """Token hợp lệ phải xác minh được và luôn phản ánh role mới nhất từ DB."""
        tok_info = self.auth_svc.issue_access_token(self.user)
        raw_token = tok_info["access_token"]

        verified_user, session, err = self.auth_svc.verify_access_token(raw_token)
        self.assertEqual(err, "")
        self.assertIsNotNone(verified_user)
        self.assertIsNotNone(session)
        self.assertEqual(verified_user.id, self.user.id)
        self.assertEqual(verified_user.role, "user")

        # Tampering chữ ký phải thất bại
        tampered = raw_token[:-4] + ("AAAA" if raw_token[-4:] != "AAAA" else "BBBB")
        u_bad, s_bad, err_bad = self.auth_svc.verify_access_token(tampered)
        self.assertIsNone(u_bad)
        self.assertIsNone(s_bad)
        self.assertTrue(len(err_bad) > 0)

    def test_expired_token_rejected(self):
        """Token đã hết hạn phải bị từ chối."""
        secret = b"unit_test_secret_key_for_expiry_check_32b"
        raw, _, _ = create_access_token(
            user_id=self.user.id,
            username=self.user.username,
            role="user",
            session_id="sess-exp",
            secret=secret,
            expires_minutes=1,
        )
        with patch("src.auth.security.time.time", return_value=time.time() + 120):
            with self.assertRaises(ValueError):
                decode_and_verify_access_token(raw, secret)

    def test_revocation_on_logout_disable_role_change_and_password_reset(self):
        """Thu hồi phiên tức thì khi logout, vô hiệu hóa tài khoản, đổi vai trò hoặc đặt lại mật khẩu."""
        # 1. Logout thu hồi session
        t1 = self.auth_svc.issue_access_token(self.user)
        u1, s1, _ = self.auth_svc.verify_access_token(t1["access_token"])
        self.assertIsNotNone(u1)
        self.auth_svc.revoke_session(s1.id, actor=u1)
        u1_after, _, _ = self.auth_svc.verify_access_token(t1["access_token"])
        self.assertIsNone(u1_after)

        # 2. Admin vô hiệu hóa tài khoản -> thu hồi mọi token
        t2 = self.auth_svc.issue_access_token(self.user)
        ok, _ = self.auth_svc.admin_toggle_active(self.admin, self.user.id, False)
        self.assertTrue(ok)
        u2_after, _, _ = self.auth_svc.verify_access_token(t2["access_token"])
        self.assertIsNone(u2_after)

        # Kích hoạt lại và kiểm tra đổi role
        self.auth_svc.admin_toggle_active(self.admin, self.user.id, True)
        t3 = self.auth_svc.issue_access_token(self.user)
        ok_role, _ = self.auth_svc.admin_change_role(self.admin, self.user.id, "admin")
        self.assertTrue(ok_role)
        u3_after, _, _ = self.auth_svc.verify_access_token(t3["access_token"])
        self.assertIsNone(u3_after)

        # Hạ role lại user và kiểm tra reset password
        self.auth_svc.admin_change_role(self.admin, self.user.id, "user")
        t4 = self.auth_svc.issue_access_token(self.user)
        ok_pw, _ = self.auth_svc.admin_reset_password(self.admin, self.user.id, "NewUserPass999!")
        self.assertTrue(ok_pw)
        u4_after, _, _ = self.auth_svc.verify_access_token(t4["access_token"])
        self.assertIsNone(u4_after)


class TestUserBoundSessionKeyAPIServer(unittest.TestCase):
    """Kiểm tra khóa phiên gắn với người dùng xác thực trong api_server.py."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        ts = int(time.time() * 1000)
        cls.user_a_name = f"sess_user_a_{ts}"
        cls.user_b_name = f"sess_user_b_{ts}"

        reg_a = cls.client.post(
            "/api/auth/register",
            json={"username": cls.user_a_name, "password": "Password123!", "confirm_password": "Password123!"},
        )
        reg_b = cls.client.post(
            "/api/auth/register",
            json={"username": cls.user_b_name, "password": "Password123!", "confirm_password": "Password123!"},
        )
        cls.user_a_id = reg_a.json()["user"]["id"]
        cls.user_b_id = reg_b.json()["user"]["id"]

        login_a = cls.client.post("/api/auth/login", json={"username": cls.user_a_name, "password": "Password123!"})
        login_b = cls.client.post("/api/auth/login", json={"username": cls.user_b_name, "password": "Password123!"})
        cls.headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
        cls.headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        clear_user_trackers(cls.user_a_id)
        clear_user_trackers(cls.user_b_id)
        backend_auth_service.user_repo.delete_user(cls.user_a_id)
        backend_auth_service.user_repo.delete_user(cls.user_b_id)

    def test_build_user_session_key_and_tracker_isolation(self):
        """Hai người dùng khác nhau cùng conversation_id mặc định phải có khóa phiên và TopicTracker tách biệt."""
        key_a = build_user_session_key(self.user_a_id, "default_session")
        key_b = build_user_session_key(self.user_b_id, "default_session")
        self.assertNotEqual(key_a, key_b)
        self.assertTrue(key_a.startswith(f"user:{self.user_a_id}:"))
        self.assertTrue(key_b.startswith(f"user:{self.user_b_id}:"))

        trk_a = get_or_create_tracker("default_session", user_id=self.user_a_id)
        trk_b = get_or_create_tracker("default_session", user_id=self.user_b_id)
        self.assertIsNot(trk_a, trk_b)

    def test_api_chat_session_isolation_between_users(self):
        """User A tra từ 'about' không được rò rỉ active_word sang User B khi gọi /api/chat."""
        clear_user_trackers(self.user_a_id)
        clear_user_trackers(self.user_b_id)

        # User A tra từ 'about' với default_session
        res_a = self.client.post(
            "/api/chat",
            headers=self.headers_a,
            json={"query": "about nghĩa là gì?", "conversation_id": "default_session"},
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json().get("word"), "about")

        # User B hỏi mơ hồ "từ này nghĩa là gì?" cũng với default_session -> KHÔNG được kế thừa "about" của User A
        res_b = self.client.post(
            "/api/chat",
            headers=self.headers_b,
            json={"query": "từ này nghĩa là gì?", "conversation_id": "default_session"},
        )
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        self.assertEqual(data_b.get("word"), "")
        self.assertEqual(data_b.get("meta", {}).get("mode"), "CLARIFICATION")

        # User B giả mạo user_id của User A trong payload phải bị chặn 403
        res_spoof = self.client.post(
            "/api/chat",
            headers=self.headers_b,
            json={"query": "about", "user_id": self.user_a_id},
        )
        self.assertEqual(res_spoof.status_code, 403)


class TestRunVocabWebNoProcessKill(unittest.TestCase):
    """Kiểm tra run_vocab_web.py không dừng tiến trình, chỉ yêu cầu đổi cổng."""

    def test_no_taskkill_or_stop_process_in_launchers(self):
        py_text = (PROJECT_ROOT / "run_vocab_web.py").read_text(encoding="utf-8")
        ps1_text = (PROJECT_ROOT / "run_vocab_web.ps1").read_text(encoding="utf-8")
        self.assertNotIn("taskkill", py_text.lower())
        self.assertNotIn("free_port_if_in_use", py_text)
        self.assertNotIn("Stop-Process", ps1_text)

    def test_busy_port_prompts_for_new_port_without_killing(self):
        """Khi cổng bận, resolve_available_port yêu cầu đổi cổng và giữ nguyên socket đang chạy."""
        busy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        busy_sock.bind(("127.0.0.1", 0))
        busy_sock.listen(1)
        busy_port = busy_sock.getsockname()[1]

        free_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        free_sock.bind(("127.0.0.1", 0))
        free_port = free_sock.getsockname()[1]
        free_sock.close()

        try:
            self.assertFalse(run_vocab_web.is_port_available(busy_port, host="127.0.0.1"))
            self.assertTrue(run_vocab_web.is_port_available(free_port, host="127.0.0.1"))

            # Non-interactive mode -> thoát với mã lỗi yêu cầu --port mới
            with self.assertRaises(SystemExit) as ctx:
                run_vocab_web.resolve_available_port(busy_port, host="127.0.0.1", is_interactive=False)
            self.assertEqual(ctx.exception.code, 1)

            # Interactive mode -> từ chối nhập không hợp lệ / cổng vẫn bận, chấp nhận cổng rảnh
            answers = iter(["abc", str(busy_port), str(free_port)])
            chosen = run_vocab_web.resolve_available_port(
                busy_port,
                host="127.0.0.1",
                input_fn=lambda _prompt: next(answers),
                is_interactive=True,
            )
            self.assertEqual(chosen, free_port)
            # Đảm bảo socket cũ vẫn sống, không bị đóng/kill
            self.assertNotEqual(busy_sock.fileno(), -1)
        finally:
            busy_sock.close()


class TestPhoBERTWordSegmentation(unittest.TestCase):
    """Kiểm tra bộ tách từ tiếng Việt trước khi đưa vào Intent Prototypes & PhoBERT."""

    def test_segment_vietnamese_text_pyvi_and_hyphen_preservation(self):
        seg_vie = segment_vietnamese_text("Gia đình tiếng Anh là gì")
        self.assertIn("gia_đình", seg_vie)

        seg_oos = segment_vietnamese_text("Thời tiết tại Hà Nội hôm nay thế nào")
        self.assertIn("thời_tiết", seg_oos)
        self.assertIn("hà_nội", seg_oos)
        self.assertIn("hôm_nay", seg_oos)

        seg_en = segment_vietnamese_text("hard-working nghĩa là gì?")
        self.assertIn("hard-working", seg_en)
        self.assertIn("nghĩa_là", seg_en)

    def test_segment_vietnamese_text_offline_fallback(self):
        """Bộ tách từ dự phòng thuần Python phải tách đúng các từ ghép cốt lõi khi thiếu pyvi."""
        seg = segment_vietnamese_text("Trường học có nghĩa là gì?", use_pyvi=False)
        self.assertIn("trường_học", seg)
        self.assertIn("có_nghĩa_là", seg)

    def test_classifier_segments_prototypes_before_encoding(self):
        """PhoBERTIntentClassifier phải tách từ toàn bộ INTENT_PROTOTYPES và câu truy vấn."""
        clf = PhoBERTIntentClassifier()
        clf.initialize()
        self.assertEqual(set(clf.segmented_prototypes.keys()), set(INTENT_PROTOTYPES.keys()))
        self.assertTrue(
            any("gia_đình" in ex for ex in clf.segmented_prototypes["TRANSLATE_VIE_TO_ENG"]),
            f"Prototype phải được tách từ trước khi mã hóa: {clf.segmented_prototypes['TRANSLATE_VIE_TO_ENG']}",
        )
        self.assertTrue(
            any("thời_tiết" in ex and "hà_nội" in ex for ex in clf.segmented_prototypes["OUT_OF_SCOPE"]),
            f"OUT_OF_SCOPE prototype phải được tách từ: {clf.segmented_prototypes['OUT_OF_SCOPE']}",
        )

        res_def = clf.classify_intent("giải thích cho tôi từ abandon có nghĩa là gì")
        self.assertEqual(res_def.intent, "DEFINE_VOCAB")
        res_oos = clf.classify_intent("thời tiết tại hà nội hôm nay thế nào?")
        self.assertEqual(res_oos.intent, "OUT_OF_SCOPE")


if __name__ == "__main__":
    unittest.main()
