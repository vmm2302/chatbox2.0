@echo off
chcp 65001 >nul
title Chatbox 2.0 - Gradio UI (rag-chatbot-main)
color 0B

echo =====================================================================
echo    KHỞI CHẠY GIAO DIỆN CHATBOT (GRADIO NATIVE - CHUẨN RAG-CHATBOT-MAIN)
echo =====================================================================
echo.

cd /d "%~dp0"

:: Tự động nhận diện môi trường Python
set "PYTHON_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe"
)

:: Kiểm tra Ollama
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [*] Đang khởi động dịch vụ Ollama...
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" 2>nul
    timeout /t 2 /nobreak > nul
)

echo [*] Đang khởi động Gradio tại http://localhost:7860 ...
echo.
start "" http://localhost:7860
"%PYTHON_EXE%" src\ui\gradio_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LỖI] Khởi chạy thất bại! Nếu là lần đầu chạy, hãy chạy setup.bat trước.
    pause
)
pause
