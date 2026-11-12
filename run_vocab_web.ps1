# PowerShell launcher for Modern Vocabulary Web App
# Usage:
#   .\run_vocab_web.ps1
#   .\run_vocab_web.ps1 --port 8001
# Or with execution policy bypass:
#   powershell -ExecutionPolicy Bypass -File .\run_vocab_web.ps1

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 📚 CHATBOX 2.0 — MODERN VOCABULARY WEB APP (A1-B2)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Run with virtual environment if present (port check & prompt handled safely inside run_vocab_web.py)
if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Host "🚀 Đang khởi động bằng môi trường ảo .venv..." -ForegroundColor Cyan
    & ".\.venv\Scripts\python.exe" run_vocab_web.py @args
} else {
    Write-Host "🚀 Đang khởi động bằng Python hệ thống..." -ForegroundColor Yellow
    python run_vocab_web.py @args
}
