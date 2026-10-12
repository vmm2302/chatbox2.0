"""Module quản lý và xử lý nhận dạng ký tự quang học cục bộ (OCR Handler).

Hoạt động 100% offline, tuân thủ các nguyên tắc:
1. Không gửi tài liệu hoặc ảnh ra bất kỳ dịch vụ/API đám mây nào bên ngoài.
2. Kiểm tra tính sẵn sàng của OCR engine cục bộ (Tesseract OCR) và bộ ngôn ngữ (vie, eng).
3. Chỉ thực hiện OCR khi trang PDF không có text hoặc lượng text dưới ngưỡng cho phép.
4. Nếu chưa cài đặt Tesseract, cung cấp thông báo và hướng dẫn cài đặt rõ ràng,
   không báo thành công giả và không làm sập ứng dụng.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Danh sách đường dẫn mặc định của Tesseract trên Windows
STANDARD_WINDOWS_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
]


class OCRHandler:
    """Điều phối và thực thi OCR cục bộ bằng Tesseract."""

    _tesseract_cmd: Optional[str] = None
    _available_languages: Optional[List[str]] = None
    _is_checked: bool = False

    @classmethod
    def get_tesseract_install_guide(cls) -> str:
        """Trả về hướng dẫn cài đặt Tesseract OCR cục bộ cho Windows."""
        return (
            "HƯỚNG DẪN CÀI ĐẶT TESSERACT OCR CỤC BỘ TRÊN WINDOWS:\n"
            "1. Tải bộ cài đặt Tesseract Windows từ GitHub chính thức:\n"
            "   https://github.com/UB-Mannheim/tesseract/wiki\n"
            "2. Trong quá trình cài đặt, tích chọn thêm gói ngôn ngữ 'Vietnamese script' và 'English'.\n"
            "3. Thêm đường dẫn cài đặt (ví dụ: C:\\Program Files\\Tesseract-OCR) vào biến môi trường PATH của hệ thống,\n"
            "   hoặc cài đặt vào đường dẫn mặc định: C:\\Program Files\\Tesseract-OCR\\tesseract.exe.\n"
            "4. Cài đặt thư viện Python hỗ trợ: pip install pytesseract\n"
            "5. Khởi động lại ứng dụng để hệ thống nhận diện Tesseract OCR."
        )

    @classmethod
    def find_tesseract_executable(cls) -> Optional[str]:
        """Xác định đường dẫn file thực thi tesseract.exe trên Windows / Linux."""
        if cls._tesseract_cmd:
            return cls._tesseract_cmd

        # 1. Kiểm tra trong PATH hệ thống
        which_tess = shutil.which("tesseract")
        if which_tess and Path(which_tess).exists():
            cls._tesseract_cmd = which_tess
            return cls._tesseract_cmd

        # 2. Kiểm tra các đường dẫn mặc định trên Windows
        if sys.platform == "win32":
            for path in STANDARD_WINDOWS_TESSERACT_PATHS:
                if path.exists() and path.is_file():
                    cls._tesseract_cmd = str(path)
                    return cls._tesseract_cmd

        return None

    @classmethod
    def get_available_languages(cls) -> List[str]:
        """Lấy danh sách các bộ ngôn ngữ OCR đã được cài đặt."""
        if cls._available_languages is not None:
            return cls._available_languages

        tess_exe = cls.find_tesseract_executable()
        if not tess_exe:
            cls._available_languages = []
            return cls._available_languages

        try:
            res = subprocess.run(
                [tess_exe, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                # Bỏ qua dòng tiêu đề "List of available languages"
                cls._available_languages = [lang for lang in lines if not lang.lower().startswith("list of")]
                return cls._available_languages
        except Exception as err:
            logger.warning("Không thể lấy danh sách ngôn ngữ Tesseract: %s", err)

        cls._available_languages = []
        return cls._available_languages

    @classmethod
    def check_environment(cls) -> Dict[str, any]:
        """Kiểm tra toàn diện môi trường OCR cục bộ."""
        tess_exe = cls.find_tesseract_executable()
        has_tesseract = tess_exe is not None

        has_pytesseract = False
        try:
            import pytesseract
            has_pytesseract = True
        except ImportError:
            pass

        langs = cls.get_available_languages() if has_tesseract else []
        has_vie = "vie" in langs
        has_eng = "eng" in langs

        is_ready = has_tesseract and (has_vie or has_eng)

        return {
            "is_ready": is_ready,
            "has_executable": has_tesseract,
            "executable_path": tess_exe,
            "has_pytesseract": has_pytesseract,
            "languages": langs,
            "has_vie": has_vie,
            "has_eng": has_eng,
            "install_guide": cls.get_tesseract_install_guide() if not is_ready else ""
        }

    @classmethod
    def ocr_pixmap(cls, pixmap, lang: Optional[str] = None) -> Tuple[bool, str, str]:
        """Thực hiện OCR trên đối tượng PyMuPDF Pixmap.

        Args:
            pixmap: pymupdf.Pixmap đối tượng hình ảnh của trang.
            lang: Ngôn ngữ OCR (mặc định thử vie+eng, hoặc vie, hoặc eng).

        Returns:
            Tuple[bool, str, str]: (Thành công?, Text trích xuất được, Thông báo lỗi/trạng thái)
        """
        env = cls.check_environment()
        if not env["is_ready"]:
            return False, "", f"Tesseract OCR chưa sẵn sàng: {env['install_guide']}"

        tess_exe = env["executable_path"]

        # Xác định ngôn ngữ phù hợp từ các gói hiện có
        chosen_lang = lang
        if not chosen_lang:
            langs = env["languages"]
            if "vie" in langs and "eng" in langs:
                chosen_lang = "vie+eng"
            elif "vie" in langs:
                chosen_lang = "vie"
            elif "eng" in langs:
                chosen_lang = "eng"
            elif langs:
                chosen_lang = langs[0]
            else:
                chosen_lang = "eng"

        try:
            import pytesseract
            from PIL import Image
            import io

            pytesseract.pytesseract.tesseract_cmd = tess_exe

            # Chuyển đổi PyMuPDF Pixmap sang PIL Image an toàn qua PNG bytes
            img_bytes = pixmap.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))

            text = pytesseract.image_to_string(image, lang=chosen_lang)
            text_clean = text.strip()
            if text_clean:
                return True, text_clean, "OCR thành công"
            return False, "", "OCR không nhận diện được văn bản nào trên trang."

        except ImportError:
            # Fallback chạy trực tiếp qua tesseract CLI nếu pytesseract chưa được pip install
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                    tmp_img_path = tmp_img.name
                    pixmap.save(tmp_img_path)

                base_out = tmp_img_path + "_out"
                res = subprocess.run(
                    [tess_exe, tmp_img_path, base_out, "-l", chosen_lang],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False
                )

                txt_file = Path(base_out + ".txt")
                if txt_file.exists():
                    text = txt_file.read_text(encoding="utf-8", errors="replace").strip()
                    txt_file.unlink(missing_ok=True)
                    Path(tmp_img_path).unlink(missing_ok=True)
                    if text:
                        return True, text, "OCR thành công (qua CLI fallback)"
                    return False, "", "OCR không nhận diện được văn bản."

                Path(tmp_img_path).unlink(missing_ok=True)
                return False, "", f"OCR thất bại qua CLI: {res.stderr}"

            except Exception as cli_err:
                return False, "", f"Lỗi thực thi Tesseract CLI: {cli_err}"

        except Exception as exc:
            return False, "", f"Lỗi xử lý OCR: {exc}"
