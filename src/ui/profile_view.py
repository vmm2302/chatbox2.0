"""Giao diện hồ sơ cá nhân và đổi mật khẩu (Profile & Account Settings).

Cho phép người dùng xem thông tin tài khoản, cập nhật tên hiển thị và đổi mật khẩu.
"""

import streamlit as st

from src.auth.service import AuthService
from src.data.user_repository import User


def render_profile_view(
    auth_service: AuthService,
    current_user: User,
) -> None:
    """Hiển thị trang quản lý thông tin cá nhân của tài khoản đang đăng nhập."""
    # Lấy thông tin mới nhất từ cơ sở dữ liệu
    fresh_user = auth_service.user_repo.get_by_id(current_user.id)
    if not fresh_user or not fresh_user.is_active:
        st.error("Tài khoản của bạn đã bị vô hiệu hóa hoặc không tồn tại.")
        return

    st.markdown(
        """
        <div class="chat-top-bar">
            <div class="chat-top-left">
                <span class="chat-view-title">👤 Thông tin cá nhân & Tài khoản</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        with st.container(border=True):
            st.markdown("#### 📋 Thông Tin Tài Khoản")
            st.markdown(f"- **Tên đăng nhập:** `{fresh_user.username}`")
            st.markdown(f"- **Tên hiển thị:** {fresh_user.display_name}")
            role_badge_html = '<span class="role-badge-admin">👑 Quản trị viên (Admin)</span>' if fresh_user.role == "admin" else '<span class="role-badge-user">👤 Người dùng (User)</span>'
            st.markdown(f"- **Vai trò:** {role_badge_html}", unsafe_allow_html=True)
            status_badge = "🟢 Đang hoạt động" if fresh_user.is_active else "🔴 Đã khóa"
            st.markdown(f"- **Trạng thái:** {status_badge}")
            created_str = fresh_user.created_at[:19].replace("T", " ") if fresh_user.created_at else "N/A"
            st.markdown(f"- **Ngày tạo tài khoản (UTC):** {created_str}")
            login_str = fresh_user.last_login_at[:19].replace("T", " ") if fresh_user.last_login_at else "Chưa ghi nhận"
            st.markdown(f"- **Đăng nhập gần nhất (UTC):** {login_str}")

            st.markdown("---")
            st.markdown("##### ✏️ Đổi Tên Hiển Thị")
            with st.form("form_update_profile"):
                new_display_name = st.text_input(
                    "Tên hiển thị mới:",
                    value=fresh_user.display_name,
                    key="input_new_display_name",
                ).strip()
                submitted_name = st.form_submit_button("Lưu tên hiển thị")

            if submitted_name:
                if not new_display_name:
                    st.warning("Tên hiển thị không được để trống.")
                else:
                    ok, msg = auth_service.user_update_profile(fresh_user, new_display_name)
                    if ok:
                        st.session_state.auth_user.display_name = new_display_name
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    with col_p2:
        with st.container(border=True):
            st.markdown("#### 🔒 Đổi Mật Khẩu")
            st.caption("Để bảo vệ tài khoản, vui lòng sử dụng mật khẩu mạnh tối thiểu 6 ký tự.")

            with st.form("form_change_password", clear_on_submit=True):
                old_pw = st.text_input(
                    "Mật khẩu hiện tại *",
                    type="password",
                    placeholder="••••••••",
                    key="input_old_password",
                )
                new_pw = st.text_input(
                    "Mật khẩu mới *",
                    type="password",
                    placeholder="Tối thiểu 6 ký tự",
                    key="input_new_password",
                )
                confirm_pw = st.text_input(
                    "Xác nhận mật khẩu mới *",
                    type="password",
                    placeholder="Nhập lại mật khẩu mới",
                    key="input_confirm_password",
                )
                submitted_pw = st.form_submit_button("Đổi mật khẩu", type="primary")

            if submitted_pw:
                if not old_pw or not new_pw or not confirm_pw:
                    st.warning("Vui lòng điền đầy đủ các trường thông tin.")
                else:
                    ok, msg = auth_service.user_change_password(
                        actor=fresh_user,
                        old_password=old_pw,
                        new_password=new_pw,
                        confirm_new_password=confirm_pw,
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
