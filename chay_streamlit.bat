@echo off
chcp 65001 >nul
title Chatbox 2.0 - Streamlit UI (Port 8501)
color 0B

echo =====================================================================
echo    KHỞI CHẠY GIAO DIỆN CHATBOT (STREAMLIT UI - PORT 8501)
echo =====================================================================
echo.

cd /d "%~dp0"

:: Tự động nhận diện môi trường Streamlit
set "STREAMLIT_EXE=streamlit"
if exist "%~dp0.venv\Scripts\streamlit.exe" (
    set "STREAMLIT_EXE=%~dp0.venv\Scripts\streamlit.exe"
) else if exist "%~dp0venv\Scripts\streamlit.exe" (
    set "STREAMLIT_EXE=%~dp0venv\Scripts\streamlit.exe"
) else if exist "C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\streamlit.exe" (
    set "STREAMLIT_EXE=C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\streamlit.exe"
)

:: Kiểm tra Ollama
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [*] Đang khởi động dịch vụ Ollama...
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" 2>nul
    timeout /t 2 /nobreak > nul
)

echo [*] Đang khởi động Streamlit tại http://localhost:8501 ...
echo.
"%STREAMLIT_EXE%" run src\ui\app.py --server.port 8501
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LỖI] Khởi chạy thất bại! Nếu là lần đầu chạy, hãy chạy setup.bat trước.
    pause
)
pause
