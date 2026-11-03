"""Engine phát âm Text-to-Speech cục bộ 100% Offline sử dụng Kokoro-ONNX (int8, af_heart).

Đặc điểm kỹ thuật:
1. Chạy 100% trên CPU qua ONNX Runtime, hoàn toàn không gọi dịch vụ Internet.
2. Tối ưu ngữ điệu từ đơn: tự động chuẩn hóa dấu câu để tránh ngắt âm cụt hoặc ngữ điệu phẳng.
3. Bộ nhớ đệm âm thanh RAM (In-Memory LRU Cache) giúp nghe lại tức thì (0ms).
4. Khóa tiến trình đồng thời (Thread-Safe Lock) bảo vệ ONNX Session.
5. Thông báo lỗi tiếng Việt rõ ràng khi thiếu tệp mô hình, không tự ý tải từ mạng.
"""

import io
import logging
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import soundfile as sf

from config.settings import settings

logger = logging.getLogger("src.tts.engine")


class KokoroTTSEngine:
    """Quản lý khởi tạo và tổng hợp giọng đọc phát âm Kokoro-ONNX."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        voices_path: Optional[Path] = None,
        default_voice: Optional[str] = None,
        default_speed: Optional[float] = None,
        max_cache_entries: int = 500,
    ):
        self.model_path = Path(model_path or settings.KOKORO_MODEL_PATH)
        self.voices_path = Path(voices_path or settings.KOKORO_VOICES_PATH)
        self.default_voice = default_voice or settings.KOKORO_DEFAULT_VOICE
        self.default_speed = default_speed if default_speed is not None else settings.KOKORO_DEFAULT_SPEED

        self._kokoro = None
        self._is_available = False
        self._lock = threading.Lock()
        self._cache: OrderedDict[Tuple[str, str, float], bytes] = OrderedDict()
        self._max_cache_entries = max_cache_entries

        # Tự động nạp mô hình khi khởi tạo nếu tệp tồn tại
        self.initialize()

    @property
    def is_available(self) -> bool:
        """Kiểm tra engine và tệp mô hình đã sẵn sàng hay chưa."""
        return self._is_available and self._kokoro is not None

    def initialize(
        self,
        model_path: Optional[Path] = None,
        voices_path: Optional[Path] = None,
    ) -> bool:
        """Nạp mô hình ONNX và tệp giọng đọc vào bộ nhớ một lần duy nhất."""
        with self._lock:
            if model_path:
                self.model_path = Path(model_path)
            if voices_path:
                self.voices_path = Path(voices_path)

            if not self.model_path.exists() or not self.voices_path.exists():
                logger.warning(
                    "Không tìm thấy tệp mô hình Kokoro tại '%s' hoặc '%s'. "
                    "Chức năng TTS cục bộ sẽ tạm thời không khả dụng.",
                    self.model_path,
                    self.voices_path,
                )
                self._is_available = False
                self._kokoro = None
                return False

            try:
                from kokoro_onnx import Kokoro

                logger.info(
                    "Đang nạp mô hình Kokoro-ONNX từ: %s (voices: %s)",
                    self.model_path.name,
                    self.voices_path.name,
                )
                self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
                self._is_available = True
                logger.info("Kokoro-ONNX TTS Engine đã sẵn sàng (Giọng mặc định: %s).", self.default_voice)
                return True
            except Exception as e:
                logger.error("Lỗi khi khởi tạo mô hình Kokoro-ONNX: %s", e, exc_info=True)
                self._is_available = False
                self._kokoro = None
                return False

    def clean_text_for_speech(self, text: str) -> str:
        """Làm sạch văn bản từ vựng và tối ưu ngữ điệu từ đơn cho Kokoro."""
        # Loại bỏ các ký tự đặc biệt, dấu gạch chéo IPA, dấu ngoặc
        cleaned = re.sub(r"[/\\()[\]*~_\"'`“”‘’]", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""

        # Kokoro tối ưu ngữ điệu ngắt nghỉ tốt hơn khi có dấu câu kết thúc.
        # Nếu là từ đơn hoặc cụm từ chưa có dấu kết thúc, thêm dấu chấm.
        if not re.search(r"[.!?,;:]$", cleaned):
            cleaned = f"{cleaned}."

        return cleaned

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """Tổng hợp giọng đọc từ vựng thành luồng bytes định dạng WAV (24kHz, 16-bit PCM).

        Args:
            text: Từ vựng hoặc câu tiếng Anh cần phát âm.
            voice: Tên giọng đọc (mặc định: 'af_heart').
            speed: Tốc độ đọc (mặc định: 1.0).

        Returns:
            bytes: Dữ liệu âm thanh chuẩn WAV.

        Raises:
            RuntimeError: Nếu mô hình chưa được nạp hoặc tệp mô hình bị thiếu.
            ValueError: Nếu văn bản rỗng sau khi làm sạch.
        """
        if not self.is_available or self._kokoro is None:
            raise RuntimeError(
                "Mô hình phát âm TTS cục bộ chưa được cấu hình hoặc tệp mô hình không tồn tại "
                f"trong '{self.model_path.parent}'. Vui lòng kiểm tra lại dịch vụ backend."
            )

        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            raise ValueError("Văn bản phát âm không hợp lệ hoặc rỗng.")

        active_voice = (voice or self.default_voice).strip()
        active_speed = float(speed if speed is not None else self.default_speed)

        cache_key = (clean_text.lower(), active_voice, round(active_speed, 2))

        # Kiểm tra bộ nhớ đệm
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        # Khóa thực thi ONNX inference để bảo đảm an toàn luồng
        with self._lock:
            try:
                samples, sample_rate = self._kokoro.create(
                    clean_text,
                    voice=active_voice,
                    speed=active_speed,
                    lang="en-us",
                )
            except Exception as exc:
                logger.error("Lỗi khi tổng hợp âm thanh Kokoro cho '%s': %s", clean_text, exc)
                raise RuntimeError(f"Lỗi tổng hợp âm thanh từ vựng: {exc}") from exc

            # Đóng gói mảng numpy thành chuẩn WAV 16-bit PCM
            buffer = io.BytesIO()
            sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
            wav_bytes = buffer.getvalue()

            # Lưu vào bộ nhớ đệm
            self._cache[cache_key] = wav_bytes
            if len(self._cache) > self._max_cache_entries:
                self._cache.popitem(last=False)

            return wav_bytes

    def get_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái hoạt động của TTS Engine."""
        return {
            "available": self.is_available,
            "engine": "Kokoro-ONNX (int8)",
            "model_path": str(self.model_path),
            "voices_path": str(self.voices_path),
            "model_exists": self.model_path.exists(),
            "voices_exists": self.voices_path.exists(),
            "default_voice": self.default_voice,
            "default_speed": self.default_speed,
            "cached_words": len(self._cache),
        }


# Singleton instance
_tts_engine: Optional[KokoroTTSEngine] = None
_tts_lock = threading.Lock()


def get_tts_engine() -> KokoroTTSEngine:
    """Lấy thể hiện duy nhất của KokoroTTSEngine (Singleton)."""
    global _tts_engine
    if _tts_engine is None:
        with _tts_lock:
            if _tts_engine is None:
                _tts_engine = KokoroTTSEngine()
    return _tts_engine
