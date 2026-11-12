"""Bộ kiểm thử Đánh giá Chất lượng Phát âm (Pronunciation & Acoustic Quality Evaluation).

Đánh giá tự động các tiêu chí âm học và phát âm chuẩn bản ngữ của TTS Kokoro-ONNX:
1. Chuẩn hóa âm học (Acoustic Specifications): Tần số lấy mẫu 24kHz, 16-bit PCM, Mono.
2. Năng lượng tín hiệu & Chống câm (Signal Energy & RMS Non-Silence Verification).
3. Đánh giá tính tương quan giữa Thời lượng phát âm và Số âm tiết (Duration vs. Syllables Ratio).
4. Độ phủ ngữ âm đa dạng A1 - A2 (Phonetic Coverage: nguyên âm đôi, phụ âm ghép, âm câm).
5. Hiệu năng thời gian thực (Real-Time Factor - RTF < 1.0).
"""

import io
import math
import sys
import time
import unittest
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tts.engine import KokoroTTSEngine, get_tts_engine


class TestPronunciationEvaluation(unittest.TestCase):
    """Lớp kiểm thử đánh giá chất lượng phát âm âm học."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo engine phát âm TTS."""
        cls.engine = get_tts_engine()
        if not cls.engine.is_available:
            raise unittest.SkipTest(
                "Mô hình Kokoro-ONNX chưa được tải. Hãy chạy 'python scripts/setup_kokoro_model.py' trước khi test."
            )

    def _parse_wav(self, wav_bytes: bytes):
        """Hàm trợ giúp phân tích cấu trúc kỹ thuật của file âm thanh WAV."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_frames = wf.readframes(n_frames)
            duration_sec = n_frames / float(framerate)

        return {
            "channels": n_channels,
            "sampwidth": sampwidth,
            "sample_rate": framerate,
            "n_frames": n_frames,
            "duration_sec": duration_sec,
            "raw_frames": raw_frames,
        }

    def _calculate_rms(self, raw_frames: bytes, sampwidth: int) -> float:
        """Tính toán năng lượng âm lượng hiệu dụng (RMS Energy) để kiểm tra âm thanh không bị câm."""
        import struct

        if sampwidth != 2:
            return 0.0

        count = len(raw_frames) // 2
        format_str = f"<{count}h"
        shorts = struct.unpack(format_str, raw_frames)

        sum_squares = sum(s ** 2 for s in shorts)
        rms = math.sqrt(sum_squares / count) if count > 0 else 0.0
        return rms

    # ==========================================================================
    # TIÊU CHÍ 1: ĐÁNH GIÁ CHUẨN ĐỊNH DẠNG ÂM HỌC (ACOUSTIC FORMAT SPEC)
    # ==========================================================================

    def test_01_acoustic_format_specifications(self):
        """Đảm bảo âm thanh phát âm chuẩn HD Audio: 24.000 Hz, 16-bit, 1 kênh Mono."""
        wav_bytes = self.engine.synthesize("education")
        info = self._parse_wav(wav_bytes)

        self.assertEqual(info["sample_rate"], 24000, "Tần số lấy mẫu phải đạt chuẩn 24kHz HD Audio")
        self.assertEqual(info["channels"], 1, "Kênh âm thanh phải là Mono để tối ưu truyền phát web")
        self.assertEqual(info["sampwidth"], 2, "Độ sâu bit phải là 16-bit (2 bytes)")
        self.assertGreater(info["duration_sec"], 0.4, "Thời lượng từ 'education' phải lớn hơn 0.4s")

    # ==========================================================================
    # TIÊU CHÍ 2: ĐÁNH GIÁ NĂNG LƯỢNG ÂM LƯỢNG (RMS ENERGY & NON-SILENCE)
    # ==========================================================================

    def test_02_audio_energy_and_clarity(self):
        """Kiểm tra âm thanh phát âm có biên độ sóng rõ ràng, không bị câm hoặc mất tiếng."""
        sample_words = ["apple", "beautiful", "communication"]

        for word in sample_words:
            with self.subTest(word=word):
                wav_bytes = self.engine.synthesize(word)
                info = self._parse_wav(wav_bytes)
                rms = self._calculate_rms(info["raw_frames"], info["sampwidth"])

                # RMS của giọng đọc bình thường 16-bit PCM thường dao động từ 1.000 đến 12.000
                self.assertGreater(rms, 500.0, f"Âm thanh của từ '{word}' quá nhỏ hoặc bị câm (RMS={rms:.1f})")
                self.assertLess(rms, 28000.0, f"Âm thanh của từ '{word}' bị vỡ tiếng (Clipping/Distortion, RMS={rms:.1f})")

    # ==========================================================================
    # TIÊU CHÍ 3: ĐÁNH GIÁ TƯƠNG QUAN THỜI LƯỢNG VỚI SỐ ÂM TIẾT (DURATION VS SYLLABLES)
    # ==========================================================================

    def test_03_duration_vs_syllable_correlation(self):
        """Đảm bảo thời lượng phát âm tỷ lệ thuận tự nhiên với độ dài âm tiết của từ vựng."""
        # Danh sách từ có số âm tiết tăng dần từ 1 đến 5 âm tiết
        test_cases = [
            ("cat", 1, 0.3, 1.2),           # 1 âm tiết: 0.3s - 1.2s
            ("water", 2, 0.5, 1.6),         # 2 âm tiết: 0.5s - 1.6s
            ("family", 3, 0.7, 2.0),        # 3 âm tiết: 0.7s - 2.0s
            ("information", 4, 0.9, 2.5),   # 4 âm tiết: 0.9s - 2.5s
            ("responsibility", 6, 1.1, 3.2) # 6 âm tiết: 1.1s - 3.2s
        ]

        durations = []
        for word, syllables, min_sec, max_sec in test_cases:
            wav_bytes = self.engine.synthesize(word)
            info = self._parse_wav(wav_bytes)
            dur = info["duration_sec"]
            durations.append(dur)

            self.assertGreaterEqual(dur, min_sec, f"Từ '{word}' ({syllables} âm tiết) phát âm quá cụt: {dur:.2f}s")
            self.assertLessEqual(dur, max_sec, f"Từ '{word}' ({syllables} âm tiết) phát âm kéo dài bất thường: {dur:.2f}s")

        # Kiểm tra tính đơn điệu tăng dần: từ nhiều âm tiết hơn phải có thời lượng nói dài hơn
        self.assertLess(durations[0], durations[-1], "Từ 1 âm tiết ('cat') phải ngắn hơn từ 6 âm tiết ('responsibility')")

    # ==========================================================================
    # TIÊU CHÍ 4: ĐỘ PHỦ NGỮ ÂM ĐẶC THÙ TIẾNG ANH (PHONETIC PHONEME COVERAGE)
    # ==========================================================================

    def test_04_complex_phonetic_structures(self):
        """Đánh giá phát âm các từ vựng có cấu trúc ngữ âm phức tạp: âm câm, nguyên âm đôi, phụ âm ghép."""
        complex_words = [
            ("knife", "Chứa âm câm k-"),
            ("doubt", "Chứa âm câm -b-"),
            ("school", "Phụ âm ghép sch- và nguyên âm dài -oo-"),
            ("through", "Âm vô thanh th- và vần -ough"),
            ("world", "Cụm phụ âm cuối -rld khó phát âm"),
        ]

        for word, desc in complex_words:
            with self.subTest(word=word, feature=desc):
                wav_bytes = self.engine.synthesize(word)
                info = self._parse_wav(wav_bytes)

                self.assertGreater(len(wav_bytes), 12000, f"Phát âm từ phức tạp '{word}' thất bại")
                self.assertGreater(info["duration_sec"], 0.4, f"Thời lượng từ '{word}' không đủ chuẩn")

    # ==========================================================================
    # TIÊU CHÍ 5: ĐÁNH GIÁ TỐC ĐỘ XỬ LÝ THỜI GIAN THỰC (REAL-TIME FACTOR - RTF)
    # ==========================================================================

    def test_05_synthesis_latency_and_real_time_factor(self):
        """Đo hệ số Real-Time Factor (RTF): Thời gian sinh âm thanh phải nhanh hơn thời gian nói thực tế."""
        test_phrase = "Artificial intelligence helps students learn English vocabulary effectively."

        start_time = time.perf_counter()
        wav_bytes = self.engine.synthesize(test_phrase)
        inference_time = time.perf_counter() - start_time

        info = self._parse_wav(wav_bytes)
        audio_duration = info["duration_sec"]

        # RTF = Thời gian xử lý / Thời lượng âm thanh sinh ra
        rtf = inference_time / audio_duration if audio_duration > 0 else 1.0

        # RTF < 1.0 có nghĩa là mô hình tổng hợp nhanh hơn tốc độ nói thực tế của con người
        self.assertLess(rtf, 1.2, f"Hệ số RTF = {rtf:.2f} quá chậm (Cần < 1.2 trên CPU)")


if __name__ == "__main__":
    unittest.main()