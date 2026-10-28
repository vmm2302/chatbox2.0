"""Conversation and Chat History routes for Vocab Web Application.
Reuses src.data.conversation_repository.ConversationRepository without modifying existing files.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.data.conversation_repository import ConversationRepository
from vocab_backend.vocab_parser import parse_vocabulary_text

logger = logging.getLogger("vocab_api.conversations")
conv_router = APIRouter(prefix="/api/conversations", tags=["conversations"])
conv_repo = ConversationRepository()


class CreateConversationRequest(BaseModel):
    user_id: int
    title: Optional[str] = "Cuộc trò chuyện mới"


class RenameConversationRequest(BaseModel):
    user_id: int
    title: str = Field(..., min_length=1)


def get_conversation_time_group(iso_timestamp: Optional[str]) -> str:
    """Classify conversation by time: Hôm nay, 7 ngày gần đây, Trước đó."""
    if not iso_timestamp:
        return "Trước đó"
    try:
        ts_clean = str(iso_timestamp).replace("T", " ").split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
        diff_days = (date.today() - dt.date()).days
        if diff_days <= 0:
            return "Hôm nay"
        elif diff_days <= 7:
            return "7 ngày gần đây"
        else:
            return "Trước đó"
    except Exception:
        return "Trước đó"


@conv_router.get("")
def list_conversations(
    user_id: int = Query(...),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """List conversations for user, organized by pinned and time groups."""
    raw_convs = conv_repo.list_conversations(user_id=user_id, limit=limit)
    valid_convs = [c for c in raw_convs if c.message_count > 0]

    # Search filter
    if search and search.strip():
        q = search.strip().lower()
        valid_convs = [c for c in valid_convs if q in c.title.lower()]

    pinned: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "Hôm nay": [],
        "7 ngày gần đây": [],
        "Trước đó": [],
    }

    for c in valid_convs:
        c_dict = c.to_dict()
        if c.is_pinned:
            pinned.append(c_dict)
        else:
            grp = get_conversation_time_group(c.updated_at or c.created_at)
            grouped[grp].append(c_dict)

    return {
        "pinned": pinned,
        "grouped": grouped,
        "total": len(valid_convs),
    }


@conv_router.post("")
def create_conversation(payload: CreateConversationRequest):
    """Create a new conversation session."""
    conv = conv_repo.create_conversation(user_id=payload.user_id, title=payload.title or "Cuộc trò chuyện mới")
    return {"status": "created", "conversation": conv.to_dict()}


@conv_router.get("/{conv_id}/messages")
def get_conversation_messages(conv_id: str, user_id: int = Query(...)):
    """Get all messages for a specific conversation."""
    conv = conv_repo.get_conversation(user_id=user_id, conversation_id=conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")

    db_msgs = conv_repo.get_messages(user_id=user_id, conversation_id=conv_id)
    messages = []
    for m in db_msgs:
        meta_dict = m.get_meta()
        card_data = None
        if m.role == "assistant":
            word_val = meta_dict.get("word") or ""
            card_data = parse_vocabulary_text(m.content, default_word=word_val)

        messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "meta": meta_dict,
            "cardData": card_data,
            "created_at": m.created_at,
        })

    return {
        "conversation": conv.to_dict(),
        "messages": messages,
    }


@conv_router.patch("/{conv_id}/title")
def rename_conversation(conv_id: str, payload: RenameConversationRequest):
    """Rename a conversation."""
    updated = conv_repo.update_title(user_id=payload.user_id, conversation_id=conv_id, new_title=payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Không thể đổi tên cuộc trò chuyện.")
    return {"status": "updated", "conversation_id": conv_id, "title": payload.title}


@conv_router.patch("/{conv_id}/pin")
def toggle_pin_conversation(conv_id: str, user_id: int = Query(...)):
    """Toggle pinned status for a conversation."""
    new_state = conv_repo.toggle_pin_conversation(user_id=user_id, conversation_id=conv_id)
    return {"status": "updated", "conversation_id": conv_id, "is_pinned": new_state}


@conv_router.delete("/{conv_id}")
def delete_conversation(conv_id: str, user_id: int = Query(...)):
    """Delete a conversation."""
    deleted = conv_repo.delete_conversation(user_id=user_id, conversation_id=conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không thể xóa cuộc trò chuyện.")
    return {"status": "deleted", "conversation_id": conv_id}


@conv_router.delete("")
def clear_all_history(user_id: int = Query(...)):
    """Clear all chat history for user."""
    count = conv_repo.clear_user_history(user_id=user_id)
    return {"status": "cleared", "deleted_count": count}
