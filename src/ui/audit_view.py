"""Giao diện xem nhật ký kiểm toán hệ thống (Admin Audit Logs UI).

Hiển thị các thao tác quản trị, bảo mật và thay đổi cấu hình hệ thống.
"""

import json
from typing import Optional

import streamlit as st

from src.data.audit_repository import AuditRepository
from src.data.user_repository import User


def render_admin_audit_logs(
    audit_repo: AuditRepository,
    current_user: User,
) -> None:
    """Hiển thị bảng nhật ký kiểm toán quản trị hệ thống."""
    st.markdown("#### 📜 Nhật Ký Thao Tác Quản Trị Hệ Thống (Audit Logs)")
    st.caption("Ghi lại đầy đủ các hoạt động quản trị tài khoản, thay đổi quyền và nạp dữ liệu.")

    col_l1, col_l2 = st.columns([2, 1])
    with col_l1:
        search_log = st.text_input(
            "Tìm kiếm nhật ký (tên người dùng, đối tượng, chi tiết):",
            placeholder="Nhập từ khóa tìm kiếm...",
            key="audit_log_search",
        ).strip()
    with col_l2:
        action_filter = st.selectbox(
            "Lọc theo loại thao tác:",
            options=[
                "Tất cả",
                "USER_REGISTER",
                "USER_LOGIN",
                "USER_LOGOUT",
                "BOOTSTRAP_ADMIN",
                "ADMIN_CREATE_USER",
                "ADMIN_DISABLE_USER",
                "ADMIN_ENABLE_USER",
                "ADMIN_RESET_PASSWORD",
                "ADMIN_CHANGE_ROLE",
                "ADMIN_DELETE_USER",
                "CLEAR_KB",
                "BATCH_INGEST_KB",
            ],
            key="audit_log_action_filter",
        )

    action_val = None if action_filter == "Tất cả" else action_filter
    search_val = search_log if search_log else None

    total_logs = audit_repo.count_logs(action=action_val, search=search_val)
    logs = audit_repo.list_logs(limit=100, offset=0, action=action_val, search=search_val)

    st.markdown(f"**Tổng số bản ghi:** {total_logs:,} (hiển thị tối đa 100 bản ghi mới nhất)")

    if logs:
        log_rows = []
        for lg in logs:
            log_rows.append({
                "ID": lg.id,
                "Thời gian (UTC)": lg.created_at[:19].replace("T", " "),
                "Người thực hiện": lg.actor_username,
                "Hành động": lg.action,
                "Đối tượng": f"{lg.target_type} ({lg.target_id or '-'})",
                "Trạng thái": "🟢 " + lg.status if lg.status == "SUCCESS" else "🔴 " + lg.status,
                "Chi tiết": lg.details or "",
            })
        st.dataframe(log_rows, use_container_width=True)

        # Nút tải về file JSON
        logs_json_data = [lg.to_dict() for lg in logs]
        st.download_button(
            label="📥 Tải Nhật Ký Audit Quản Trị (JSON)",
            data=json.dumps(logs_json_data, ensure_ascii=False, indent=2),
            file_name="chatbox2_admin_audit_logs.json",
            mime="application/json",
            use_container_width=True,
            key="btn_download_admin_audit_logs",
        )
    else:
        st.info("Không có bản ghi nhật ký kiểm toán nào phù hợp.")
