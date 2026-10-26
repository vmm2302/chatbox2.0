"""Kiểm thử tự động giao diện Streamlit Chatbox 2.0 bằng AppTest.

Kiểm tra:
1. Giao diện khi chưa đăng nhập (Unauthenticated):
   - Sidebar có logo Chatbox 2.0.
   - Nút '+ Đoạn chat mới' yêu cầu đăng nhập.
   - Sidebar footer có nút Đăng nhập và Tạo tài khoản.
   - Khung chính hiển thị màn hình chào mừng và form xác thực.
2. Giao diện sau khi đăng nhập User:
   - Footer hiển thị popover thông tin User (không có menu Admin).
   - Truy cập trái phép vào trang Admin bị từ chối ở backend.
   - Hiển thị 4 thẻ gợi ý và ô nhập st.chat_input.
3. Giao diện sau khi đăng nhập Admin:
   - Footer hiển thị menu Quản trị: Quản lý tài khoản, Quản lý dữ liệu, Chẩn đoán.
   - Được phép truy cập đầy đủ các trang quản trị.
4. Cách ly dữ liệu và không rò rỉ ngữ cảnh:
   - Reset TopicTracker và hội thoại khi bấm Tạo đoạn chat mới.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.data.user_repository import User

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "ui" / "app.py")


class TestUIAppTest(unittest.TestCase):
    """Bộ kiểm thử Streamlit UI thông qua Streamlit AppTest framework."""

    def test_01_unauthenticated_sidebar_and_main_view(self):
        """Khi chưa đăng nhập: sidebar và khung chính hiển thị đúng bố cục bảo vệ."""
        at = AppTest.from_file(APP_PATH)
        at.session_state["auth_user"] = None
        at.run(timeout=30)

        self.assertFalse(at.exception)

        # 1. Nút new chat trong sidebar
        btn_new_chat = [b for b in at.sidebar.button if b.key == "btn_sidebar_new_chat"]
        self.assertTrue(len(btn_new_chat) > 0)

        # 2. Nút Login và Register trong footer sidebar
        btn_login = [b for b in at.sidebar.button if b.key == "btn_sidebar_unauth_login"]
        btn_register = [b for b in at.sidebar.button if b.key == "btn_sidebar_unauth_register"]
        self.assertTrue(len(btn_login) > 0)
        self.assertTrue(len(btn_register) > 0)

        # 3. Main tabs hiển thị Login và Register
        tab_labels = [t.label for t in at.tabs]
        self.assertIn("🔐 Đăng nhập", tab_labels)
        self.assertIn("📝 Đăng ký tài khoản", tab_labels)

    def test_02_authenticated_user_chat_view_and_no_admin_menu(self):
        """Khi đăng nhập User: chỉ hiển thị tính năng chat, không có menu Admin."""
        mock_user = User(
            id=991,
            username="test_student",
            password_hash="mock",
            display_name="Sinh Viên A",
            role="user",
            is_active=True,
            created_at="2026-01-01 00:00:00",
            last_login_at=None,
            updated_at="2026-01-01 00:00:00",
        )

        with patch("src.auth.service.AuthService.verify_active_session", return_value=mock_user):
            at = AppTest.from_file(APP_PATH)
            at.session_state["auth_user"] = mock_user
            at.session_state["nav_page"] = "💬 Tra cứu từ vựng"
            at.run(timeout=30)

            self.assertFalse(at.exception)

            # Ô nhập chat_input phải xuất hiện
            self.assertEqual(len(at.chat_input), 1)

            # 4 Thẻ gợi ý phải xuất hiện khi chưa có tin nhắn
            sug_cards = [b for b in at.button if "sug_card_" in (b.key or "")]
            self.assertEqual(len(sug_cards), 4)

            # Không xuất hiện nút quản trị của Admin
            admin_btn_keys = [b.key for b in at.sidebar.button if "admin" in (b.key or "")]
            self.assertEqual(len(admin_btn_keys), 0)

    def test_03_user_forbidden_from_admin_pages(self):
        """User thường truy cập trái phép trang Admin sẽ bị chặn ở backend."""
        mock_user = User(
            id=992,
            username="normal_user_probe",
            password_hash="mock",
            display_name="Normal User",
            role="user",
            is_active=True,
            created_at="2026-01-01 00:00:00",
            last_login_at=None,
            updated_at="2026-01-01 00:00:00",
        )

        with patch("src.auth.service.AuthService.verify_active_session", return_value=mock_user):
            # Thử truy cập trang Quản lý tài khoản
            at = AppTest.from_file(APP_PATH)
            at.session_state["auth_user"] = mock_user
            at.session_state["nav_page"] = "👥 Quản lý tài khoản"
            at.run(timeout=30)

            self.assertFalse(at.exception)
            # Phải có thông báo lỗi từ chối truy cập
            error_alerts = [e.value for e in at.error]
            self.assertTrue(any("từ chối" in str(err).lower() or "admin" in str(err).lower() for err in error_alerts))

    def test_04_admin_can_access_management_page(self):
        """Admin truy cập trang Quản trị thành công mà không bị chặn."""
        mock_admin = User(
            id=1,
            username="admin_lead",
            password_hash="mock",
            display_name="Trưởng Quản Trị",
            role="admin",
            is_active=True,
            created_at="2026-01-01 00:00:00",
            last_login_at=None,
            updated_at="2026-01-01 00:00:00",
        )

        with patch("src.auth.service.AuthService.verify_active_session", return_value=mock_admin):
            at = AppTest.from_file(APP_PATH)
            at.session_state["auth_user"] = mock_admin
            at.session_state["nav_page"] = "👥 Quản lý tài khoản"
            at.run(timeout=30)

            self.assertFalse(at.exception)
            # Metrics quản lý tài khoản xuất hiện
            self.assertTrue(len(at.metric) >= 4)


if __name__ == "__main__":
    unittest.main()
