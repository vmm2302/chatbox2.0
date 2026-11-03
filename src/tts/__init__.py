"""Package phát âm giọng đọc tiếng Anh cục bộ (Offline Text-to-Speech) sử dụng Kokoro-ONNX."""

from src.tts.engine import KokoroTTSEngine, get_tts_engine

__all__ = ["KokoroTTSEngine", "get_tts_engine"]
