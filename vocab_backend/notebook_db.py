"""SQLite database for managing user's saved vocabulary notebook and learning progress."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "vocab_notebook.db"


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_notebook_db() -> None:
    """Initialize the notebook and progress tables if they do not exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                word TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'A1',
                ipa TEXT DEFAULT '',
                part_of_speech TEXT DEFAULT '',
                meaning TEXT NOT NULL DEFAULT '',
                example TEXT DEFAULT '',
                collocations TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'learning', -- 'learning' or 'mastered'
                review_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(user_id, word)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_saved_user_level 
            ON saved_words(user_id, level, status)
        """)
        conn.commit()


def save_word(
    word: str,
    level: str = "A1",
    ipa: str = "",
    part_of_speech: str = "",
    meaning: str = "",
    example: str = "",
    collocations: str = "",
    user_id: str = "default_user",
) -> Dict[str, Any]:
    """Save or update a word in the user's notebook."""
    now = time.time()
    clean_word = word.strip().lower()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO saved_words 
                (user_id, word, level, ipa, part_of_speech, meaning, example, collocations, status, review_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'learning', 0, ?, ?)
            ON CONFLICT(user_id, word) DO UPDATE SET
                level = excluded.level,
                ipa = COALESCE(NULLIF(excluded.ipa, ''), saved_words.ipa),
                part_of_speech = COALESCE(NULLIF(excluded.part_of_speech, ''), saved_words.part_of_speech),
                meaning = COALESCE(NULLIF(excluded.meaning, ''), saved_words.meaning),
                example = COALESCE(NULLIF(excluded.example, ''), saved_words.example),
                collocations = COALESCE(NULLIF(excluded.collocations, ''), saved_words.collocations),
                updated_at = excluded.updated_at
            """,
            (user_id, clean_word, level.upper(), ipa, part_of_speech, meaning, example, collocations, now, now),
        )
        conn.commit()
    return get_word(clean_word, user_id=user_id) or {}


def delete_word(word: str, user_id: str = "default_user") -> bool:
    """Remove a word from the notebook."""
    clean_word = word.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM saved_words WHERE user_id = ? AND word = ?",
            (user_id, clean_word),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_word_status(
    word: str,
    status: str,
    user_id: str = "default_user",
    increment_review: bool = False,
) -> Optional[Dict[str, Any]]:
    """Update status ('learning' or 'mastered') and increment review count."""
    clean_word = word.strip().lower()
    now = time.time()
    review_inc = 1 if increment_review else 0
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE saved_words
            SET status = ?,
                review_count = review_count + ?,
                updated_at = ?
            WHERE user_id = ? AND word = ?
            """,
            (status, review_inc, now, user_id, clean_word),
        )
        conn.commit()
    return get_word(clean_word, user_id=user_id)


def get_word(word: str, user_id: str = "default_user") -> Optional[Dict[str, Any]]:
    """Get a single saved word by headword."""
    clean_word = word.strip().lower()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM saved_words WHERE user_id = ? AND word = ?",
            (user_id, clean_word),
        ).fetchone()
        if row:
            return dict(row)
    return None


def list_saved_words(
    user_id: str = "default_user",
    level: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List saved words with optional level and status filters."""
    query = "SELECT * FROM saved_words WHERE user_id = ?"
    params: List[Any] = [user_id]
    if level and level.upper() in {"A1", "A2", "B1", "B2"}:
        query += " AND level = ?"
        params.append(level.upper())
    if status and status in {"learning", "mastered"}:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_learning_stats(user_id: str = "default_user") -> Dict[str, Any]:
    """Return summary statistics of user's saved vocabulary."""
    with get_db_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM saved_words WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        mastered = conn.execute(
            "SELECT COUNT(*) FROM saved_words WHERE user_id = ? AND status = 'mastered'",
            (user_id,),
        ).fetchone()[0]

        learning = conn.execute(
            "SELECT COUNT(*) FROM saved_words WHERE user_id = ? AND status = 'learning'",
            (user_id,),
        ).fetchone()[0]

        # Stats by level
        level_counts = {}
        for lvl in ["A1", "A2", "B1", "B2"]:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM saved_words WHERE user_id = ? AND level = ?",
                (user_id, lvl),
            ).fetchone()[0]
            level_counts[lvl] = cnt

    return {
        "total_saved": total,
        "mastered": mastered,
        "learning": learning,
        "by_level": level_counts,
    }
