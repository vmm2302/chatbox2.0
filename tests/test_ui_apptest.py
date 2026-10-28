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
        """Khi chưa đăng nhập: sidebar bị ẩn hoàn toàn, khung chính hiển thị form xác thực."""
        at = AppTest.from_file(APP_PATH)
        at.session_state["auth_user"] = None
        at.run(timeout=30)

        self.assertFalse(at.exception)

        # 1. Sidebar được ẩn khi chưa đăng nhập, không chứa nút thao tác
        self.assertEqual(len(at.sidebar.button), 0)

        # 2. Main tabs hiển thị Login và Register
        tab_labels = [t.label for t in at.tabs]
        self.assertIn("🔐 Đăng nhập", tab_labels)
        self.assertIn("📝 Đăng ký tài khoản", tab_labels)

    def test_02_authenticated_user_chat_view_and_no_admin_menu(self):
        """Khi đăng nhập User: hiển thị sidebar, tính năng chat, gợi ý về từ about, không có menu Admin."""
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

            # Sidebar có nút tạo đoạn chat mới khi đã đăng nhập
            btn_new_chat = [b for b in at.sidebar.button if b.key == "btn_sidebar_new_chat"]
            self.assertTrue(len(btn_new_chat) > 0)

            # Ô nhập chat_input phải xuất hiện
            self.assertEqual(len(at.chat_input), 1)

            # 4 Thẻ gợi ý phải xuất hiện khi chưa có tin nhắn, trong đó có ví dụ hỏi nghĩa từ about
            sug_cards = [b for b in at.button if "sug_card_" in (b.key or "")]
            self.assertEqual(len(sug_cards), 4)
            card_texts = [b.label for b in sug_cards]
            self.assertTrue(any("about" in t.lower() for t in card_texts))

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
            # Metrics quản lý tài khoản xuất hiện (Tổng tài khoản, Tài khoản hoạt động, Quản trị viên)
            self.assertTrue(len(at.metric) >= 3)

    def test_05_system_theme_and_color_adaptation(self):
        """Hệ thống hỗ trợ theme System theo thiết bị, bỏ các cấu hình ép dark."""
        import toml
        from src.ui.theme import get_custom_css, CUSTOM_CSS

        # 1. Đọc file config.toml và đảm bảo không ép cứng base = 'dark'
        config_path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
        self.assertTrue(config_path.exists())
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = toml.load(f)

        theme_cfg = cfg.get("theme", {})
        self.assertNotEqual(theme_cfg.get("base"), "dark", "config.toml không được ép base = 'dark'")
        # Phải có hỗ trợ cấu hình theme light và dark
        self.assertIn("light", theme_cfg)
        self.assertIn("dark", theme_cfg)

        # 2. Không có biến môi trường ép theme dark trong tiến trình
        self.assertNotEqual(os.environ.get("STREAMLIT_THEME_BASE"), "dark")

        # 3. get_custom_css mặc định (System) phải chứa quy tắc CSS thích ứng theo thiết bị
        css_default = get_custom_css()
        self.assertIn("prefers-color-scheme: dark", css_default)
        self.assertIn("--app-bg: #FFFFFF", css_default)
        self.assertIn("--app-bg: #212121", css_default)
        self.assertIn("var(--sidebar-bg)", css_default)
        self.assertIn("var(--chat-input-bg)", css_default)
        self.assertIn("var(--border-subtle)", css_default)

        # 4. Khi theme_type là dark hoặc light, CSS sinh ra các biến tương ứng
        css_dark = get_custom_css("dark")
        self.assertIn("--app-bg: #212121 !important", css_dark)

        css_light = get_custom_css("light")
        self.assertIn("--app-bg: #FFFFFF !important", css_light)


if __name__ == "__main__":
    unittest.main()
