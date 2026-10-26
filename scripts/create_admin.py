"""Script khởi tạo tài khoản Quản trị viên (Admin) đầu tiên cho Chatbox 2.0.

Sử dụng getpass để bảo mật tuyệt đối, không hiển thị mật khẩu ra màn hình terminal.
Mật khẩu được băm bằng thuật toán an toàn trước khi lưu vào cơ sở dữ liệu ứng dụng.

Cách chạy:
    python scripts/create_admin.py
    Hoặc với tham số:
    python scripts/create_admin.py --username admin --display-name "Super Admin"
"""

import argparse
import getpass
import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc của dự án được nhận diện
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.auth.security import validate_password, validate_username
from src.auth.service import AuthService


def main():
    parser = argparse.ArgumentParser(
        description="Khởi tạo tài khoản Quản trị viên (Admin) an toàn cho Chatbox 2.0."
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="Tên đăng nhập cho tài khoản Admin (3-30 ký tự, không dấu cách).",
    )
    parser.add_argument(
        "--display-name",
        type=str,
        default=None,
        help="Tên hiển thị của Quản trị viên.",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Mật khẩu (chỉ dùng cho môi trường kiểm thử tự động). Khuyến khích nhập tương tác.",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("🤖 CHATBOX 2.0 — KHỞI TẠO TÀI KHOẢN QUẢN TRỊ VIÊN (ADMIN)")
    print("=" * 65)

    # 1. Thu thập tên đăng nhập
    username = args.username
    if not username:
        try:
            username = input("Nhập tên đăng nhập Admin: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Thao tác bị hủy bởi người dùng.")
            sys.exit(1)

    valid_u, err_u = validate_username(username)
    if not valid_u:
        print(f"❌ Lỗi tên đăng nhập: {err_u}")
        sys.exit(1)

    # 2. Thu thập tên hiển thị
    display_name = args.display_name
    if not display_name:
        try:
            display_name = input(f"Nhập tên hiển thị [{username}]: ").strip() or username
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Thao tác bị hủy bởi người dùng.")
            sys.exit(1)

    # 3. Thu thập mật khẩu an toàn
    password = args.password
    if not password:
        try:
            password = getpass.getpass("Nhập mật khẩu Admin (tối thiểu 6 ký tự): ")
            confirm = getpass.getpass("Xác nhận lại mật khẩu: ")
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Thao tác bị hủy bởi người dùng.")
            sys.exit(1)

        if password != confirm:
            print("❌ Lỗi: Mật khẩu xác nhận không khớp.")
            sys.exit(1)
    else:
        # Nếu truyền qua flag thì kiểm tra trực tiếp
        pass

    valid_p, err_p = validate_password(password)
    if not valid_p:
        print(f"❌ Lỗi mật khẩu: {err_p}")
        sys.exit(1)

    # 4. Tiến hành khởi tạo qua AuthService
    auth_service = AuthService()
    success, admin_user, msg = auth_service.bootstrap_first_admin(
        username=username,
        password=password,
        display_name=display_name,
    )

    if success:
        print("\n" + "-" * 65)
        print(f"✅ THÀNH CÔNG: {msg}")
        print(f"   • Tên đăng nhập: {admin_user.username}")
        print(f"   • Tên hiển thị : {admin_user.display_name}")
        print(f"   • Vai trò      : {admin_user.role}")
        print(f"   • Trạng thái   : {'Hoạt động' if admin_user.is_active else 'Khóa'}")
        print("-" * 65)
        print("💡 Bây giờ bạn có thể đăng nhập vào ứng dụng Chatbox 2.0 bằng tài khoản này.")
        sys.exit(0)
    else:
        print(f"\n❌ Thất bại: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
