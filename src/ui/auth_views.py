"""Giao diện xác thực: Đăng nhập và Đăng ký người dùng (Authentication UI).

Tuân thủ quy chuẩn thiết kế Soft Slate của Chatbox 2.0.
Đảm bảo kiểm tra thông tin ở backend và không tiết lộ cấu trúc nhạy cảm.
"""

from typing import Optional

import streamlit as st

from src.auth.service import AuthService
from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User


def render_auth_page(
    auth_service: AuthService,
    conv_repo: ConversationRepository,
) -> Optional[User]:
    """Hiển thị màn hình đăng nhập và đăng ký khi người dùng chưa xác thực."""
    # Hiển thị tiêu đề chính
    st.markdown(
        """
        <div style="text-align: center; margin-top: 1.5rem; margin-bottom: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🤖</div>
            <h1 style="font-size: 1.85rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem;">
                Chatbox 2.0
            </h1>
            <p style="color: #64748B; font-size: 0.95rem;">
                Hệ thống tra cứu từ vựng tiếng Anh thông minh với AI cục bộ
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_spacer_l, col_auth, col_spacer_r = st.columns([1, 2, 1])

    with col_auth:
        tab_login, tab_register = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký tài khoản"])

        # ----------------------------------------------------------------------
        # TAB 1: ĐĂNG NHẬP
        # ----------------------------------------------------------------------
        with tab_login:
            st.markdown("##### Đăng nhập vào hệ thống")
            st.caption("Nhập tên đăng nhập và mật khẩu để tiếp tục.")

            with st.form("form_login", clear_on_submit=False):
                username_input = st.text_input(
                    "Tên đăng nhập",
                    placeholder="ví dụ: nguyenvana",
                    key="login_username",
                ).strip()
                password_input = st.text_input(
                    "Mật khẩu",
                    type="password",
                    placeholder="••••••••",
                    key="login_password",
                )
                submitted_login = st.form_submit_button(
                    "Đăng nhập",
                    use_container_width=True,
                    type="primary",
                )

            if submitted_login:
                if not username_input or not password_input:
                    st.warning("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
                else:
                    success, user, msg = auth_service.authenticate(username_input, password_input)
                    if success and user:
                        # Lưu user vào session state
                        st.session_state.auth_user = user
                        # Xóa mọi ngữ cảnh cũ và tin nhắn còn sót lại
                        st.session_state.messages = []
                        st.session_state.current_conversation_id = None
                        st.session_state.status = "Sẵn sàng!"
                        st.toast(f"Xin chào, {user.display_name}!", icon="👋")
                        st.rerun()
                    else:
                        st.error(msg)

        # ----------------------------------------------------------------------
        # TAB 2: ĐĂNG KÝ USER
        # ----------------------------------------------------------------------
        with tab_register:
            st.markdown("##### Tạo tài khoản mới")
            st.caption("Tài khoản tự đăng ký mặc định có vai trò Người dùng (User).")

            with st.form("form_register", clear_on_submit=False):
                reg_username = st.text_input(
                    "Tên đăng nhập *",
                    placeholder="3-30 ký tự (chữ cái, số, gạch dưới)",
                    key="reg_username",
                ).strip()
                reg_display_name = st.text_input(
                    "Tên hiển thị (Tùy chọn)",
                    placeholder="ví dụ: Nguyễn Văn A",
                    key="reg_display_name",
                ).strip()
                reg_password = st.text_input(
                    "Mật khẩu *",
                    type="password",
                    placeholder="Tối thiểu 6 ký tự",
                    key="reg_password",
                )
                reg_confirm_password = st.text_input(
                    "Xác nhận mật khẩu *",
                    type="password",
                    placeholder="Nhập lại mật khẩu",
                    key="reg_confirm_password",
                )
                submitted_register = st.form_submit_button(
                    "Đăng ký ngay",
                    use_container_width=True,
                )

            if submitted_register:
                success, new_user, msg = auth_service.register_user(
                    username=reg_username,
                    password=reg_password,
                    confirm_password=reg_confirm_password,
                    display_name=reg_display_name,
                )
                if success:
                    st.success(f"✅ {msg}")
                    st.info("👉 Bạn có thể chuyển sang tab **'Đăng nhập'** bên cạnh để bắt đầu tra cứu.")
                else:
                    st.error(f"❌ {msg}")

    return None
