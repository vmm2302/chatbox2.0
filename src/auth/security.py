"""Bảo mật mật khẩu và kiểm tra tính hợp lệ dữ liệu xác thực.

Sử dụng thuật toán băm an toàn Bcrypt kết hợp Salt ngẫu nhiên.
Hỗ trợ cơ chế dự phòng PBKDF2-HMAC-SHA256 (600,000 vòng) cho môi trường ngoại tuyến
khi thư viện ngoài không khả dụng.
Tuyệt đối không lưu trữ hoặc in mật khẩu văn bản thuần ra log / console.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

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


def _b64url_encode(data: bytes) -> str:
    """Mã hóa Base64URL không padding theo chuẩn JWT."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    """Giải mã Base64URL an toàn."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode((segment + padding).encode("ascii"))


def hash_token(raw_token: str) -> str:
    """Băm SHA-256 chuỗi Access Token để lưu đối chiếu an toàn trong SQLite."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    session_id: str,
    secret: bytes,
    expires_minutes: int = 480,
) -> Tuple[str, int, str]:
    """Tạo Access Token định dạng JWT ký bằng HMAC-SHA256 (100% offline, stdlib).

    Returns:
        Tuple[str, int, str]: (raw_token, expires_in_seconds, expires_at_iso)
    """
    if not secret:
        raise ValueError("Khóa bí mật ký token không được rỗng.")

    ttl_minutes = max(1, int(expires_minutes))
    now_ts = int(time.time())
    expires_in = ttl_minutes * 60
    exp_ts = now_ts + expires_in
    expires_at_iso = datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "jti": session_id,
        "iat": now_ts,
        "exp": exp_ts,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig_bytes = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig_bytes)

    return f"{header_b64}.{payload_b64}.{sig_b64}", expires_in, expires_at_iso


def decode_and_verify_access_token(token: str, secret: bytes) -> Dict[str, Any]:
    """Giải mã và kiểm chứng chữ ký + hạn dùng của Access Token HS256."""
    if not token or not isinstance(token, str):
        raise ValueError("Access token không hợp lệ.")
    if not secret:
        raise ValueError("Khóa bí mật xác thực token chưa được cấu hình.")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Định dạng Access token không đúng chuẩn.")

    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Không thể giải mã header của Access token.") from exc

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("Thuật toán ký Access token không được hỗ trợ.")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = _b64url_encode(hmac.new(secret, signing_input, hashlib.sha256).digest())
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise ValueError("Chữ ký Access token không hợp lệ.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Không thể giải mã payload của Access token.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload Access token không hợp lệ.")

    sub = payload.get("sub")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not sub or not jti or not isinstance(exp, (int, float)):
        raise ValueError("Access token thiếu thông tin định danh hoặc thời hạn.")

    if int(time.time()) >= int(exp):
        raise ValueError("Access token đã hết hạn.")

    return payload
