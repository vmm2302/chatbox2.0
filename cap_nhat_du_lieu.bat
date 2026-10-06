@echo off
chcp 65001 > nul
title Chatbox 2.0 - Cập Nhật Dữ Liệu Tri Thức Excel
color 0A

echo ===================================================================
echo     CHATBOX 2.0 - CÔNG CỤ CẬP NHẬT DỮ LIỆU EXCEL TỰ ĐỘNG
echo ===================================================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\User\Desktop\chatbot\chatbot\venv\Scripts\python.exe"
)

:: Kiểm tra nếu người dùng kéo thả trực tiếp tệp Excel vào file .bat
if not "%~1"=="" (
    echo [*] Phát hiện tệp kéo thả: "%~1"
    echo [*] Bắt đầu nạp bổ sung dữ liệu vào Chatbox...
    echo.
    "%PYTHON_EXE%" ingest_data.py --file "%~1" --mode append
    echo.
    pause
    exit /b
)

:: Menu lựa chọn nếu người dùng click đúp mở file
echo Hãy chọn một trong các phương án sau:
echo   [1] Cập nhật / Đồng bộ từ tệp Excel mặc định (data/raw/...)
echo   [2] Nhập đường dẫn tệp Excel mới của bạn (.xlsx)
echo   [3] Thoát
echo.
set /p choice="Nhập lựa chọn của bạn (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo [*] Đang nạp dữ liệu từ tệp mặc định...
    "%PYTHON_EXE%" ingest_data.py --mode append
    echo.
    pause
    exit /b
)

if "%choice%"=="2" (
    echo.
    set /p custom_file="Nhập đường dẫn tệp Excel (ví dụ C:\data\tuvung.xlsx): "
    if exist "%custom_file%" (
        echo [*] Đang nạp dữ liệu từ "%custom_file%"...
        "%PYTHON_EXE%" ingest_data.py --file "%custom_file%" --mode append
    ) else (
        echo [!] Không tìm thấy tệp: "%custom_file%"
    )
    echo.
    pause
    exit /b
)

if "%choice%"=="3" (
    exit /b
)

echo [!] Lựa chọn không hợp lệ.
pause
