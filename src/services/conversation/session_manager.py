"""Conversation session manager backed by SQLite.

Provides a simple API over ``ConversationSessionDB``; all persistence
goes through the shared ``get_db_session()`` context manager so the same
SQLAlchemy engine is reused across the app.

Session messages are stored as a JSON list of ``{"role": ..., "content": ...}``
dicts, matching the OpenAI chat format so they can be passed directly to the
LLM provider.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import NoResultFound

from src.database.connection import get_db_session
from src.database.models import Base, ConversationSessionDB


def _ensure_tables() -> None:
    """Create tables if they don't exist yet (idempotent)."""
    from src.database.connection import get_engine
    Base.metadata.create_all(bind=get_engine())


# ------------------------------------------------------------------ #
# Public API                                                            #
# ------------------------------------------------------------------ #

def create_session(
    user_id: str | None = None,
    langfuse_session_id: str | None = None,
) -> str:
    """Create a new session and return its UUID string."""
    _ensure_tables()
    session_id = str(uuid.uuid4())

    with get_db_session() as db:
        db.add(ConversationSessionDB(
            session_id=session_id,
            user_id=user_id,
            start_time=datetime.now(timezone.utc),
            messages=[],
            context_data={},
            langfuse_session_id=langfuse_session_id,
        ))

    return session_id


def add_message(
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Append a message to an existing session."""
    with get_db_session() as db:
        row = db.query(ConversationSessionDB).filter_by(session_id=session_id).first()
        if row is None:
            return
        messages: list[dict[str, str]] = list(row.messages or [])
        messages.append({"role": role, "content": content})
        row.messages = messages


def get_context(session_id: str) -> list[dict[str, str]]:
    """Return the full message history for a session as a list of dicts."""
    with get_db_session() as db:
        row = db.query(ConversationSessionDB).filter_by(session_id=session_id).first()
        if row is None:
            return []
        return list(row.messages or [])


def update_context_data(session_id: str, data: dict[str, Any]) -> None:
    """Merge ``data`` into the session's ``context_data`` JSON field."""
    with get_db_session() as db:
        row = db.query(ConversationSessionDB).filter_by(session_id=session_id).first()
        if row is None:
            return
        existing: dict[str, Any] = dict(row.context_data or {})
        existing.update(data)
        row.context_data = existing


def save_session(session_id: str) -> None:
    """Mark a session as ended (sets end_time)."""
    with get_db_session() as db:
        row = db.query(ConversationSessionDB).filter_by(session_id=session_id).first()
        if row is not None:
            row.end_time = datetime.now(timezone.utc)


def get_session_metadata(session_id: str) -> dict[str, Any] | None:
    """Return session metadata dict or None if not found."""
    with get_db_session() as db:
        row = db.query(ConversationSessionDB).filter_by(session_id=session_id).first()
        if row is None:
            return None
        return {
            "session_id": row.session_id,
            "user_id": row.user_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "langfuse_session_id": row.langfuse_session_id,
            "context_data": row.context_data or {},
            "message_count": len(row.messages or []),
        }
