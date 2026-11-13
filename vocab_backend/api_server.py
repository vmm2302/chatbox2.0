"""FastAPI server for the Modern Vocabulary Web Application.

Provides REST endpoints for:
- Chatbot vocabulary lookup with the required prefix 'Từ bạn tìm kiếm: <word>'
- User-bound session tracker isolation (khóa phiên gắn với người dùng xác thực)
- CEFR level filtering & dynamic vocabulary discovery
- Fast autocomplete search across vocabulary items
- Serving the built modern frontend SPA
"""

from __future__ import annotations

import logging
import os
import random
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
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

from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User
from vocab_backend.dependencies import get_current_user, verify_actor_user_id_match
from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text

logger = logging.getLogger("vocab_api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Chatbot cho từ vựng A1 - A2 - English Vocabulary Web API",
    description="Dedicated API for CEFR English vocabulary lookup (A1–A2) with modern UI/UX.",
    version="2.0.0",
)

from vocab_backend.auth_routes import auth_router
from vocab_backend.conversation_routes import conv_router
from vocab_backend.streaming_routes import streaming_router
from vocab_backend.admin_routes import admin_router
from vocab_backend.tts_routes import tts_router

app.include_router(auth_router)
app.include_router(conv_router)
app.include_router(streaming_router)
app.include_router(admin_router)
app.include_router(tts_router)

# Enable CORS for local Vite dev server and configurable origins (no wildcard with credentials)
_default_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_env_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_cors or _default_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global caches & user-scoped session state
_RECORDS_CACHE: Optional[List[Any]] = None
_WORD_INDEX: Dict[str, Any] = {}
_CHAT_ENGINE = None
_USER_TRACKERS: Dict[str, Any] = {}
_SESSION_LOCKS: Dict[str, threading.Lock] = {}
_MAX_SESSION_TRACKERS = 500
_TRACKER_LOCK = threading.RLock()
_CONV_REPO = ConversationRepository()


def build_user_session_key(user_id: int, conversation_id: Optional[str] = None) -> str:
    """Tạo khóa phiên cô lập gắn chặt với user_id xác thực và conversation_id."""
    conv_part = (conversation_id or "default_session").strip() or "default_session"
    return f"user:{int(user_id)}:session:{conv_part}"


def get_session_lock(session_key: str) -> threading.Lock:
    """Lấy hoặc tạo khóa đồng bộ (thread lock) riêng cho từng khóa phiên người dùng."""
    with _TRACKER_LOCK:
        if session_key not in _SESSION_LOCKS:
            _SESSION_LOCKS[session_key] = threading.Lock()
        return _SESSION_LOCKS[session_key]


def clear_session_tracker(session_key: str) -> bool:
    """Xóa tracker và lock của một khóa phiên cụ thể."""
    with _TRACKER_LOCK:
        existed = session_key in _USER_TRACKERS
        _USER_TRACKERS.pop(session_key, None)
        _SESSION_LOCKS.pop(session_key, None)
        return existed


def clear_user_trackers(user_id: Optional[int] = None) -> int:
    """Dọn dẹp toàn bộ tracker thuộc một user_id hoặc toàn hệ thống."""
    with _TRACKER_LOCK:
        if user_id is None:
            count = len(_USER_TRACKERS)
            _USER_TRACKERS.clear()
            _SESSION_LOCKS.clear()
            return count

        prefix = f"user:{int(user_id)}:"
        keys_to_remove = [k for k in _USER_TRACKERS if k.startswith(prefix)]
        for k in keys_to_remove:
            _USER_TRACKERS.pop(k, None)
            _SESSION_LOCKS.pop(k, None)
        return len(keys_to_remove)


def reload_records():
    """Invalidate memory cache, reload records from disk, and refresh active trackers."""
    global _RECORDS_CACHE, _WORD_INDEX
    _RECORDS_CACHE = None
    _WORD_INDEX.clear()
    recs = get_records()
    with _TRACKER_LOCK:
        for trk in _USER_TRACKERS.values():
            try:
                trk.load_known_words(recs)
                if not recs:
                    trk.clear()
            except Exception as exc:
                logger.warning("Không thể đồng bộ lại tracker khi reload records: %s", exc)
    return recs


def get_records():
    global _RECORDS_CACHE, _WORD_INDEX
    if _RECORDS_CACHE is None:
        try:
            from src.data.loader import QALoader
            loader = QALoader()
            all_recs = loader.get_or_create_records()
            # Retain all valid records with question & answer (supporting any CEFR/custom level)
            _RECORDS_CACHE = [
                r for r in all_recs
                if getattr(r, "question", "") and getattr(r, "answer", "")
            ]
            _WORD_INDEX.clear()
            for rec in _RECORDS_CACHE:
                w = getattr(rec, "word", "").strip().lower()
                lvl = (getattr(rec, "level", "") or "").strip().upper()
                if w:
                    if (w, lvl) not in _WORD_INDEX:
                        _WORD_INDEX[(w, lvl)] = rec
                    if w not in _WORD_INDEX:
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


