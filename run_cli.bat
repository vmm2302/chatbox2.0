@echo off
chcp 65001 > nul
title Chatbox 2.0 - Terminal CLI
color 0A

echo ======================================================
echo    ĐANG KHỞI ĐỘNG CHATBOX 2.0 (CLI TERMINAL)...
echo ======================================================
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

:: 2. Tự động nhận diện Python
set "PYTHON_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe"
)

:: 3. Khởi chạy CLI
echo [2/3] Đang khởi chạy Chatbot trên Terminal...
echo.
"%PYTHON_EXE%" src/ui/cli.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LỖI] Khởi chạy thất bại! Hãy chắc chắn đã chạy setup.bat trước đó.
    pause
)
pause
