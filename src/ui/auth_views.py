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
    """Hiển thị màn hình đăng nhập và đăng ký khi người dùng chưa xác thực.
    
    Xử lý rõ ràng 3 trạng thái:
    1. Cơ sở dữ liệu bị lỗi (DB_ERROR): cảnh báo an toàn, không xóa hay ghi đè.
    2. Chưa có tài khoản Admin nào (NO_ADMIN): hướng dẫn chạy CLI an toàn.
    3. Hệ thống đã sẵn sàng (READY): cho phép đăng nhập và đăng ký User.
    """
    # Kiểm tra trạng thái khởi tạo hệ thống và vòng đời tài khoản
    init_status, init_err = auth_service.get_system_init_status()
    lifecycle_state, lifecycle_meta = auth_service.get_account_lifecycle_state()

    # Hiển thị tiêu đề chính
    st.markdown(
        """
        <div class="auth-header-box">
            <div class="auth-header-icon">🤖</div>
            <h1 class="auth-header-title">Chatbox 2.0</h1>
            <p class="auth-header-desc">
                Hệ thống tra cứu từ vựng tiếng Anh thông minh với AI cục bộ. Đăng nhập để lưu và cá nhân hóa lịch sử trò chuyện của bạn.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_spacer_l, col_auth, col_spacer_r = st.columns([1, 2, 1])

    with col_auth:
        # Trường hợp 1: Cơ sở dữ liệu bị lỗi kết nối hoặc hỏng file
        if init_status == "DB_ERROR":
            st.error(
                f"❌ **LỖI KẾT NỐI CƠ SỞ DỮ LIỆU ỨNG DỤNG**\n\n"
                f"- Chi tiết: `{init_err}`\n\n"
                f"- Hệ thống đã tạm dừng để bảo vệ an toàn dữ liệu. Tuyệt đối không tự động xóa hoặc ghi đè database.\n"
                f"- Vui lòng kiểm tra quyền truy cập file tại `data/app_data.db` và khởi động lại."
            )
            return None

        # Trường hợp 2: Hệ thống chưa có tài khoản Admin nào (STATE_2_DB_EMPTY hoặc STATE_3_NO_ACTIVE_ADMIN)
        if init_status == "NO_ADMIN":
            if lifecycle_state == "STATE_2_DB_EMPTY":
                admin_notice_subtitle = "Cơ sở dữ liệu ứng dụng vừa khởi tạo và <b>chưa có bất kỳ tài khoản nào</b>."
            else:
                admin_notice_subtitle = "Đã có tài khoản trong hệ thống nhưng <b>chưa có Quản trị viên nào đang hoạt động</b>."

            st.markdown(
                f"""
                <div class="admin-setup-card">
                    <div class="admin-setup-title">
                        🛡️ Hệ thống chưa có Quản trị viên (Admin)
                    </div>
                    <p class="admin-setup-desc">
                        {admin_notice_subtitle} Để đảm bảo an toàn phân quyền, hệ thống yêu cầu khởi tạo tài khoản <b>Quản trị viên đầu tiên</b> qua terminal an toàn trước khi mở đăng ký người dùng:
                    </p>
                    <div class="admin-setup-code">
                        python scripts/create_admin.py
                    </div>
                    <p class="admin-setup-note">
                        Lệnh CLI sẽ bảo mật mật khẩu (không in ra màn hình) và băm bảo mật bằng thuật toán Bcrypt / Salt ngẫu nhiên.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            col_rf1, col_rf2 = st.columns([1, 1])
            with col_rf1:
                if st.button("🔄 Kiểm tra lại trạng thái", key="btn_check_admin_init", use_container_width=True):
                    st.rerun()

        # Chọn tab mặc định dựa trên session_state.auth_tab (tương thích đa phiên bản Streamlit)
        active_tab_label = "📝 Đăng ký tài khoản" if st.session_state.get("auth_tab") == "register" else "🔐 Đăng nhập"
        try:
            tab_login, tab_register = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký tài khoản"], default=active_tab_label)
        except TypeError:
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
                        # Tải trước Ollama dưới nền và làm nóng model trong lúc đăng nhập
                        try:
                            from src.resource.ollama_service import (
                                ensure_ollama_running_background,
                                preload_model_in_background,
                            )
                            ensure_ollama_running_background()
                            preload_model_in_background()
                        except Exception as ollama_bg_err:
                            pass

                        # Lưu user vào session state
                        st.session_state.auth_user = user
                        # Xóa mọi ngữ cảnh cũ và tin nhắn còn sót lại, khởi tạo tracker độc lập
                        st.session_state.messages = []
                        st.session_state.current_conversation_id = None
                        st.session_state.tracker = None
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
            if init_status == "NO_ADMIN":
                st.warning("⚠️ Chức năng đăng ký tài khoản User đang tạm khóa cho đến khi Quản trị viên (Admin) đầu tiên được tạo qua lệnh CLI.")
                st.info("💡 Vui lòng chạy lệnh sau trên terminal để khởi tạo Admin trước: \n\n`python scripts/create_admin.py`")
            else:
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
                        require_admin_exists=True,
                    )
                    if success:
                        st.success(f"✅ {msg}")
                        st.session_state.auth_tab = "login"
                        st.info("👉 Bạn có thể chuyển sang tab **'Đăng nhập'** bên cạnh để bắt đầu tra cứu.")
                    else:
                        st.error(f"❌ {msg}")

    return None