def get_or_create_tracker(session_id: str, user_id: Optional[int] = None):
    """Lấy hoặc khởi tạo TopicTracker gắn với khóa phiên người dùng (thread-safe)."""
    from src.chat.topic_tracker import TopicTracker

    if user_id is not None:
        prefix = f"user:{int(user_id)}:"
        session_key = session_id if str(session_id).startswith(prefix) else build_user_session_key(user_id, session_id)
    else:
        session_key = str(session_id)

    with _TRACKER_LOCK:
        if session_key not in _USER_TRACKERS:
            if len(_USER_TRACKERS) >= _MAX_SESSION_TRACKERS:
                oldest_key = next(iter(_USER_TRACKERS))
                _USER_TRACKERS.pop(oldest_key, None)
                _SESSION_LOCKS.pop(oldest_key, None)
            records = get_records()
            _USER_TRACKERS[session_key] = TopicTracker(records=records)
        return _USER_TRACKERS[session_key]


@app.on_event("startup")
async def startup_event():
    get_records()
    from src.tts.engine import get_tts_engine
    get_tts_engine()


# ---------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question or vocabulary word")
    level: str = Field("Tất cả", description="Filter CEFR level: 'Tất cả', 'A1', 'A2'")
    conversation_id: Optional[str] = "default_session"
    user_id: Optional[Any] = None


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
async def chat_endpoint(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Process user vocabulary query under authenticated user-bound session key.
    Guarantees that the response begins with:
    'Từ bạn tìm kiếm: <word>'
    """
    actor_user_id = verify_actor_user_id_match(
        current_user,
        payload.user_id,
        allow_default_placeholder=True,
    )

    conv_id = (payload.conversation_id or "default_session").strip() or "default_session"
    if conv_id != "default_session" and _CONV_REPO.is_owned_by_another_user(actor_user_id, conv_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập phiên hội thoại của tài khoản khác.",
        )

    clean_query = payload.query.strip()
    session_key = build_user_session_key(actor_user_id, conv_id)
    tracker = get_or_create_tracker(session_key)
    session_lock = get_session_lock(session_key)
    engine = get_chat_engine()
    word_index = get_word_index()

    # Determine effective query with CEFR preference if specified
    effective_query = clean_query
    if payload.level in {"A1", "A2"}:
        effective_query = f"{clean_query}\n\nƯu tiên thông tin từ trình độ {payload.level}."

    answer_text = ""
    meta_info: Dict[str, Any] = {}
    active_word = ""

    with session_lock:
        # Check direct word dictionary match first for zero-latency response
        clean_lower = clean_query.lower()
        extracted_word = tracker.extract_target_word(clean_query)
        word_candidate = extracted_word if extracted_word else clean_lower
        if not extracted_word:
            for prefix in ["từ ", "nghĩa của từ ", "nghĩa của ", "từ vựng ", "tra từ "]:
                if word_candidate.startswith(prefix):
                    word_candidate = word_candidate[len(prefix):].strip()
                    break
            word_candidate = re.sub(r"\s*(?:nghĩa là gì|là gì|có nghĩa là gì|means?|meaning)\s*\??$", "", word_candidate, flags=re.IGNORECASE).strip()

        direct_rec = word_index.get(word_candidate)

        if engine is not None:
            try:
                resp = engine.ask(effective_query, tracker=tracker)
                answer_text = resp.answer
                resp_intent = getattr(resp, "intent", "DEFINE_VOCAB")
                resp_word = getattr(resp, "word", "") or getattr(resp, "active_word", "") or tracker.active_word
                meta_info = {
                    "mode": resp.mode,
                    "intent": resp_intent,
                    "latency_ms": getattr(resp, "latency_ms", 0.0),
                    "rrf_score": getattr(resp, "rrf_score", 0.0),
                    "active_word": resp_word,
                    "word": resp_word,
                }
                active_word = resp_word or (word_candidate if word_candidate in word_index else "")
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
            answer_text = "Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ."
            active_word = ""

    is_out_of_scope = (
        meta_info.get("mode") == "NO_MATCH"
        or "nằm ngoài phạm vi" in (answer_text or "").lower()
        or "chưa có dữ liệu" in (answer_text or "").lower()
    )

    if is_out_of_scope:
        active_word = ""
        final_text = (answer_text or "").strip()
        structured_card = None
        meta_info["record_id"] = None
        meta_info["word"] = ""
    else:
        # If active_word wasn't resolved, use candidate if it's an English word
        if not active_word and word_candidate in word_index:
            active_word = word_candidate

        # Ensure the mandatory prefix is prepended: 'Từ bạn tìm kiếm: <word>' or 'Từ tiếng Anh phù hợp: <word>'
        current_intent = meta_info.get("intent")
        final_text = ensure_required_search_prefix(answer_text, active_word, intent=current_intent)

        # Parse rich card data (skip structured card for level list responses without a headword)
        if current_intent == "GET_LEVEL_LIST" and not active_word:
            structured_card = None
        else:
            rec_level = getattr(direct_rec, "level", "A1") if direct_rec else "A1"
            structured_card = parse_vocabulary_text(
                final_text,
                default_word=active_word or (word_candidate if word_candidate in word_index else ""),
                default_level=rec_level,
            )
            if structured_card and structured_card.get("word") and not active_word:
                active_word = structured_card["word"]
                meta_info["word"] = active_word
                meta_info["active_word"] = active_word

    return {
        "reply": final_text,
        "word": active_word,
        "structured_card": structured_card,
        "meta": meta_info,
    }


@app.get("/api/words/search", dependencies=[Depends(get_current_user)])
def search_words(
    q: str = Query("", min_length=1),
    level: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Fast prefix & substring autocomplete search across A1–A2 vocabulary."""
    query_clean = q.strip().lower()
    records = get_records()
    results = []

    level_filter = level.strip().upper() if level and level.strip().upper() not in {"", "TẤT CẢ", "ALL"} else None

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


@app.get("/api/words/detail/{word}", dependencies=[Depends(get_current_user)])
def get_word_detail(word: str):
    """Get full structured details for a specific vocabulary word."""
    clean_word = word.strip().lower()
    rec = get_word_index().get(clean_word)
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
    }


