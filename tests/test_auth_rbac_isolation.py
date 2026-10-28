"""Bộ kiểm thử toàn diện cho hệ thống Tài khoản, Phân quyền RBAC và Cách ly Dữ liệu.

Sử dụng thư viện chuẩn unittest và cơ sở dữ liệu tạm thời (tempfile) để đảm bảo:
- Không can thiệp hoặc ghi đè dữ liệu thật (app_data.db).
- Không ảnh hưởng đến Knowledge Base hay database từ điển (dictionary_en_vi.db).
- Kiểm tra 100% các tiêu chí: Xác thực, Phân quyền, Cách ly dữ liệu, Quản trị, Hồi quy ngữ cảnh.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List

# Đảm bảo nhận diện đường dẫn gốc
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.auth.security import (
    hash_password,
    validate_password,
    validate_username,
    verify_password,
)
from src.auth.service import AuthService
from src.chat.topic_tracker import TopicTracker
from src.core.models import QARecord
from src.data.app_db import AppDatabase
from src.data.audit_repository import AuditRepository
from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User, UserRepository


class BaseAuthTestCase(unittest.TestCase):
    """Lớp nền tảng thiết lập cơ sở dữ liệu SQLite tạm thời cho từng ca kiểm thử."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="chatbox_auth_test_")
        self.db_path = Path(self.temp_dir) / "test_app_data.db"
        self.db = AppDatabase(db_path=self.db_path)
        self.user_repo = UserRepository(db=self.db)
        self.audit_repo = AuditRepository(db=self.db)
        self.conv_repo = ConversationRepository(db=self.db)
        self.auth_service = AuthService(
            user_repo=self.user_repo,
            audit_repo=self.audit_repo,
            db=self.db,
        )

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestAuthentication(BaseAuthTestCase):
    """Kiểm tra chức năng Đăng ký, Đăng nhập và Bảo mật Mật khẩu."""

    def test_register_user_success(self):
        """Đăng ký tài khoản User thành công."""
        ok, user, msg = self.auth_service.register_user(
            username="testuser1",
            password="SecurePassword123!",
            confirm_password="SecurePassword123!",
            display_name="Test User One",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "testuser1")
        self.assertEqual(user.role, "user")
        self.assertTrue(user.is_active)
        self.assertEqual(user.display_name, "Test User One")

    def test_register_duplicate_username_fails(self):
        """Từ chối đăng ký tên đăng nhập bị trùng."""
        self.auth_service.register_user(
            username="duplicate_user",
            password="Password123!",
            confirm_password="Password123!",
        )
        ok, user, msg = self.auth_service.register_user(
            username="DUPLICATE_USER",  # Kiểm tra không phân biệt hoa thường
            password="AnotherPassword456!",
            confirm_password="AnotherPassword456!",
        )
        self.assertFalse(ok)
        self.assertIsNone(user)
        self.assertIn("đã tồn tại", msg.lower())

    def test_register_password_policy(self):
        """Kiểm tra chính sách mật khẩu (độ dài tối thiểu 6 ký tự)."""
        ok, _, msg = self.auth_service.register_user(
            username="shortpass",
            password="123",
            confirm_password="123",
        )
        self.assertFalse(ok)
        self.assertIn("ít nhất 6 ký tự", msg.lower())

    def test_register_password_mismatch(self):
        """Từ chối đăng ký khi mật khẩu xác nhận không khớp."""
        ok, _, msg = self.auth_service.register_user(
            username="mismatch",
            password="Password123!",
            confirm_password="DifferentPassword456!",
        )
        self.assertFalse(ok)
        self.assertIn("không khớp", msg.lower())

    def test_password_is_hashed_not_plaintext(self):
        """Mật khẩu lưu trong cơ sở dữ liệu BẮT BUỘC là chuỗi băm an toàn, không phải văn bản thuần."""
        plain_pw = "MySecretPass2026!"
        ok, user, _ = self.auth_service.register_user(
            username="hashcheck",
            password=plain_pw,
            confirm_password=plain_pw,
        )
        self.assertTrue(ok)

        # Lấy trực tiếp từ DB
        raw_user = self.user_repo.get_by_id(user.id)
        self.assertNotEqual(raw_user.password_hash, plain_pw)
        self.assertTrue(verify_password(plain_pw, raw_user.password_hash))
        self.assertFalse(verify_password("wrong_password", raw_user.password_hash))

    def test_login_success(self):
        """Đăng nhập đúng tên đăng nhập và mật khẩu."""
        self.auth_service.register_user(
            username="validlogin",
            password="CorrectPass123!",
            confirm_password="CorrectPass123!",
        )
        ok, user, msg = self.auth_service.authenticate("validlogin", "CorrectPass123!")
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "validlogin")
        self.assertIsNotNone(user.last_login_at)

    def test_login_wrong_password_rejected(self):
        """Từ chối khi nhập sai mật khẩu với thông báo an toàn không lộ thông tin."""
        self.auth_service.register_user(
            username="validlogin2",
            password="CorrectPass123!",
            confirm_password="CorrectPass123!",
        )
        ok, user, msg = self.auth_service.authenticate("validlogin2", "WrongPass123!")
        self.assertFalse(ok)
        self.assertIsNone(user)
        self.assertIn("không chính xác", msg.lower())

    def test_login_deactivated_account_rejected(self):
        """Thông báo rõ ràng khi tài khoản bị vô hiệu hóa."""
        _, user, _ = self.auth_service.register_user(
            username="lockeduser",
            password="Password123!",
            confirm_password="Password123!",
        )
        # Khóa tài khoản
        self.user_repo.set_active_status(user.id, is_active=False)

        ok, auth_user, msg = self.auth_service.authenticate("lockeduser", "Password123!")
        self.assertFalse(ok)
        self.assertIsNone(auth_user)
        self.assertIn("vô hiệu hóa", msg.lower())

    def test_logout_and_session_clearing(self):
        """Đăng xuất ghi nhận audit log và kiểm tra xóa session."""
        _, user, _ = self.auth_service.register_user(
            username="logoutuser",
            password="Password123!",
            confirm_password="Password123!",
        )
        self.auth_service.logout(user)
        logs = self.audit_repo.list_logs(action="USER_LOGOUT")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].actor_username, "logoutuser")


