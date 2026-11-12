"""API Routes cho dịch vụ phát âm Text-to-Speech (TTS) cục bộ 100% Offline.

Cung cấp các endpoint:
- POST /api/tts/synthesize: Tổng hợp phát âm từ vựng tiếng Anh ra tệp âm thanh WAV.
- GET  /api/tts/status: Kiểm tra trạng thái sẵn sàng của mô hình Kokoro-ONNX trên máy.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.tts.engine import get_tts_engine
from vocab_backend.dependencies import get_current_user

logger = logging.getLogger("vocab_api.tts")
tts_router = APIRouter(prefix="/api/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=300, description="Từ vựng hoặc câu tiếng Anh cần phát âm")
    voice: Optional[str] = Field("af_heart", description="Tên giọng đọc (mặc định: af_heart)")
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0, description="Tốc độ phát âm (0.5 - 2.0)")


@tts_router.post("/synthesize", dependencies=[Depends(get_current_user)])
def synthesize_speech(payload: SynthesizeRequest):
    """Endpoint tạo âm thanh phát âm từ vựng tiếng Anh bằng mô hình Kokoro-ONNX cục bộ.

    Trả về:
        Response: Tệp âm thanh nhị phân chuẩn audio/wav (24kHz, 16-bit PCM).
    """
    tts_engine = get_tts_engine()

    if not tts_engine.is_available:
        logger.warning("Yêu cầu phát âm thất bại: Mô hình Kokoro-ONNX chưa sẵn sàng.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Mô hình phát âm TTS cục bộ chưa được cấu hình hoặc tệp mô hình không tồn tại "
                "trong 'data/models/kokoro/'. Vui lòng kiểm tra lại dịch vụ backend."
            ),
        )

    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp từ vựng hoặc câu tiếng Anh cần phát âm.",
        )

    try:
        wav_bytes = tts_engine.synthesize(
            text=clean_text,
            voice=payload.voice or "af_heart",
            speed=payload.speed or 1.0,
        )
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Type": "audio/wav",
                "Content-Length": str(len(wav_bytes)),
                "Cache-Control": "public, max-age=86400",
            },
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        logger.error("Lỗi khi tổng hợp phát âm cho '%s': %s", clean_text, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi tổng hợp âm thanh phát âm: {exc}",
        )


@tts_router.get("/status", dependencies=[Depends(get_current_user)])
def tts_status():
    """Endpoint kiểm tra trạng thái hoạt động của mô hình TTS cục bộ."""
    tts_engine = get_tts_engine()
    return tts_engine.get_status()
