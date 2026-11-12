"""Entrypoint script to launch the Modern CEFR Vocabulary Web Application.

Usage:
    python run_vocab_web.py
    python run_vocab_web.py --port 8001

Features:
    - Runs FastAPI backend on http://127.0.0.1:<port> and http://localhost:<port>
    - Directly serves the modern React + Tailwind SPA frontend from vocab_frontend/dist
    - Never kills or terminates existing processes on a busy port; asks the user to choose another port
    - Smart readiness polling: Opens browser ONLY when the server and AI models are ready
    - 100% Offline, no external APIs needed
"""

import argparse
import os
import sys
import time
import socket
import webbrowser
from pathlib import Path
from typing import Callable, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Automatically switch to virtual environment Python if invoked with system Python
venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    print(f"🔄 Đang tự động chuyển sang Python môi trường ảo: {venv_python}")
    import subprocess
    sys.exit(subprocess.call([str(venv_python)] + sys.argv))

# Offline environment settings
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def is_port_available(port: int, host: str = DEFAULT_HOST) -> bool:
    """Check whether TCP port is free without touching or terminating any process."""
    if not isinstance(port, int) or port < 1 or port > 65535:
        return False

    check_hosts = [host]
    if host == "0.0.0.0":
        check_hosts.append("127.0.0.1")

    for check_host in check_hosts:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((check_host, port))
        except OSError:
            return False
        finally:
            sock.close()

    # Probe loopback IPv4/IPv6 to detect listeners bound on another address family
    for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        probe = socket.socket(family, socket.SOCK_STREAM)
        probe.settimeout(0.25)
        try:
            if probe.connect_ex((addr, port)) == 0:
                return False
        except OSError:
            pass
        finally:
            probe.close()

    return True


def resolve_available_port(
    initial_port: int = DEFAULT_PORT,
    host: str = DEFAULT_HOST,
    input_fn: Callable[[str], str] = input,
    is_interactive: Optional[bool] = None,
) -> int:
    """Verify the requested port is free; never stop existing processes, only require changing port."""
    port = int(initial_port)
    interactive = sys.stdin.isatty() if is_interactive is None else bool(is_interactive)

    while True:
        if 1 <= port <= 65535 and is_port_available(port, host=host):
            return port

        print(f"⚠️ Cổng {port} đang được tiến trình khác sử dụng.")
        print("ℹ️ Hệ thống không cho phép dừng tiến trình đang chạy — vui lòng đổi sang cổng khác.")

        if not interactive:
            print(
                f"❌ Không thể khởi động trên cổng {port}. "
                f"Vui lòng chạy lại với cổng khác, ví dụ: python run_vocab_web.py --port {port + 1}"
            )
            raise SystemExit(1)

        try:
            raw = input_fn(
                "👉 Nhập số cổng mới (1024–65535, ví dụ 8001) hoặc nhập 'q' để thoát: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Đã hủy khởi động máy chủ.")
            raise SystemExit(1)

        if raw.lower() in {"q", "quit", "exit"}:
            print("🛑 Đã hủy khởi động máy chủ theo yêu cầu.")
            raise SystemExit(0)

        if not raw.isdigit():
            print("❌ Số cổng không hợp lệ. Vui lòng nhập một số nguyên trong khoảng 1024–65535.")
            continue

        candidate = int(raw)
        if candidate < 1024 or candidate > 65535:
            print("❌ Vui lòng chọn số cổng trong khoảng 1024–65535.")
            continue

        port = candidate


def open_browser_when_ready(target_url: str, health_url: str, timeout: float = 25.0):
    """Poll health endpoint until server and models are 100% ready before popping up browser."""
    import urllib.request
    t_start = time.time()
    while time.time() - t_start < timeout:
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    elapsed = round(time.time() - t_start, 1)
                    print(f"✅ Máy chủ và mô hình đã sẵn sàng ({elapsed}s)!")
                    print(f"🌐 Đang tự động mở trình duyệt tại: {target_url}\n")
                    webbrowser.open(target_url)
                    return
        except Exception:
            pass
        time.sleep(0.35)

    print(f"🌐 Vui lòng mở trình duyệt và truy cập: {target_url}")


def parse_args(argv=None):
    """Parse CLI arguments for host and port configuration."""
    env_port = os.getenv("PORT", str(DEFAULT_PORT))
    default_port = int(env_port) if env_port.isdigit() else DEFAULT_PORT
    parser = argparse.ArgumentParser(description="Launch CEFR Vocabulary Web Application")
    parser.add_argument("--host", default=os.getenv("HOST", DEFAULT_HOST), help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=default_port, help="TCP port to listen on (default: 8000)")
    return parser.parse_args(argv)


def main(argv=None):
    import uvicorn
    import threading

    args = parse_args(argv)

    # 1. Check port availability without stopping any running process; prompt to switch port if busy
    selected_port = resolve_available_port(initial_port=args.port, host=args.host)

    print("=" * 70)
    print(" 📚 CHATBOT CHO TỪ VỰNG A1 - A2 — WEB APPLICATION")
    print("=" * 70)
    print(" 🚀 Đang khởi động Backend API & Giao diện Web...")
    print(" 🌐 Địa chỉ truy cập:")
    print(f"    👉 http://127.0.0.1:{selected_port} (Khuyên dùng)")
    print(f"    👉 http://localhost:{selected_port}")
    print(" 🛠️  Dành cho lập trình viên (Hot reload Vite React):")
    print("    cd vocab_frontend; npm run dev  --> http://localhost:5173")
    print("=" * 70)

    # 2. Launch background readiness polling
    target_browser_url = f"http://127.0.0.1:{selected_port}"
    health_check_url = f"http://127.0.0.1:{selected_port}/api/health"
    threading.Thread(
        target=open_browser_when_ready,
        args=(target_browser_url, health_check_url),
        daemon=True,
    ).start()

    # 3. Launch Uvicorn server on configured host & selected port
    uvicorn.run(
        "vocab_backend.api_server:app",
        host=args.host,
        port=selected_port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
