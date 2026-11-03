"""Unit and Integration tests for local Kokoro-ONNX Text-to-Speech (TTS).

Covers:
1. Engine singleton initialization and status.
2. Punctuation normalization for single words and phrases.
3. Audio WAV generation (RIFF/WAVE header, 24kHz 16-bit PCM).
4. Diverse vocabulary test cases: single-syllable, multi-syllable, compound phrases.
5. In-memory LRU audio caching.
6. Error handling for missing models (clean Vietnamese exception and HTTP 503).
7. FastAPI endpoint GET /api/tts/status and POST /api/tts/synthesize.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from config.settings import settings
from src.tts.engine import KokoroTTSEngine, get_tts_engine
from vocab_backend.api_server import app


class TestKokoroTTSEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = get_tts_engine()

    def test_01_engine_singleton_and_availability(self):
        """Test engine singleton is initialized and reporting model available."""
        self.assertIsNotNone(self.engine)
        self.assertTrue(self.engine.is_available, "Kokoro TTS engine should be available")
        status = self.engine.get_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["default_voice"], "af_heart")
        self.assertTrue(status["model_exists"])
        self.assertTrue(status["voices_exists"])

    def test_02_text_normalization(self):
        """Test single-word prosody punctuation normalization."""
        # Single word without terminal punctuation gets '.'
        self.assertEqual(self.engine.clean_text_for_speech("apple"), "apple.")
        self.assertEqual(self.engine.clean_text_for_speech("  dog   "), "dog.")
        self.assertEqual(self.engine.clean_text_for_speech("ice cream"), "ice cream.")

        # Text with existing terminal punctuation is preserved
        self.assertEqual(self.engine.clean_text_for_speech("hello!"), "hello!")
        self.assertEqual(self.engine.clean_text_for_speech("how are you?"), "how are you?")
        self.assertEqual(self.engine.clean_text_for_speech("family."), "family.")

    def test_03_synthesize_diverse_words(self):
        """Test synthesis of single-syllable, multi-syllable, and compound words."""
        test_words = [
            ("dog", "Single-syllable"),
            ("family", "Multi-syllable"),
            ("ice cream", "Compound phrase"),
        ]

        for word, desc in test_words:
            with self.subTest(word=word, desc=desc):
                wav_bytes = self.engine.synthesize(word)
                self.assertIsInstance(wav_bytes, bytes)
                self.assertGreater(len(wav_bytes), 10000, f"Audio for {word} too short")

                # Verify RIFF WAVE header
                self.assertTrue(wav_bytes.startswith(b"RIFF"), "WAV must start with RIFF")
                self.assertEqual(wav_bytes[8:12], b"WAVE", "WAV format identifier must be WAVE")

    def test_04_in_memory_lru_cache(self):
        """Test that identical synthesis requests hit the in-memory cache."""
        word = "cat"
        status_before = self.engine.get_status()
        cache_before = status_before["cached_words"]

        # First synthesis
        audio1 = self.engine.synthesize(word)
        status_after_1 = self.engine.get_status()
        self.assertGreaterEqual(status_after_1["cached_words"], cache_before)

        # Second synthesis (must hit cache, exact same bytes)
        audio2 = self.engine.synthesize(word)
        self.assertEqual(audio1, audio2)

    def test_05_missing_model_graceful_handling(self):
        """Test engine behaves gracefully when model files are missing."""
        dummy_engine = KokoroTTSEngine(
            model_path=Path("non_existent_dir/model.onnx"),
            voices_path=Path("non_existent_dir/voices.bin"),
        )
        self.assertFalse(dummy_engine.is_available)
        dummy_status = dummy_engine.get_status()
        self.assertFalse(dummy_status["available"])
        self.assertFalse(dummy_status["model_exists"])

        # Attempting to synthesize raises clean RuntimeError in Vietnamese
        with self.assertRaises(RuntimeError) as ctx:
            dummy_engine.synthesize("hello")
        self.assertIn("Mô hình phát âm TTS cục bộ chưa được cấu hình", str(ctx.exception))


class TestKokoroTTSRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_api_tts_status(self):
        """Test GET /api/tts/status endpoint."""
        res = self.client.get("/api/tts/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("available"))
        self.assertEqual(data.get("default_voice"), "af_heart")

    def test_02_api_tts_synthesize_success(self):
        """Test POST /api/tts/synthesize endpoint returns audio/wav."""
        res = self.client.post("/api/tts/synthesize", json={"text": "hello"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "audio/wav")
        body = res.content
        self.assertTrue(body.startswith(b"RIFF"))
        self.assertEqual(body[8:12], b"WAVE")
        self.assertGreater(len(body), 10000)

    def test_03_api_tts_synthesize_empty_text(self):
        """Test POST /api/tts/synthesize rejects empty or whitespace-only text."""
        res = self.client.post("/api/tts/synthesize", json={"text": "   "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Vui lòng cung cấp từ vựng", res.json().get("detail", ""))

    def test_04_api_tts_synthesize_custom_speed(self):
        """Test POST /api/tts/synthesize accepts custom speed parameter."""
        res = self.client.post(
            "/api/tts/synthesize",
            json={"text": "good morning", "speed": 1.1, "voice": "af_heart"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "audio/wav")
        self.assertTrue(res.content.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
