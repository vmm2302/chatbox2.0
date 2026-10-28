"""FastAPI server for the Modern Vocabulary Web Application.

Provides REST endpoints for:
- Chatbot vocabulary lookup with the required prefix 'Từ bạn tìm kiếm: <word>'
- CEFR level filtering (A1, A2, B1, B2)
- Fast autocomplete search across 3,725 Oxford vocabulary items
- Word discovery & random cards
- Sổ tay từ vựng (Word Notebook) & Flashcard state tracking
- Serving the built modern frontend SPA
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Offline environment settings
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from vocab_backend.notebook_db import (
    delete_word,
    get_learning_stats,
    get_word,
    init_notebook_db,
    list_saved_words,
    save_word,
    update_word_status,
)
from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text

logger = logging.getLogger("vocab_api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Chatbox 2.0 - English Vocabulary Web API",
    description="Dedicated API for CEFR English vocabulary lookup (A1–B2) with modern UI/UX.",
    version="2.0.0",
)

from vocab_backend.auth_routes import auth_router
from vocab_backend.conversation_routes import conv_router
from vocab_backend.streaming_routes import streaming_router
from vocab_backend.admin_routes import admin_router

app.include_router(auth_router)
app.include_router(conv_router)
app.include_router(streaming_router)
app.include_router(admin_router)

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global caches
_RECORDS_CACHE: Optional[List[Any]] = None
_WORD_INDEX: Dict[str, Any] = {}
_CHAT_ENGINE = None
_USER_TRACKERS: Dict[str, Any] = {}


def get_records():
    global _RECORDS_CACHE, _WORD_INDEX
    if _RECORDS_CACHE is None:
        try:
            from src.data.loader import QALoader
            loader = QALoader()
            _RECORDS_CACHE = loader.get_or_create_records()
            _WORD_INDEX.clear()
            for rec in _RECORDS_CACHE:
                w = getattr(rec, "word", "").strip().lower()
                if w and w not in _WORD_INDEX:
                    _WORD_INDEX[w] = rec
            logger.info("Loaded %d vocabulary records into memory.", len(_RECORDS_CACHE))
        except Exception as e:
            logger.error("Failed to load records: %s", e)
            _RECORDS_CACHE = []
            _WORD_INDEX.clear()
    return _RECORDS_CACHE


def get_word_index() -> Dict[str, Any]:
    get_records()
    return _WORD_INDEX


def get_chat_engine():
    global _CHAT_ENGINE
    if _CHAT_ENGINE is None:
        try:
            from src.chat.engine import get_shared_chat_engine
            # Fast retrieval initialization
            _CHAT_ENGINE = get_shared_chat_engine(timeout=3.0)
            logger.info("ChatEngine initialized successfully.")
        except Exception as e:
            logger.warning("ChatEngine initialization deferred or failed: %s", e)
    return _CHAT_ENGINE


def get_or_create_tracker(session_id: str):
    from src.chat.topic_tracker import TopicTracker
    if session_id not in _USER_TRACKERS:
        records = get_records()
        _USER_TRACKERS[session_id] = TopicTracker(records=records)
    return _USER_TRACKERS[session_id]


@app.on_event("startup")
async def startup_event():
    init_notebook_db()
    get_records()


# ---------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question or vocabulary word")
    level: str = Field("Tất cả", description="Filter CEFR level: 'Tất cả', 'A1', 'A2', 'B1', 'B2'")
    conversation_id: Optional[str] = "default_session"
    user_id: Optional[str] = "default_user"


class SaveWordRequest(BaseModel):
    word: str
    level: str = "A1"
    ipa: Optional[str] = ""
    part_of_speech: Optional[str] = ""
    meaning: str = ""
    example: Optional[str] = ""
    collocations: Optional[str] = ""
    user_id: Optional[str] = "default_user"


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(learning|mastered)$")
    user_id: Optional[str] = "default_user"
    increment_review: bool = True


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/api/health")
def health_check():
    engine = get_chat_engine()
    return {
        "status": "ok",
        "engine_ready": engine is not None,
        "total_records": len(get_records()),
        "time": time.time(),
    }


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    """Process user vocabulary query.
    Guarantees that the response begins with:
    'Từ bạn tìm kiếm: <word>'
    """
    clean_query = payload.query.strip()
    session_id = payload.conversation_id or "default_session"
    tracker = get_or_create_tracker(session_id)
    engine = get_chat_engine()

    # Determine effective query with CEFR preference if specified
    effective_query = clean_query
    if payload.level in {"A1", "A2", "B1", "B2"}:
        effective_query = f"{clean_query}\n\nƯu tiên thông tin từ trình độ {payload.level}."

    answer_text = ""
    meta_info: Dict[str, Any] = {}
    active_word = ""

    # Check direct word dictionary match first for zero-latency response
    clean_lower = clean_query.lower()
    # Strip common Vietnamese search prefixes if user typed "từ apple nghĩa là gì?"
    word_candidate = clean_lower
    for prefix in ["từ ", "nghĩa của từ ", "nghĩa của ", "từ vựng ", "tra từ "]:
        if word_candidate.startswith(prefix):
            word_candidate = word_candidate[len(prefix):].strip()
            break
    for suffix in [" nghĩa là gì?", " nghĩa là gì", " là gì?", " là gì", " means", " meaning"]:
        if word_candidate.endswith(suffix):
            word_candidate = word_candidate[:-len(suffix)].strip()
            break

    direct_rec = _WORD_INDEX.get(word_candidate)
    
    if engine is not None:
        try:
            resp = engine.ask(effective_query, tracker=tracker)
            answer_text = resp.answer
            meta_info = {
                "mode": resp.mode,
                "intent": resp.intent,
                "latency_ms": getattr(resp, "latency_ms", 0.0),
                "rrf_score": getattr(resp, "rrf_score", 0.0),
                "active_word": getattr(resp, "active_word", ""),
            }
            active_word = getattr(resp, "active_word", "") or word_candidate
        except Exception as e:
            logger.error("ChatEngine query failed: %s", e)
            if direct_rec:
                answer_text = direct_rec.answer
                active_word = direct_rec.word
            else:
                answer_text = "Xin lỗi, chatbot đang khởi động lại mô hình. Vui lòng thử lại sau giây lát."
    elif direct_rec:
        answer_text = direct_rec.answer
        active_word = direct_rec.word
        meta_info = {"mode": "DIRECT_MATCH", "intent": "DEFINE_VOCAB", "latency_ms": 1.2}
    else:
        answer_text = f"Xin lỗi, hiện tại chưa tìm thấy thông tin cho câu hỏi '{clean_query}'. Bạn hãy thử nhập từ tiếng Anh cụ thể nhé!"
        active_word = ""

    # If active_word wasn't resolved, use candidate if it's an English word
    if not active_word and word_candidate in _WORD_INDEX:
        active_word = word_candidate

    # Ensure the mandatory prefix is prepended: 'Từ bạn tìm kiếm: <word>'
    final_text = ensure_required_search_prefix(answer_text, active_word)

    # Parse rich card data
    rec_level = getattr(direct_rec, "level", "A1") if direct_rec else "A1"
    structured_card = parse_vocabulary_text(
        final_text,
        default_word=active_word or word_candidate,
        default_level=rec_level,
    )

    # Dynamic follow-up suggestion chips tailored to CEFR level
    current_level = structured_card.get("level", "A1")
    suggestions = _build_level_suggestions(active_word or word_candidate, current_level)

    # Check if word is already saved in notebook
    is_saved = False
    if active_word:
        saved_entry = get_word(active_word, user_id=payload.user_id or "default_user")
        is_saved = saved_entry is not None

    return {
        "reply": final_text,
        "word": active_word,
        "structured_card": structured_card,
        "is_saved": is_saved,
        "meta": meta_info,
        "suggestions": suggestions,
    }


def _build_level_suggestions(word: str, level: str) -> List[str]:
    """Generate adaptive follow-up prompts based on word and CEFR level."""
    if not word:
        return [
            "Cho mình danh sách từ vựng A1",
            "Các từ vựng phổ biến cấp độ B1",
            "Phân biệt borrow và lend",
        ]
    
    if level == "A1":
        return [
            f"Cho thêm 2 câu ví dụ đơn giản với '{word}'",
            f"Cách phát âm chuẩn từ '{word}' như thế nào?",
            f"'{word}' thuộc từ loại nào và cách dùng?",
            "Luyện đặt câu đơn giản",
        ]
    elif level == "A2":
        return [
            f"Dạng quá khứ và số nhiều của '{word}' là gì?",
            f"Cho 2 ví dụ ngữ cảnh sinh hoạt với '{word}'",
            f"Từ trái nghĩa của '{word}' là gì?",
            f"Đặt câu với '{word}' ở thì hiện tại hoàn thành",
        ]
    elif level == "B1":
        return [
            f"Các Collocations phổ biến nhất đi với '{word}'",
            f"Phân biệt '{word}' với các từ đồng nghĩa gần nghĩa",
            f"Ví dụ dùng '{word}' trong môi trường công sở/học tập",
            f"Cụm động từ (Phrasal verbs) liên quan đến '{word}'",
        ]
    else:  # B2
        return [
            f"Sắc thái trang trọng (Register) và ngữ cảnh dùng của '{word}'",
            f"Các Idioms hoặc thành ngữ chứa từ '{word}'",
            f"Những lỗi sai phổ biến người học hay gặp với '{word}'",
            f"Từ đồng nghĩa nâng cao thay thế cho '{word}'",
        ]


@app.get("/api/words/search")
def search_words(
    q: str = Query("", min_length=1),
    level: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Fast prefix & substring autocomplete search across 3,725 Oxford words."""
    query_clean = q.strip().lower()
    records = get_records()
    results = []

    level_filter = level.upper() if level and level.upper() in {"A1", "A2", "B1", "B2"} else None

    # 1. Exact match & prefix match first
    for rec in records:
        w = getattr(rec, "word", "").strip()
        w_lower = w.lower()
        rec_lvl = getattr(rec, "level", "A1").upper()
        
        if level_filter and rec_lvl != level_filter:
            continue

        if w_lower.startswith(query_clean):
            # Extract simple first line meaning as snippet
            ans = getattr(rec, "answer", "")
            lines = [line.strip() for line in ans.split("\n") if line.strip()]
            snippet = ""
            ipa = ""
            for l in lines:
                if l.startswith("Phát âm:"):
                    ipa = l.replace("Phát âm:", "").strip()
                elif not l.startswith("Trình độ:") and not l.startswith("Phát âm:") and not snippet:
                    snippet = l.lstrip("•-123456789. ")
            results.append({
                "word": w,
                "level": rec_lvl,
                "ipa": ipa,
                "snippet": snippet[:90],
            })
            if len(results) >= limit:
                break

    # 2. Substring match if not enough results
    if len(results) < limit:
        for rec in records:
            w = getattr(rec, "word", "").strip()
            w_lower = w.lower()
            rec_lvl = getattr(rec, "level", "A1").upper()
            if level_filter and rec_lvl != level_filter:
                continue
            if query_clean in w_lower and not any(r["word"] == w for r in results):
                ans = getattr(rec, "answer", "")
                results.append({
                    "word": w,
                    "level": rec_lvl,
                    "ipa": "",
                    "snippet": ans[:80].replace("\n", " "),
                })
                if len(results) >= limit:
                    break

    return {"query": q, "results": results}


