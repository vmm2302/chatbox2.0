"""Bộ thực thi toàn bộ test suite cho hệ thống Chatbox 2.0 (Backend & Frontend).

Hỗ trợ quét và thực thi:
1. 30 tệp kiểm thử chuẩn unittest.TestCase trong tests/
2. 5 tệp kiểm thử tích hợp dạng hàm / kịch bản độc lập trong tests/
3. Bộ nghiệm thu giao diện React/Vite Frontend (build, lint, unit tests)
"""

import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Danh sách 5 tệp kiểm thử tích hợp dạng hàm/kịch bản (chạy trực tiếp bằng python <file>)
STANDALONE_TEST_FILES = [
    "test_dynamic_levels_and_discovery.py",
    "test_multi_level_e2e_flow.py",
    "test_vocab_auth_admin.py",
    "test_vocab_web_backend.py",
    "test_vocab_web_e2e.py",
]


def setup_test_environment() -> dict:
    env = os.environ.copy()
    env["TESTING"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["AUTH_TOKEN_SECRET"] = "test-secret-key"
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return env


def run_single_test_file(file_path: Path, env: dict, timeout: int = 180) -> tuple:
    start_time = time.perf_counter()
    fname = file_path.name

    if fname in STANDALONE_TEST_FILES:
        cmd = [sys.executable, str(file_path)]
    else:
        cmd = [sys.executable, "-m", "unittest", f"tests/{fname}"]

    try:
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed = round(time.perf_counter() - start_time, 2)
        if res.returncode == 0:
            return "PASS", elapsed, ""
        else:
            err = res.stderr.strip() or res.stdout.strip()
            err_summary = "\n".join(err.splitlines()[-8:])
            return "FAIL", elapsed, err_summary
    except subprocess.TimeoutExpired:
        elapsed = round(time.perf_counter() - start_time, 2)
        return "TIMEOUT", elapsed, f"Quá thời gian chờ ({timeout}s)"
    except Exception as exc:
        elapsed = round(time.perf_counter() - start_time, 2)
        return "ERROR", elapsed, str(exc)


def run_frontend_tests() -> tuple:
    frontend_dir = PROJECT_ROOT / "vocab_frontend"
    if not frontend_dir.exists():
        return "SKIPPED", 0.0, "Không tìm thấy thư mục vocab_frontend"

    start_time = time.perf_counter()
    # Chạy npm test trên Windows
    cmd = "npm test"
    try:
        res = subprocess.run(
            cmd,
            cwd=str(frontend_dir),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        elapsed = round(time.perf_counter() - start_time, 2)
        if res.returncode == 0:
            return "PASS", elapsed, ""
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return "FAIL", elapsed, "\n".join(err.splitlines()[-10:])
    except Exception as exc:
        elapsed = round(time.perf_counter() - start_time, 2)
        return "ERROR", elapsed, str(exc)


def main():
    parser = argparse.ArgumentParser(description="Chạy bộ kiểm thử hệ thống Chatbox 2.0")
    parser.add_argument("--filter", "-f", type=str, default="", help="Lọc tệp kiểm thử theo tên")
    parser.add_argument("--skip-frontend", action="store_true", help="Bỏ qua kiểm thử Frontend")
    parser.add_argument("--timeout", type=int, default=180, help="Thời gian chờ tối đa mỗi tệp (giây)")
    args = parser.parse_args()

    tests_dir = PROJECT_ROOT / "tests"
    all_test_files = sorted(tests_dir.glob("test_*.py"))
    if args.filter:
        all_test_files = [f for f in all_test_files if args.filter.lower() in f.name.lower()]

    env = setup_test_environment()
    results = {}
    print(f"\n{'='*70}")
    print(f"BẮT ĐẦU CHẠY TOÀN BỘ BỘ KIỂM THỬ ({len(all_test_files)} tệp Backend)")
    print(f"Môi trường: Python {sys.version.split()[0]} | Root: {PROJECT_ROOT}")
    print(f"{'='*70}\n")

    for idx, f in enumerate(all_test_files, 1):
        print(f"[{idx:02d}/{len(all_test_files):02d}] Đang chạy {f.name}...", end="", flush=True)
        status, elapsed, err = run_single_test_file(f, env, timeout=args.timeout)
        results[f.name] = (status, elapsed, err)
        if status == "PASS":
            print(f" -> \033[92mPASS\033[0m ({elapsed}s)")
        else:
            print(f" -> \033[91m{status}\033[0m ({elapsed}s)")

    frontend_result = None
    if not args.skip_frontend and not args.filter:
        print(f"\n[FRONTEND] Đang chạy kiểm thử React/Vite (build, lint, tests)...", end="", flush=True)
        fe_status, fe_elapsed, fe_err = run_frontend_tests()
        frontend_result = (fe_status, fe_elapsed, fe_err)
        if fe_status == "PASS":
            print(f" -> \033[92mPASS\033[0m ({fe_elapsed}s)")
        else:
            print(f" -> \033[91m{fe_status}\033[0m ({fe_elapsed}s)")

    # Tổng kết
    print(f"\n{'='*70}")
    print("BẢNG TỔNG KẾT KẾT QUẢ KIỂM THỬ")
    print(f"{'='*70}")

    pass_count = sum(1 for s, _, _ in results.values() if s == "PASS")
    fail_count = sum(1 for s, _, _ in results.values() if s in ("FAIL", "ERROR", "TIMEOUT"))

    print(f"Backend Test Files: {pass_count}/{len(results)} PASS ({pass_count/len(results)*100:.1f}%)")
    if frontend_result:
        print(f"Frontend Verification: {frontend_result[0]} ({frontend_result[1]}s)")

    if fail_count > 0:
        print("\nCác tệp thất bại:")
        for name, (s, elapsed, err) in results.items():
            if s != "PASS":
                print(f" - [{s}] {name} ({elapsed}s)")
                if err:
                    print(f"    Chi tiết: {err}")
        sys.exit(1)
    else:
        print("\n\033[92mTẤT CẢ CÁC BÀI TEST ĐÃ HOÀN TOÀN ĐẠT CHUẨN (100% PASS)!\033[0m\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