@app.get("/api/words/levels", dependencies=[Depends(get_current_user)])
def get_available_levels():
    """Get dynamic list of CEFR levels present in qa_records.jsonl without hardcoding."""
    records = get_records()
    unique_levels = {
        (getattr(r, "level", "") or "").strip().upper()
        for r in records
        if getattr(r, "level", None) and str(r.level).strip()
    }
    # Standard CEFR sorting order first, then any other dynamic levels
    cefr_canonical = ["A1", "A2", "B1", "B2", "C1", "C2"]
    known_levels = [lvl for lvl in cefr_canonical if lvl in unique_levels]
    other_levels = sorted([lvl for lvl in unique_levels if lvl not in cefr_canonical])
    available = known_levels + other_levels
    if not available:
        available = ["A1", "A2"]

    counts = {
        lvl: sum(1 for r in records if (getattr(r, "level", "") or "").strip().upper() == lvl)
        for lvl in available
    }
    return {"levels": available, "counts": counts}


@app.get("/api/words/discover", dependencies=[Depends(get_current_user)])
def discover_words(
    level: Optional[str] = Query("A1"),
    count: int = Query(6, ge=1, le=20),
):
    """Get a set of discovery words for any given level present in the knowledge base."""
    records = get_records()
    eff_count = count if isinstance(count, int) else 6
    eff_level = level if isinstance(level, str) else "A1"
    req_level = eff_level.strip().upper()
    matched = [r for r in records if (getattr(r, "level", "") or "").strip().upper() == req_level]
    if not matched:
        matched = [r for r in records if (getattr(r, "level", "") or "").strip().upper() in {req_level, "A1"}]

    sample = random.sample(matched, min(eff_count, len(matched))) if matched else []

    cards = []
    for r in sample:
        card = parse_vocabulary_text(r.answer, default_word=r.word, default_level=r.level)
        if card:
            # Enforce level based on the level column of qa_records.jsonl
            if getattr(r, "level", None) and str(r.level).strip():
                card["level"] = str(r.level).strip().upper()
            cards.append(card)

    return {"level": req_level, "words": cards, "total_available": len(matched)}


# ---------------------------------------------------------
# Static files mounting for Frontend SPA
# ---------------------------------------------------------
FRONTEND_DIST = PROJECT_ROOT / "vocab_frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static_assets")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon_ico():
        ico_path = FRONTEND_DIST / "favicon.ico"
        if ico_path.exists():
            return FileResponse(
                ico_path,
                media_type="image/x-icon",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return Response(status_code=404)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon_svg():
        svg_path = FRONTEND_DIST / "favicon.svg"
        if svg_path.exists():
            return FileResponse(
                svg_path,
                media_type="image/svg+xml",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return Response(status_code=404)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found.")
        dist_root = FRONTEND_DIST.resolve()
        file_path = (FRONTEND_DIST / full_path).resolve()
        if str(file_path).startswith(str(dist_root)) and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
