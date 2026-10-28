"""Entrypoint script to launch the Modern CEFR Vocabulary Web Application.

Usage:
    python run_vocab_web.py
    
Features:
    - Runs FastAPI backend on http://127.0.0.1:8000 and http://localhost:8000
    - Directly serves the modern React + Tailwind SPA frontend from vocab_frontend/dist
    - Auto-detects and frees port 8000 if occupied by a stale instance
    - Smart readiness polling: Opens browser ONLY when the server and AI models are 100% ready
    - 100% Offline, no external APIs needed
"""

import os
import sys
import time
import socket
import webbrowser
from pathlib import Path

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


def free_port_if_in_use(port: int = 8000):
    """Detect if port is in use and cleanly free it if held by a stale process."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_in_use = False
    try:
        sock.bind(("0.0.0.0", port))
        sock.close()
        return
    except OSError:
        is_in_use = True

    if is_in_use:
        print(f"⚠️ Cổng {port} đang bị chiếm dụng. Đang tự động giải phóng cổng...")
        if sys.platform == "win32":
            try:
                import subprocess
                cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"'
                out = subprocess.check_output(cmd, shell=True, text=True).strip()
                pids = [int(p) for p in out.split() if p.isdigit()]
                for pid in pids:
                    if pid != os.getpid():
                        print(f"   -> Dừng tiến trình cũ PID: {pid}")
                        subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True)
                time.sleep(1.0)
            except Exception as e:
                print(f"   -> Không thể tự động dừng tiến trình: {e}")


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


def main():
    import uvicorn
    import threading

    print("=" * 70)
    print(" 📚 CHATBOX 2.0 — MODERN VOCABULARY WEB APPLICATION (A1–B2)")
    print("=" * 70)
    print(" 🚀 Đang khởi động Backend API & Giao diện Web...")
    print(" 🌐 Địa chỉ truy cập:")
    print("    👉 http://127.0.0.1:8000 (Khuyên dùng)")
    print("    👉 http://localhost:8000")
    print(" 🛠️  Dành cho lập trình viên (Hot reload Vite React):")
    print("    cd vocab_frontend; npm run dev  --> http://localhost:5173")
    print("=" * 70)

    # 1. Clean up port if occupied
    free_port_if_in_use(8000)

    # 2. Launch background readiness polling
    target_browser_url = "http://127.0.0.1:8000"
    health_check_url = "http://127.0.0.1:8000/api/health"
    threading.Thread(
        target=open_browser_when_ready,
        args=(target_browser_url, health_check_url),
        daemon=True,
    ).start()

    # 3. Launch Uvicorn server on all IPv4 interfaces (0.0.0.0)
    uvicorn.run(
        "vocab_backend.api_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
