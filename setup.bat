@echo off
chcp 65001 > nul
title Chatbox 2.0 - Cài Đặt Tự Động (1-Click Setup)
color 0A

echo =====================================================================
echo       CHATBOX 2.0 — CÔNG CỤ CÀI ĐẶT ^& THIẾT LẬP MÔI TRƯỜNG TỰ ĐỘNG
echo =====================================================================
echo.

cd /d "%~dp0"

rem Thiết lập biến môi trường để tắt cảnh báo symlinks và log thừa của Hugging Face
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "TRANSFORMERS_VERBOSITY=error"

rem 1. Kiểm tra Python
echo [1/5] Kiểm tra phiên bản Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Chưa tìm thấy Python trên máy tính!
    echo Vui lòng cài đặt Python [phiên bản 3.10 hoặc 3.11] từ: https://www.python.org/downloads/
    echo Lưu ý: Hãy tích chọn "Add Python to PATH" khi cài đặt.
    echo.
    pause
    exit /b 1
)
python --version
echo.

rem 2. Khởi tạo Virtual Environment (.venv)
echo [2/5] Kiểm tra và khởi tạo môi trường ảo [.venv]...
if not exist ".venv\Scripts\python.exe" (
    echo Đang tạo môi trường ảo tại .venv ...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [LỖI] Không thể tạo môi trường ảo .venv!
        pause
        exit /b 1
    )
    echo Đã tạo môi trường ảo .venv thành công!
) else (
    echo Môi trường ảo .venv đã tồn tại sẵn.
)
echo.

rem 3. Cài đặt các thư viện bắt buộc từ requirements.txt
echo [3/5] Đang cài đặt các thư viện [pip install -r requirements.txt]...
echo Quá trình này có thể mất từ 2-5 phút tùy theo tốc độ mạng. Vui lòng đợi...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Cài đặt thư viện thất bại! Vui lòng kiểm tra lại kết nối mạng.
    pause
    exit /b 1
)
echo Đã cài đặt xong toàn bộ thư viện cần thiết!
echo.

rem 4. Tải trước các mô hình Hugging Face [PhoBERT va BGE-M3]
echo [4/5] Đang kiểm tra / tải các mô hình NLP cục bộ [PhoBERT-base-v2 và BGE-M3]...
".venv\Scripts\python.exe" scripts\download_models.py
if %ERRORLEVEL% NEQ 0 (
    echo [CẢNH BÁO] Quá trình tải mô hình có sự cố, hệ thống sẽ tự động tải lại khi khởi chạy nếu cần.
)
echo.

rem 5. Kiểm tra dịch vụ Ollama và mô hình Qwen2.5:7B
echo [5/5] Kiểm tra dịch vụ Ollama và mô hình LLM...
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [NHẮC NHỞ] Chưa phát hiện dịch vụ 'ollama' trong hệ thống.
    echo Vui lòng tải và cài đặt Ollama từ: https://ollama.com
    echo Sau khi cài đặt xong, hãy mở Terminal/CMD và gõ:
    echo     ollama pull qwen2.5:7b
    goto :finish
)

echo Dịch vụ Ollama đã được cài đặt!
echo Đang kiểm tra mô hình qwen2.5:7b...
ollama list > "%TEMP%\chatbox_ollama_list.tmp" 2>nul
findstr /i "qwen2.5:7b" "%TEMP%\chatbox_ollama_list.tmp" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [NHẮC NHỞ] Chưa tìm thấy mô hình qwen2.5:7b trong Ollama.
    echo Đang tiến hành kéo mô hình qwen2.5:7b [dung lượng ~4.7 GB]...
    ollama pull qwen2.5:7b
) else (
    echo [V] Mô hình qwen2.5:7b đã sẵn sàng!
)
if exist "%TEMP%\chatbox_ollama_list.tmp" del "%TEMP%\chatbox_ollama_list.tmp" >nul 2>&1

:finish
echo.
echo =====================================================================
echo  🎉 THIẾT LẬP HOÀN TẤT! BẠN ĐÃ SẴN SÀNG CHẠY CHATBOX 2.0!
echo =====================================================================
echo.
echo Để khởi chạy ứng dụng:
echo   - Giao diện Gradio (chuẩn rag-chatbot-main):  Click đúp chay_gradio.bat
echo   - Giao diện Streamlit:                        Click đúp chay_streamlit.bat
echo   - Cập nhật thêm từ vựng Excel:                Click đúp cap_nhat_du_lieu.bat
echo.
pause
