# PowerShell launcher for Modern Vocabulary Web App
# Usage:
#   .\run_vocab_web.ps1
# Or with execution policy bypass:
#   powershell -ExecutionPolicy Bypass -File .\run_vocab_web.ps1

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 📚 CHATBOX 2.0 — MODERN VOCABULARY WEB APP (A1-B2)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Check if port 8000 is occupied and free it
$busyPort = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($busyPort) {
    Write-Host "⚠️ Phát hiện cổng 8000 đang bận. Đang giải phóng tiến trình cũ..." -ForegroundColor Yellow
    $busyPort | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 800
}

# Run with virtual environment if present
if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Host "🚀 Đang khởi động bằng môi trường ảo .venv..." -ForegroundColor Cyan
    & ".\.venv\Scripts\python.exe" run_vocab_web.py
} else {
    Write-Host "🚀 Đang khởi động bằng Python hệ thống..." -ForegroundColor Yellow
    python run_vocab_web.py
}
