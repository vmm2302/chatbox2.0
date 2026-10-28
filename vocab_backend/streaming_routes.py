"""Server-Sent Events (SSE) Streaming routes for Vocab Web Application.
Streams tokens in real-time with status updates and TTFT measurement.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Generator, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.data.conversation_repository import ConversationRepository
from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text

logger = logging.getLogger("vocab_api.streaming")
streaming_router = APIRouter(prefix="/api/chat", tags=["chat_streaming"])
conv_repo = ConversationRepository()


class StreamChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    level: str = "Tất cả"
    conversation_id: Optional[str] = None
    user_id: int


@streaming_router.post("/stream")
def stream_chat_endpoint(payload: StreamChatRequest):
    """Endpoint streaming tokens using Server-Sent Events (SSE).
    Guarantees prefix 'Từ bạn tìm kiếm: <word>' and updates conversation history.
    """
    from vocab_backend.api_server import (
        get_chat_engine,
        get_or_create_tracker,
        get_word_index,
        _build_level_suggestions,
    )

    word_index = get_word_index()

    clean_query = payload.query.strip()
    user_id = payload.user_id
    conv_id = payload.conversation_id

    # 1. Ensure conversation exists in DB
    if not conv_id:
        short_title = clean_query[:35] + ("..." if len(clean_query) > 35 else "")
        new_conv = conv_repo.create_conversation(user_id=user_id, title=short_title)
        conv_id = new_conv.id

    # Save user message
    try:
        conv_repo.add_message(user_id=user_id, conversation_id=conv_id, role="user", content=clean_query)
    except Exception as e:
        logger.warning("Could not persist user message: %s", e)

    # 2. Extract potential candidate word
    clean_lower = clean_query.lower()
    word_candidate = clean_lower
    for pfx in ["từ ", "nghĩa của từ ", "nghĩa của ", "từ vựng ", "tra từ "]:
        if word_candidate.startswith(pfx):
            word_candidate = word_candidate[len(pfx):].strip()
            break
    for sfx in [" nghĩa là gì?", " nghĩa là gì", " là gì?", " là gì", " means", " meaning"]:
        if word_candidate.endswith(sfx):
            word_candidate = word_candidate[:-len(sfx)].strip()
            break

    engine = get_chat_engine()
    tracker = get_or_create_tracker(f"user_{user_id}_{conv_id}")

    # Effective query with level
    effective_query = clean_query
    if payload.level in {"A1", "A2", "B1", "B2"}:
        effective_query = f"{clean_query}\n\nƯu tiên thông tin từ trình độ {payload.level}."

    def event_generator() -> Generator[str, None, None]:
        t_start = time.perf_counter()
        # Initial status event
        yield f"data: {json.dumps({'type': 'status', 'text': 'Đang phân tích câu hỏi & tìm kiếm dữ liệu...'}, ensure_ascii=False)}\n\n"

        tokens_accumulated = []
        response_meta = None
        active_word = word_candidate if word_candidate in word_index else ""

        # Emit the mandatory prefix immediately if word is known
        if active_word:
            prefix_chunk = f"Từ bạn tìm kiếm: {active_word}\n\n"
            tokens_accumulated.append(prefix_chunk)
            yield f"data: {json.dumps({'type': 'token', 'token': prefix_chunk}, ensure_ascii=False)}\n\n"

        if engine is not None:
            try:
                for token, meta in engine.ask_stream(effective_query, tracker=tracker):
                    if meta is not None:
                        response_meta = meta
                    if token:
                        tokens_accumulated.append(token)
                        yield f"data: {json.dumps({'type': 'token', 'token': token}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.error("Error during streaming ask_stream: %s", exc)
                error_msg = f"Lỗi xử lý mô hình AI: {exc}"
                tokens_accumulated.append(error_msg)
                yield f"data: {json.dumps({'type': 'token', 'token': error_msg}, ensure_ascii=False)}\n\n"
        else:
            # Fallback to direct word match
            direct_rec = word_index.get(word_candidate)
            if direct_rec:
                ans = direct_rec.answer
                active_word = direct_rec.word
                for chunk in ans.split(" "):
                    tokens_accumulated.append(chunk + " ")
                    yield f"data: {json.dumps({'type': 'token', 'token': chunk + ' '}, ensure_ascii=False)}\n\n"
                    time.sleep(0.01)
            else:
                msg = f"Hiện tại chưa tìm thấy dữ liệu cho '{clean_query}'. Vui lòng thử từ khác."
                tokens_accumulated.append(msg)
                yield f"data: {json.dumps({'type': 'token', 'token': msg}, ensure_ascii=False)}\n\n"

        raw_answer = "".join(tokens_accumulated)
        if response_meta is not None:
            meta_answer = getattr(response_meta, "answer", None)
            meta_word = getattr(response_meta, "word", None)
            if meta_word:
                active_word = meta_word
            if meta_answer and not raw_answer:
                raw_answer = meta_answer

        if not active_word and word_candidate:
            active_word = word_candidate

        # Ensure mandatory prefix in final complete text
        final_answer = ensure_required_search_prefix(raw_answer, active_word)

        # Parse structured card
        structured_card = parse_vocabulary_text(
            final_answer,
            default_word=active_word or word_candidate,
            default_level=payload.level if payload.level in {"A1", "A2", "B1", "B2"} else "A1",
        )

        # Resolve source and sheet from response_meta or candidates
        resolved_source = getattr(response_meta, "source", None)
        resolved_sheet = getattr(response_meta, "sheet", None)
        if not resolved_source and response_meta and getattr(response_meta, "candidates", None):
            for cand in response_meta.candidates:
                if getattr(cand, "record", None) and getattr(cand.record, "source", None):
                    resolved_source = cand.record.source
                    resolved_sheet = getattr(cand.record, "sheet", None)
                    break

        # Build metadata dictionary with Provenance
        meta_dict = {
            "mode": getattr(response_meta, "mode", "DIRECT_MATCH" if active_word in word_index else "RAG_GENERATION"),
            "intent": getattr(response_meta, "intent", "DEFINE_VOCAB"),
            "record_id": getattr(response_meta, "record_id", None),
            "rrf_score": getattr(response_meta, "rrf_score", 0.0),
            "latency_ms": getattr(response_meta, "latency_ms", round((time.perf_counter() - t_start) * 1000, 1)),
            "word": active_word,
            "source": resolved_source or "Cambridge Dictionary",
            "sheet": resolved_sheet,
        }

        # Build suggestions
        suggestions = _build_level_suggestions(active_word, structured_card.get("level", "A1"))

        # Save assistant message to DB
        try:
            conv_repo.add_message(
                user_id=user_id,
                conversation_id=conv_id,
                role="assistant",
                content=final_answer,
                meta_json=json.dumps(meta_dict, ensure_ascii=False),
            )
            # Update title if default
            curr_c = conv_repo.get_conversation(user_id=user_id, conversation_id=conv_id)
            if curr_c and curr_c.title == "Cuộc trò chuyện mới":
                auto_title = clean_query[:35] + ("..." if len(clean_query) > 35 else "")
                conv_repo.update_title(user_id=user_id, conversation_id=conv_id, new_title=auto_title)
        except Exception as e:
            logger.warning("Could not persist assistant message: %s", e)

        # Final complete result event
        result_payload = {
            "type": "final",
            "reply": final_answer,
            "conversation_id": conv_id,
            "structured_card": structured_card,
            "meta": meta_dict,
            "suggestions": suggestions,
        }
        yield f"data: {json.dumps(result_payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
