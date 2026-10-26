"""Bảng điều khiển Quản trị viên (Admin Dashboard & User Management).

Cung cấp các công cụ quản lý tài khoản, theo dõi số liệu và giám sát hệ thống.
Mọi thao tác thay đổi trạng thái, vai trò hoặc mật khẩu đều được xác minh quyền ở backend.
"""

from typing import Any, Dict, List

import streamlit as st

from src.auth.service import AuthService
from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User


def render_admin_dashboard(
    auth_service: AuthService,
    conv_repo: ConversationRepository,
    current_user: User,
) -> None:
    """Hiển thị Dashboard quản trị dành riêng cho Admin."""
    # Kiểm tra bảo vệ quyền backend
    try:
        auth_service.require_admin(current_user)
    except PermissionError as perm_err:
        st.error(f"❌ Truy cập bị từ chối: {perm_err}")
        return

    st.markdown(
        """
        <div class="chat-top-bar">
            <div class="chat-top-left">
                <span class="chat-view-title">👥 Quản lý tài khoản & Người dùng</span>
                <span class="role-badge-admin">Admin Dashboard</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------------------
    # 1. KHU VỰC TỔNG QUAN (OVERVIEW METRICS)
    # --------------------------------------------------------------------------
    stats = auth_service.user_repo.count_users()
    total_convs = conv_repo.count_all_conversations()

    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        with st.container(border=True):
            st.metric("Tổng tài khoản", f"{stats['total']:,}")
    with col_s2:
        with st.container(border=True):
            st.metric("User hoạt động", f"{stats['total_users']:,}")
    with col_s3:
        with st.container(border=True):
            st.metric("Quản trị viên (Admin)", f"{stats['active_admins']:,}")
    with col_s4:
        with st.container(border=True):
            st.metric("Tài khoản bị khóa", f"{stats['disabled_count']:,}")
    with col_s5:
        with st.container(border=True):
            st.metric("Tổng cuộc hội thoại", f"{total_convs:,}")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 2. BỘ LỌC VÀ TÌM KIẾM TÀI KHOẢN
    # --------------------------------------------------------------------------
    st.markdown("#### 🔍 Danh Sách Tài Khoản Hệ Thống")

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_kw = st.text_input(
            "Tìm kiếm theo username hoặc tên hiển thị",
            placeholder="Nhập từ khóa...",
            key="admin_search_kw",
        ).strip()
    with col_f2:
        role_filter_label = st.selectbox(
            "Lọc vai trò",
            options=["Tất cả", "user", "admin"],
            key="admin_filter_role",
        )
    with col_f3:
        status_filter_label = st.selectbox(
            "Lọc trạng thái",
            options=["Tất cả", "Hoạt động", "Đã vô hiệu hóa"],
            key="admin_filter_status",
        )

    role_val = None if role_filter_label == "Tất cả" else role_filter_label
    is_active_val = None
    if status_filter_label == "Hoạt động":
        is_active_val = True
    elif status_filter_label == "Đã vô hiệu hóa":
        is_active_val = False

    users_list = auth_service.user_repo.list_users(
        search=search_kw if search_kw else None,
        role=role_val,
        is_active=is_active_val,
        limit=100,
    )

    if users_list:
        table_data = []
        for u in users_list:
            table_data.append({
                "ID": u.id,
                "Tên đăng nhập": u.username,
                "Tên hiển thị": u.display_name,
                "Vai trò": u.role.upper(),
                "Trạng thái": "🟢 Hoạt động" if u.is_active else "🔴 Đã khóa",
                "Ngày tạo (UTC)": u.created_at[:19].replace("T", " ") if u.created_at else "N/A",
                "Đăng nhập gần nhất (UTC)": u.last_login_at[:19].replace("T", " ") if u.last_login_at else "Chưa từng",
            })
        st.dataframe(table_data, use_container_width=True)
    else:
        st.info("Không tìm thấy tài khoản nào phù hợp với điều kiện tìm kiếm.")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 3. THAO TÁC QUẢN TRỊ TÀI KHOẢN (ACTION PANELS)
    # --------------------------------------------------------------------------
    col_act1, col_act2 = st.columns([1, 1])

    with col_act1:
        st.markdown("#### ⚡ Thao Tác Nhanh Cho Tài Khoản")
        if not users_list:
            st.caption("Không có tài khoản nào được chọn.")
        else:
            user_options = {f"{u.id} - {u.username} ({u.display_name})": u for u in users_list}
            selected_user_label = st.selectbox(
                "Chọn tài khoản cần thao tác:",
                options=list(user_options.keys()),
                key="admin_selected_user_box",
            )
            target_user = user_options[selected_user_label]

            # Hiển thị thông tin tóm tắt
            st.caption(
                f"Tài khoản: **{target_user.username}** | Vai trò: `{target_user.role}` | "
                f"Trạng thái: {'Hoạt động' if target_user.is_active else 'Đã khóa'}"
            )

            # Tab các thao tác
            tab_status, tab_role, tab_reset, tab_delete = st.tabs([
                "Trạng thái", "Vai trò", "Đặt lại mật khẩu", "Xóa tài khoản"
            ])

            with tab_status:
                st.markdown("##### Kích hoạt / Vô hiệu hóa tài khoản")
                new_status = not target_user.is_active
                status_btn_text = "🟢 Kích hoạt lại tài khoản" if not target_user.is_active else "🔴 Vô hiệu hóa tài khoản"
                if st.button(status_btn_text, key="btn_toggle_active_user", use_container_width=True):
                    ok, msg = auth_service.admin_toggle_active(current_user, target_user.id, new_status)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            with tab_role:
                st.markdown("##### Thay đổi vai trò người dùng")
                new_role_choice = st.selectbox(
                    "Chọn vai trò mới:",
                    options=["user", "admin"],
                    index=0 if target_user.role == "user" else 1,
                    key="admin_role_change_choice",
                )
                if st.button("Lưu thay đổi vai trò", key="btn_save_role_change", use_container_width=True):
                    ok, msg = auth_service.admin_change_role(current_user, target_user.id, new_role_choice)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            with tab_reset:
                st.markdown("##### Đặt lại mật khẩu mới cho người dùng")
                new_pw_input = st.text_input(
                    "Mật khẩu mới:",
                    type="password",
                    placeholder="Tối thiểu 6 ký tự",
                    key="admin_reset_pw_input",
                )
                if st.button("Xác nhận đặt lại mật khẩu", key="btn_confirm_reset_pw", use_container_width=True):
                    if not new_pw_input:
                        st.warning("Vui lòng nhập mật khẩu mới.")
                    else:
                        ok, msg = auth_service.admin_reset_password(current_user, target_user.id, new_pw_input)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

            with tab_delete:
                st.markdown("##### Xóa tài khoản vĩnh viễn")
                st.warning("⚠️ Thao tác này sẽ xóa vĩnh viễn tài khoản và toàn bộ lịch sử trò chuyện!")
                confirm_delete = st.checkbox(
                    f"Tôi xác nhận muốn xóa vĩnh viễn tài khoản '{target_user.username}'",
                    key="cb_confirm_delete_user",
                )
                if st.button(
                    "🗑️ Xóa vĩnh viễn tài khoản",
                    type="primary",
                    disabled=not confirm_delete,
                    key="btn_execute_delete_user",
                    use_container_width=True,
                ):
                    ok, msg = auth_service.admin_delete_user(current_user, target_user.id)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with col_act2:
        st.markdown("#### ➕ Tạo Tài Khoản Mới (Bởi Admin)")
        st.caption("Quản trị viên có thể tạo trực tiếp tài khoản User hoặc Admin mới.")

        with st.form("form_admin_create_user", clear_on_submit=True):
            new_u_name = st.text_input(
                "Tên đăng nhập *",
                placeholder="ví dụ: tranvanb",
                key="admin_new_u_name",
            ).strip()
            new_u_disp = st.text_input(
                "Tên hiển thị",
                placeholder="ví dụ: Trần Văn B",
                key="admin_new_u_disp",
            ).strip()
            new_u_pass = st.text_input(
                "Mật khẩu *",
                type="password",
                placeholder="Tối thiểu 6 ký tự",
                key="admin_new_u_pass",
            )
            new_u_role = st.selectbox(
                "Vai trò tài khoản *",
                options=["user", "admin"],
                index=0,
                key="admin_new_u_role",
            )
            submitted_create = st.form_submit_button(
                "Tạo tài khoản",
                type="primary",
                use_container_width=True,
            )

        if submitted_create:
            ok, user_created, msg = auth_service.admin_create_user(
                actor=current_user,
                username=new_u_name,
                password=new_u_pass,
                display_name=new_u_disp,
                role=new_u_role,
            )
            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")