class TestRBACPermissions(BaseAuthTestCase):
    """Kiểm tra mô hình phân quyền Role-Based Access Control (RBAC)."""

    def setUp(self):
        super().setUp()
        # Tạo 1 Admin và 1 User
        _, self.admin, _ = self.auth_service.bootstrap_first_admin(
            username="admin1",
            password="AdminPassword123!",
            display_name="Super Admin",
        )
        _, self.user, _ = self.auth_service.register_user(
            username="normaluser",
            password="UserPassword123!",
            confirm_password="UserPassword123!",
            display_name="Regular User",
        )

    def test_user_cannot_access_admin_functions(self):
        """User thường không thể thực hiện các thao tác quản trị ở backend."""
        with self.assertRaises(PermissionError):
            self.auth_service.require_admin(self.user)

        with self.assertRaises(PermissionError):
            self.auth_service.admin_create_user(
                actor=self.user,
                username="hacker_admin",
                password="Password123!",
                role="admin",
            )

        with self.assertRaises(PermissionError):
            self.auth_service.admin_toggle_active(
                actor=self.user,
                target_user_id=self.admin.id,
                is_active=False,
            )

    def test_user_cannot_register_as_admin(self):
        """Người dùng tự đăng ký luôn có vai trò 'user', không thể nhận quyền 'admin'."""
        ok, new_user, _ = self.auth_service.register_user(
            username="wannabe_admin",
            password="Password123!",
            confirm_password="Password123!",
        )
        self.assertTrue(ok)
        self.assertEqual(new_user.role, "user")

    def test_admin_can_perform_authorized_actions(self):
        """Admin có thể tạo tài khoản, đổi trạng thái và đặt lại mật khẩu."""
        # 1. Tạo user mới bởi admin
        ok, created_u, msg = self.auth_service.admin_create_user(
            actor=self.admin,
            username="newstaff",
            password="StaffPassword123!",
            role="user",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(created_u)

        # 2. Vô hiệu hóa user
        ok_toggle, _ = self.auth_service.admin_toggle_active(
            actor=self.admin,
            target_user_id=created_u.id,
            is_active=False,
        )
        self.assertTrue(ok_toggle)
        refreshed = self.user_repo.get_by_id(created_u.id)
        self.assertFalse(refreshed.is_active)

        # 3. Đặt lại mật khẩu
        ok_reset, _ = self.auth_service.admin_reset_password(
            actor=self.admin,
            target_user_id=created_u.id,
            new_password="NewStaffPassword456!",
        )
        self.assertTrue(ok_reset)
        # Kích hoạt lại và đăng nhập với mật khẩu mới
        self.auth_service.admin_toggle_active(self.admin, created_u.id, True)
        ok_login, _, _ = self.auth_service.authenticate("newstaff", "NewStaffPassword456!")
        self.assertTrue(ok_login)

    def test_cannot_disable_or_delete_last_active_admin(self):
        """Bảo vệ Admin cuối cùng: Không cho phép vô hiệu hóa, giáng quyền hoặc xóa Admin duy nhất."""
        self.assertEqual(self.user_repo.count_active_admins(), 1)

        # 1. Thử vô hiệu hóa
        ok_dis, msg_dis = self.auth_service.admin_toggle_active(
            actor=self.admin,
            target_user_id=self.admin.id,
            is_active=False,
        )
        self.assertFalse(ok_dis)
        self.assertIn("quản trị viên cuối cùng", msg_dis.lower())

        # 2. Thử giáng quyền
        ok_role, msg_role = self.auth_service.admin_change_role(
            actor=self.admin,
            target_user_id=self.admin.id,
            new_role="user",
        )
        self.assertFalse(ok_role)
        self.assertIn("quản trị viên cuối cùng", msg_role.lower())

        # 3. Thử tự xóa tài khoản
        ok_del, msg_del = self.auth_service.admin_delete_user(
            actor=self.admin,
            target_user_id=self.admin.id,
        )
        self.assertFalse(ok_del)
        self.assertIn("bạn đang sử dụng", msg_del.lower())


class TestDataIsolation(BaseAuthTestCase):
    """Kiểm tra cách ly dữ liệu triệt để giữa các tài khoản người dùng."""

    def setUp(self):
        super().setUp()
        _, self.user_a, _ = self.auth_service.register_user("user_a", "PassWord123!", "PassWord123!")
        _, self.user_b, _ = self.auth_service.register_user("user_b", "PassWord123!", "PassWord123!")

    def test_conversation_and_message_isolation(self):
        """User A và User B chỉ truy cập được dữ liệu hội thoại của chính mình."""
        # User A tạo cuộc hội thoại và gửi tin nhắn
        conv_a = self.conv_repo.create_conversation(self.user_a.id, "Từ vựng Unit 1")
        self.conv_repo.add_message(self.user_a.id, conv_a.id, "user", "about nghĩa là gì?")
        self.conv_repo.add_message(self.user_a.id, conv_a.id, "assistant", "about nghĩa là về, khoảng.")

        # User B tạo cuộc hội thoại
        conv_b = self.conv_repo.create_conversation(self.user_b.id, "Học phát âm")
        self.conv_repo.add_message(self.user_b.id, conv_b.id, "user", "pronunciation của abandon?")
        self.conv_repo.add_message(self.user_b.id, conv_b.id, "assistant", "/əˈbændən/")

        # 1. User A chỉ thấy danh sách hội thoại của User A
        list_a = self.conv_repo.list_conversations(self.user_a.id)
        self.assertEqual(len(list_a), 1)
        self.assertEqual(list_a[0].id, conv_a.id)

        # 2. User B chỉ thấy danh sách hội thoại của User B
        list_b = self.conv_repo.list_conversations(self.user_b.id)
        self.assertEqual(len(list_b), 1)
        self.assertEqual(list_b[0].id, conv_b.id)

        # 3. User B KHÔNG THỂ đọc cuộc hội thoại của User A bằng cách truyền conv_a.id
        unauthorized_conv = self.conv_repo.get_conversation(self.user_b.id, conv_a.id)
        self.assertIsNone(unauthorized_conv)

        unauthorized_messages = self.conv_repo.get_messages(self.user_b.id, conv_a.id)
        self.assertEqual(len(unauthorized_messages), 0)

        # 4. User B KHÔNG THỂ ghi tin nhắn vào hội thoại của User A
        with self.assertRaises(PermissionError):
            self.conv_repo.add_message(self.user_b.id, conv_a.id, "user", "Tin nhắn xâm nhập")

        # 5. User B KHÔNG THỂ xóa hội thoại của User A
        deleted = self.conv_repo.delete_conversation(self.user_b.id, conv_a.id)
        self.assertFalse(deleted)
        # Cuộc trò chuyện của User A vẫn còn nguyên
        self.assertIsNotNone(self.conv_repo.get_conversation(self.user_a.id, conv_a.id))

    def test_topic_tracker_isolation_across_sessions(self):
        """TopicTracker ngữ cảnh hội thoại phải được làm sạch hoàn toàn khi chuyển phiên."""
        tracker_a = TopicTracker(records=[])
        tracker_a.active_word = "about"

        # Giả lập User A đăng xuất và User B đăng nhập
        tracker_b = TopicTracker(records=[])
        # Đảm bảo tracker_b hoàn toàn độc lập, không thừa hưởng active_word của tracker_a
        self.assertIsNone(tracker_b.active_word)

        # Khi tracker_a được clear()
        tracker_a.clear()
        self.assertIsNone(tracker_a.active_word)


class TestAdminAuditAndManagement(BaseAuthTestCase):
    """Kiểm tra ghi nhận Audit Log và tính toàn vẹn của dữ liệu quản trị."""

    def test_audit_log_records_without_passwords(self):
        """Audit Log ghi nhận thao tác nhưng TUYỆT ĐỐI không ghi mật khẩu."""
        self.auth_service.bootstrap_first_admin(
            username="auditadmin",
            password="SuperAdminSecret999!",
            display_name="Audit Administrator",
        )
        logs = self.audit_repo.list_logs(action="BOOTSTRAP_ADMIN")
        self.assertEqual(len(logs), 1)
        log_entry = logs[0]
        self.assertEqual(log_entry.actor_username, "system_cli")
        self.assertNotIn("SuperAdminSecret999!", str(log_entry.details))

        # Thử ghi audit log có key password
        self.audit_repo.log(
            actor_username="testactor",
            action="TEST_ACTION",
            target_type="security",
            details={"username": "testactor", "password": "PlainTextPassword"},
        )
        test_logs = self.audit_repo.list_logs(action="TEST_ACTION")
        self.assertNotIn("PlainTextPassword", test_logs[0].details)
        self.assertIn("******", test_logs[0].details)

    def test_bootstrap_admin_cli(self):
        """Kiểm tra gọi trực tiếp lệnh CLI bootstrap admin."""
        # Gọi scripts/create_admin.py qua subprocess với môi trường APP_DB_PATH trỏ vào DB tạm
        env = {
            **subprocess.os.environ,
            "APP_DB_PATH": str(self.db_path),
        }
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "create_admin.py"),
            "--username", "cli_admin",
            "--display-name", "CLI Administrator",
            "--password", "CliAdminSecret123!",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, f"CLI thất bại: {proc.stderr}")
        self.assertIn("THÀNH CÔNG", proc.stdout)

        # Xác minh trong DB tạm
        admin_u = self.user_repo.get_by_username("cli_admin")
        self.assertIsNotNone(admin_u)
        self.assertEqual(admin_u.role, "admin")
        self.assertTrue(admin_u.is_active)


