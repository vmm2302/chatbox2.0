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

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        with st.container(border=True):
            st.metric("Tổng tài khoản", f"{stats['total']:,}")
    with col_s2:
        with st.container(border=True):
            st.metric("User hoạt động", f"{stats['total_users']:,}")
    with col_s3:
        with st.container(border=True):
            st.metric("Quản trị viên (Admin)", f"{stats['active_admins']:,}")

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
