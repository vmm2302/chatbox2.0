"""Tiện ích quản lý dịch vụ Ollama nền và làm nóng mô hình.

Đảm bảo:
- Phát hiện siêu nhanh trạng thái dịch vụ (socket check không chặn).
- Tự khởi động dịch vụ Ollama dưới nền nếu tìm thấy bản cài đặt cục bộ và chưa chạy.
- Tuyệt đối không tự tải mô hình từ Internet.
- Hỗ trợ làm nóng / nạp mô hình trong luồng nền song song khi đăng nhập.
"""

import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

_ollama_process: Optional[subprocess.Popen] = None
_preload_thread: Optional[threading.Thread] = None


def get_ollama_host_port(base_url: Optional[str] = None) -> tuple[str, int]:
    """Phân tách host và port từ OLLAMA_BASE_URL."""
    target_url = base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"
    parsed = urlparse(target_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    return host, port


def is_ollama_running(base_url: Optional[str] = None, timeout: float = 0.25) -> bool:
    """Kiểm tra dịch vụ Ollama có đang lắng nghe cổng mạng không (siêu nhanh, <10ms nếu online)."""
    host, port = get_ollama_host_port(base_url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def find_local_ollama_executable() -> Optional[Path]:
    """Tìm đường dẫn tệp thực thi ollama trên máy tính cục bộ."""
    # 1. Tìm trong PATH hệ thống
    which_path = shutil.which("ollama")
    if which_path:
        p = Path(which_path)
        if p.exists():
            return p

    # 2. Các vị trí cài đặt mặc định trên Windows
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
            Path("C:/Users/User/AppData/Local/Programs/Ollama/ollama.exe"),
        ]
        for c in candidates:
            if c.exists():
                return c

    # 3. Các vị trí cài đặt mặc định trên Linux / macOS
    for c_unix in [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]:
        if c_unix.exists():
            return c_unix

    return None


def ensure_ollama_running_background(base_url: Optional[str] = None) -> bool:
    """Khởi chạy Ollama dưới nền nếu dịch vụ chưa chạy và có sẵn bản cài đặt cục bộ.

    Returns:
        bool: True nếu dịch vụ đang chạy hoặc đã được phát lệnh khởi chạy; False nếu không tìm thấy.
    """
    global _ollama_process

    if is_ollama_running(base_url):
        return True

    exe_path = find_local_ollama_executable()
    if not exe_path:
        logger.info("Không tìm thấy tệp thực thi Ollama cục bộ. Bỏ qua tự khởi chạy.")
        return False

    try:
        logger.info("Khởi chạy Ollama dưới nền từ: %s", exe_path)
        creation_flags = 0
        if sys.platform == "win32":
            # 0x00000008: DETACHED_PROCESS, 0x00000200: CREATE_NEW_PROCESS_GROUP, 0x08000000: CREATE_NO_WINDOW
            creation_flags = 0x00000008 | 0x00000200 | 0x08000000

        _ollama_process = subprocess.Popen(
            [str(exe_path), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
            shell=False,
        )
        return True
    except Exception as exc:
        logger.warning("Không thể tự động khởi động Ollama dưới nền: %s", exc)
        return False


def _do_preload_model(model_name: str, base_url: str) -> None:
    """Thực hiện nạp trước model trong tiến trình nền không chặn UI."""
    clean_url = (base_url or "http://localhost:11434").rstrip("/")

    # Đợi tối đa 4 giây để Ollama sẵn sàng lắng nghe nếu vừa được khởi chạy
    for _ in range(8):
        if is_ollama_running(base_url, timeout=0.2):
            break
        time.sleep(0.5)

    if not is_ollama_running(base_url, timeout=0.3):
        return

    try:
        # Kiểm tra danh sách model đã cài đặt cục bộ (không bao giờ tải mới từ Internet)
        resp = requests.get(f"{clean_url}/api/tags", timeout=1.5)
        if resp.status_code == 200:
            installed = [m.get("name", "") for m in resp.json().get("models", [])]
            target_model = model_name or settings.OLLAMA_MODEL
            # So khớp linh hoạt (vd: qwen2.5:7b hoặc qwen2.5:7b-instruct)
            is_installed = any(
                target_model.lower() in name.lower() or name.lower() in target_model.lower()
                for name in installed
            )
            if is_installed:
                logger.info("Đang nạp model '%s' vào bộ nhớ Ollama...", target_model)
                # Gửi yêu cầu keep_alive để nạp model vào VRAM/RAM
                requests.post(
                    f"{clean_url}/api/generate",
                    json={"model": target_model, "prompt": "", "keep_alive": "10m"},
                    timeout=5.0,
                )
    except Exception as exc:
        logger.debug("Lỗi không nghiêm trọng khi preload Ollama model: %s", exc)


def preload_model_in_background(model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
    """Kích hoạt nạp trước model vào bộ nhớ trong luồng nền (daemon thread)."""
    global _preload_thread
    if _preload_thread and _preload_thread.is_alive():
        return

    target_model = model_name or settings.OLLAMA_MODEL
    target_url = base_url or settings.OLLAMA_BASE_URL
    _preload_thread = threading.Thread(
        target=_do_preload_model,
        args=(target_model, target_url),
        daemon=True,
        name="ollama-preload-thread",
    )
    _preload_thread.start()
