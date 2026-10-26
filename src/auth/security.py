"""Bảo mật mật khẩu và kiểm tra tính hợp lệ dữ liệu xác thực.

Sử dụng thuật toán băm an toàn Bcrypt kết hợp Salt ngẫu nhiên.
Hỗ trợ cơ chế dự phòng PBKDF2-HMAC-SHA256 (600,000 vòng) cho môi trường ngoại tuyến
khi thư viện ngoài không khả dụng.
Tuyệt đối không lưu trữ hoặc in mật khẩu văn bản thuần ra log / console.
"""

import hashlib
import hmac
import os
import re
from typing import Tuple

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

# Độ dài tối thiểu của mật khẩu
MIN_PASSWORD_LENGTH = 6
# Regex quy tắc tên đăng nhập: 3-30 ký tự, chữ cái, số, gạch dưới, gạch ngang, chấm
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{3,30}$")


def validate_username(username: str) -> Tuple[bool, str]:
    """Kiểm tra tên đăng nhập có hợp lệ theo quy tắc bảo mật."""
    if not username or not isinstance(username, str):
        return False, "Tên đăng nhập không được để trống."
    
    clean_user = username.strip()
    if len(clean_user) < 3 or len(clean_user) > 30:
        return False, "Tên đăng nhập phải có độ dài từ 3 đến 30 ký tự."

    if not USERNAME_REGEX.match(clean_user):
        return False, "Tên đăng nhập chỉ được chứa chữ cái, số, gạch dưới (_), gạch nối (-) hoặc dấu chấm (.)."

    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """Kiểm tra chính sách mật khẩu tối thiểu an toàn."""
    if not password or not isinstance(password, str):
        return False, "Mật khẩu không được để trống."

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự."

    if password.strip() == "":
        return False, "Mật khẩu không được chỉ chứa ký tự khoảng trắng."

    return True, ""


def hash_password(password: str) -> str:
    """Tạo chuỗi hash an toàn cho mật khẩu với muối (salt) ngẫu nhiên.
    
    Ưu tiên sử dụng Bcrypt (cost factor = 12).
    Nếu không có thư viện bcrypt, sử dụng PBKDF2-HMAC-SHA256 chuẩn NIST.
    """
    if not password:
        raise ValueError("Mật khẩu không được rỗng.")

    if _HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed_bytes.decode("utf-8")

    # Dự phòng an toàn bằng PBKDF2-HMAC-SHA256 (600,000 iterations)
    salt = os.urandom(16)
    iterations = 600_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_hex = salt.hex()
    hash_hex = derived.hex()
    return f"pbkdf2:sha256:{iterations}${salt_hex}${hash_hex}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu văn bản thuần khớp với chuỗi hash đã lưu."""
    if not plain_password or not hashed_password:
        return False

    try:
        # Nếu chuỗi hash bắt đầu bằng $2b$ hoặc $2a$, đó là Bcrypt
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            if _HAS_BCRYPT:
                return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
            return False

        # Nếu chuỗi hash dạng PBKDF2
        if hashed_password.startswith("pbkdf2:sha256:"):
            prefix, rest = hashed_password.split("pbkdf2:sha256:", 1)
            parts = rest.split("$")
            if len(parts) == 3:
                iterations = int(parts[0])
                salt = bytes.fromhex(parts[1])
                expected_hash = parts[2]
                computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations).hex()
                return hmac.compare_digest(computed, expected_hash)

        return False
    except Exception:
        return False