@app.get("/api/words/detail/{word}")
def get_word_detail(word: str):
    """Get full structured details for a specific vocabulary word."""
    clean_word = word.strip().lower()
    rec = _WORD_INDEX.get(clean_word)
    if not rec:
        raise HTTPException(status_code=404, detail="Word not found in knowledge base.")

    answer_text = rec.answer
    formatted_text = ensure_required_search_prefix(answer_text, rec.word)
    structured_card = parse_vocabulary_text(
        formatted_text,
        default_word=rec.word,
        default_level=rec.level,
    )
    return {
        "word": rec.word,
        "level": rec.level,
        "text": formatted_text,
        "structured_card": structured_card,
        "suggestions": _build_level_suggestions(rec.word, rec.level),
    }


@app.get("/api/words/discover")
def discover_words(
    level: Optional[str] = Query("A1"),
    count: int = Query(6, ge=1, le=20),
):
    """Get a set of discovery words for a given CEFR level."""
    records = get_records()
    level_filter = level.upper() if level and level.upper() in {"A1", "A2", "B1", "B2"} else "A1"
    matched = [r for r in records if getattr(r, "level", "A1").upper() == level_filter]
    sample = random.sample(matched, min(count, len(matched))) if matched else []

    cards = []
    for r in sample:
        cards.append(parse_vocabulary_text(r.answer, default_word=r.word, default_level=r.level))

    return {"level": level_filter, "words": cards}


