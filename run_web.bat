@echo off
chcp 65001 > nul
title Chatbox 2.0 - Giao Diện Chuẩn rag-chatbot-main (Gradio)
color 0B

echo =====================================================================
echo    ĐANG KHỞI ĐỘNG CHATBOX 2.0 (GIAO DIỆN CHUẨN RAG-CHATBOT-MAIN)
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Kiểm tra và khởi động dịch vụ Ollama nếu chưa chạy
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [1/3] Đang khởi động dịch vụ Ollama...
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" 2>nul
    timeout /t 3 /nobreak > nul
) else (
    echo [1/3] Dịch vụ Ollama đã sẵn sàng!
)

:: 2. Chuyển vào thư mục dự án và chọn môi trường Python phù hợp
echo [2/3] Đang định cấu hình môi trường...
set "PYTHON_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe"
)

:: 3. Mở trình duyệt và khởi chạy giao diện Gradio chuẩn 100% demo.png
echo [3/3] Đang khởi động máy chủ Gradio tại http://localhost:7860 ...
echo.
start "" http://localhost:7860
"%PYTHON_EXE%" src\ui\gradio_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LỖI] Khởi chạy thất bại! Nếu là lần đầu chạy trên máy mới, hãy chạy setup.bat trước.
    pause
)
pause