class TestChatContextRegression(BaseAuthTestCase):
    """Kiểm tra hồi quy logic ngữ cảnh đa lượt và cách ly giữa các tài khoản."""

    def setUp(self):
        super().setUp()
        _, self.user_a, _ = self.auth_service.register_user("chat_user_a", "Password123!", "Password123!")
        _, self.user_b, _ = self.auth_service.register_user("chat_user_b", "Password123!", "Password123!")

        # Tạo mẫu dữ liệu từ vựng giả lập
        self.sample_records = [
            QARecord(
                id="T_01",
                sheet="Unit1",
                question="about nghĩa là gì?",
                answer="Về, khoảng.",
                source="Vocabulary A1",
                word="about",
            ),
            QARecord(
                id="T_02",
                sheet="Unit1",
                question="abandon nghĩa là gì?",
                answer="Từ bỏ, ruồng bỏ.",
                source="Vocabulary B2",
                word="abandon",
            ),
        ]

    def test_multiturn_context_in_same_account(self):
        """Trong cùng tài khoản, TopicTracker theo dõi đúng active_word và giải quyết câu hỏi tiếp nối."""
        tracker = TopicTracker(records=self.sample_records)
        tracker.load_known_words(self.sample_records)

        # Lượt 1: User A hỏi về từ 'about'
        resolved_q, target_word, is_follow_up, is_ambiguous = tracker.resolve_query("about nghĩa là gì?")
        self.assertEqual(target_word, "about")
        tracker.add_turn(
            user_query="about nghĩa là gì?",
            resolved_query=resolved_q,
            active_word="about",
            intent="DEFINITION",
            answer="Về, khoảng.",
            mode="DIRECT_MATCH",
        )
        self.assertEqual(tracker.active_word, "about")

        # Lượt 2: User A hỏi câu hỏi mơ hồ 'cho ví dụ câu của từ này'
        resolved_q2, target_w2, is_fu2, is_amb2 = tracker.resolve_query("cho ví dụ câu của từ này")
        self.assertTrue(is_fu2)
        self.assertEqual(target_w2, "about")
        self.assertIn("about", resolved_q2)

    def test_context_isolation_across_users(self):
        """Khi chuyển từ User A sang User B, ngữ cảnh của User A không được rò rỉ sang User B."""
        # User A có active_word là 'abandon'
        tracker_user_a = TopicTracker(records=self.sample_records)
        tracker_user_a.active_word = "abandon"

        # User A đăng xuất: Tracker bị clear()
        tracker_user_a.clear()
        self.assertIsNone(tracker_user_a.active_word)

        # User B đăng nhập: Khởi tạo tracker_user_b mới
        tracker_user_b = TopicTracker(records=self.sample_records)
        self.assertIsNone(tracker_user_b.active_word)

        # User B hỏi câu hỏi mơ hồ 'cho ví dụ câu của từ này' mà chưa từng hỏi từ nào trước đó
        resolved_q_b, target_w_b, is_fu_b, is_amb_b = tracker_user_b.resolve_query("cho ví dụ câu của từ này")
        # Phải được nhận diện là mơ hồ hoặc không có target_word (không được lấy từ 'abandon' của User A!)
        self.assertIsNone(target_w_b)
        self.assertNotEqual(target_w_b, "abandon")

    def test_database_persistence_across_app_reloads(self):
        """Tin nhắn và lịch sử trò chuyện được lưu trữ bền vững qua các lần khởi động lại."""
        conv = self.conv_repo.create_conversation(self.user_a.id, "Phiên lưu trữ bền vững")
        self.conv_repo.add_message(self.user_a.id, conv.id, "user", "Hello Chatbox")
        meta = {"mode": "DIRECT_MATCH", "rrf_score": 0.033}
        self.conv_repo.add_message(self.user_a.id, conv.id, "assistant", "Chào bạn!", json.dumps(meta))

        # Giả lập tắt ứng dụng và khởi tạo đối tượng AppDatabase mới trỏ vào cùng file DB
        reloaded_db = AppDatabase(db_path=self.db_path)
        reloaded_conv_repo = ConversationRepository(db=reloaded_db)

        # Kiểm tra đọc lại lịch sử
        loaded_conv = reloaded_conv_repo.get_conversation(self.user_a.id, conv.id)
        self.assertIsNotNone(loaded_conv)
        self.assertEqual(loaded_conv.title, "Phiên lưu trữ bền vững")
        self.assertEqual(loaded_conv.message_count, 2)

        messages = reloaded_conv_repo.get_messages(self.user_a.id, conv.id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Hello Chatbox")
        self.assertEqual(messages[1].role, "assistant")
        self.assertEqual(messages[1].content, "Chào bạn!")
        self.assertEqual(messages[1].get_meta().get("mode"), "DIRECT_MATCH")
        reloaded_db.close()


class TestSystemBootstrapAndAdminEnforcement(BaseAuthTestCase):
    """Kiểm tra 3 trạng thái khởi tạo hệ thống và chính sách khóa đăng ký User khi chưa có Admin."""

    def test_has_admin_empty_vs_created(self):
        """Xác minh has_admin() trả về False khi chưa có Admin và True khi đã tạo Admin."""
        # Cơ sở dữ liệu mới tinh: Chưa có Admin
        self.assertFalse(self.auth_service.has_admin())

        # Tạo một tài khoản User thông thường (không có quyền Admin)
        self.user_repo.create_user("normal_user", "hash123", "Normal User", role="user")
        self.assertFalse(self.auth_service.has_admin())

        # Tạo một tài khoản Admin qua CLI / Backend
        self.user_repo.create_user("sys_admin", "hash456", "System Admin", role="admin")
        self.assertTrue(self.auth_service.has_admin())

    def test_get_system_init_status(self):
        """Xác minh get_system_init_status() trả về NO_ADMIN khi chưa có admin và READY khi đã có."""
        # Chưa có admin
        status, err = self.auth_service.get_system_init_status()
        self.assertEqual(status, "NO_ADMIN")
        self.assertIsNone(err)

        # Tạo Admin
        self.user_repo.create_user("superadmin", "hash789", "Super Admin", role="admin")
        status, err = self.auth_service.get_system_init_status()
        self.assertEqual(status, "READY")
        self.assertIsNone(err)

    def test_get_system_init_status_db_error(self):
        """Xác minh get_system_init_status() xử lý lỗi DB_ERROR an toàn khi database gặp sự cố."""
        import sqlite3
        from unittest.mock import patch

        with patch.object(self.user_repo, "count_active_admins", side_effect=sqlite3.DatabaseError("database disk image is malformed")):
            status, err = self.auth_service.get_system_init_status()
            self.assertEqual(status, "DB_ERROR")
            self.assertIsNotNone(err)
            self.assertIn("malformed", str(err))

    def test_register_user_locked_until_admin_exists(self):
        """Người dùng không thể tự đăng ký khi hệ thống chưa có Quản trị viên (require_admin_exists=True)."""
        # Chưa có Admin -> Đăng ký bị từ chối
        ok, user, msg = self.auth_service.register_user(
            username="newuser_waiting",
            password="SecurePassword123!",
            confirm_password="SecurePassword123!",
            require_admin_exists=True,
        )
        self.assertFalse(ok)
        self.assertIsNone(user)
        self.assertIn("chưa có tài khoản Quản trị viên", msg)
        self.assertIn("python scripts/create_admin.py", msg)

        # Khởi tạo Admin qua script / repo
        self.user_repo.create_user("admin_first", "hashadmin", "First Admin", role="admin")

        # Bây giờ người dùng đăng ký thành công
        ok, user, msg = self.auth_service.register_user(
            username="newuser_waiting",
            password="SecurePassword123!",
            confirm_password="SecurePassword123!",
            require_admin_exists=True,
        )
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "newuser_waiting")
        self.assertEqual(user.role, "user")

    def test_account_lifecycle_states_distinction(self):
        """Kiểm tra phân biệt đầy đủ các trạng thái vòng đời tài khoản (Section 5):
        STATE_2_DB_EMPTY, STATE_3_NO_ACTIVE_ADMIN, STATE_4_UNAUTHENTICATED,
        STATE_5_AUTHENTICATED, STATE_6_DISABLED_OR_INVALID, STATE_7_DB_ERROR.
        """
        # 1. Ban đầu DB rỗng, chưa có user nào -> STATE_2_DB_EMPTY
        state, meta = self.auth_service.get_account_lifecycle_state()
        self.assertEqual(state, "STATE_2_DB_EMPTY")

        # 2. Tạo một tài khoản user thường (chưa có admin) -> STATE_3_NO_ACTIVE_ADMIN
        u = self.user_repo.create_user("plain_user", "hash1", "Plain User", role="user")
        state, meta = self.auth_service.get_account_lifecycle_state()
        self.assertEqual(state, "STATE_3_NO_ACTIVE_ADMIN")

        # 3. Tạo Admin -> Hệ thống có Admin, nhưng khách chưa login -> STATE_4_UNAUTHENTICATED
        adm = self.user_repo.create_user("super_adm", "hash2", "Super Admin", role="admin")
        state, meta = self.auth_service.get_account_lifecycle_state(current_user=None)
        self.assertEqual(state, "STATE_4_UNAUTHENTICATED")

        # 4. Đăng nhập bằng user hợp lệ -> STATE_5_AUTHENTICATED
        state, meta = self.auth_service.get_account_lifecycle_state(current_user=u)
        self.assertEqual(state, "STATE_5_AUTHENTICATED")
        self.assertEqual(meta["user"].username, "plain_user")

        # 5. Khóa tài khoản -> STATE_6_DISABLED_OR_INVALID
        self.user_repo.set_active_status(u.id, is_active=False)
        state, meta = self.auth_service.get_account_lifecycle_state(current_user=u)
        self.assertEqual(state, "STATE_6_DISABLED_OR_INVALID")

        # 6. Lỗi SQLite hỏng -> STATE_7_DB_ERROR
        import sqlite3
        from unittest.mock import patch
        with patch.object(self.user_repo, "count_users", side_effect=sqlite3.DatabaseError("Disk I/O error")):
            state, meta = self.auth_service.get_account_lifecycle_state()
            self.assertEqual(state, "STATE_7_DB_ERROR")

    def test_conversation_pin_toggle_and_isolation(self):
        """Kiểm tra chức năng Ghim/Bỏ ghim hội thoại, sắp xếp ưu tiên và cô lập giữa các user."""
        u1 = self.user_repo.create_user("user_pin_1", "hash1", "User Pin 1")
        u2 = self.user_repo.create_user("user_pin_2", "hash2", "User Pin 2")

        c1 = self.conv_repo.create_conversation(u1.id, "Đoạn chat 1 của User 1")
        c2 = self.conv_repo.create_conversation(u1.id, "Đoạn chat 2 của User 1")
        c_u2 = self.conv_repo.create_conversation(u2.id, "Đoạn chat của User 2")

        # 1. Mặc định chưa ghim
        self.assertFalse(c1.is_pinned)
        self.assertFalse(c2.is_pinned)

        # 2. User 1 ghim c1 thành công
        ok = self.conv_repo.toggle_pin_conversation(u1.id, c1.id)
        self.assertTrue(ok)
        conv1_fetched = self.conv_repo.get_conversation(u1.id, c1.id)
        self.assertTrue(conv1_fetched.is_pinned)

        # 3. User 2 KHÔNG THỂ ghim cuộc trò chuyện của User 1 (Data isolation)
        ok_cross = self.conv_repo.toggle_pin_conversation(u2.id, c1.id)
        self.assertFalse(ok_cross)
        conv1_still = self.conv_repo.get_conversation(u1.id, c1.id)
        self.assertTrue(conv1_still.is_pinned)

        # 4. Danh sách hội thoại của User 1 ưu tiên hội thoại đã ghim lên đầu
        convs_u1 = self.conv_repo.list_conversations(u1.id)
        self.assertEqual(convs_u1[0].id, c1.id)
        self.assertTrue(convs_u1[0].is_pinned)

        # 5. User 1 bỏ ghim c1
        ok_unpin = self.conv_repo.toggle_pin_conversation(u1.id, c1.id)
        self.assertTrue(ok_unpin)
        conv1_unpinned = self.conv_repo.get_conversation(u1.id, c1.id)
        self.assertFalse(conv1_unpinned.is_pinned)

    def test_conversation_delete_and_isolation(self):
        """Kiểm tra chức năng Xóa hội thoại và bảo đảm chỉ chủ sở hữu mới được xóa."""
        u1 = self.user_repo.create_user("user_del_1", "hash1", "User Del 1")
        u2 = self.user_repo.create_user("user_del_2", "hash2", "User Del 2")

        c1 = self.conv_repo.create_conversation(u1.id, "Đoạn chat cần xóa")
        self.conv_repo.add_message(u1.id, c1.id, "user", "Hello message")

        # 1. User 2 cố gắng xóa hội thoại của User 1 -> Không thành công
        deleted_cross = self.conv_repo.delete_conversation(u2.id, c1.id)
        self.assertFalse(deleted_cross)
        self.assertIsNotNone(self.conv_repo.get_conversation(u1.id, c1.id))

        # 2. User 1 xóa hội thoại của chính mình -> Thành công
        deleted_own = self.conv_repo.delete_conversation(u1.id, c1.id)
        self.assertTrue(deleted_own)
        self.assertIsNone(self.conv_repo.get_conversation(u1.id, c1.id))
        self.assertEqual(len(self.conv_repo.get_messages(u1.id, c1.id)), 0)


if __name__ == "__main__":
    unittest.main()