# ---------------------------------------------------------
# Sổ tay từ vựng (Word Notebook & Flashcard endpoints)
# ---------------------------------------------------------
@app.get("/api/notebook")
def get_notebook(
    level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user_id: str = Query("default_user"),
    limit: int = Query(200, ge=1, le=500),
):
    """List saved words from personal notebook."""
    words = list_saved_words(user_id=user_id, level=level, status=status, limit=limit)
    return {"saved_words": words, "count": len(words)}


@app.post("/api/notebook")
def add_to_notebook(payload: SaveWordRequest):
    """Save or update a word in the user's notebook."""
    saved = save_word(
        word=payload.word,
        level=payload.level,
        ipa=payload.ipa or "",
        part_of_speech=payload.part_of_speech or "",
        meaning=payload.meaning,
        example=payload.example or "",
        collocations=payload.collocations or "",
        user_id=payload.user_id or "default_user",
    )
    return {"status": "saved", "word": saved}


@app.delete("/api/notebook/{word}")
def remove_from_notebook(word: str, user_id: str = Query("default_user")):
    """Delete a word from notebook."""
    deleted = delete_word(word, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Word not found in notebook.")
    return {"status": "deleted", "word": word}


@app.patch("/api/notebook/{word}/status")
def change_word_status(word: str, payload: StatusUpdateRequest):
    """Update word learning status (learning vs mastered)."""
    updated = update_word_status(
        word=word,
        status=payload.status,
        user_id=payload.user_id or "default_user",
        increment_review=payload.increment_review,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Word not found.")
    return {"status": "updated", "word": updated}


@app.get("/api/stats")
def get_stats(user_id: str = Query("default_user")):
    """Get personal learning progress stats."""
    return get_learning_stats(user_id=user_id)


# ---------------------------------------------------------
# Static files mounting for Frontend SPA
# ---------------------------------------------------------
FRONTEND_DIST = PROJECT_ROOT / "vocab_frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
