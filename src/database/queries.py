from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import AlertDB, ConversationSessionDB, EnvironmentalDataCacheDB


def get_session_by_id(db: Session, session_id: str) -> ConversationSessionDB | None:
    stmt = select(ConversationSessionDB).where(ConversationSessionDB.session_id == session_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert_conversation_session(
    db: Session,
    session_id: str,
    context_data: dict | None,
    messages: list | None,
    user_id: str | None = None,
    langfuse_session_id: str | None = None,
) -> ConversationSessionDB:
    existing = get_session_by_id(db, session_id)
    if existing:
        if context_data is not None:
            existing.context_data = context_data
        if messages is not None:
            existing.messages = messages
        existing.end_time = datetime.utcnow()
        return existing
    row = ConversationSessionDB(
        session_id=session_id,
        user_id=user_id,
        context_data=context_data,
        messages=messages,
        langfuse_session_id=langfuse_session_id,
    )
    db.add(row)
    return row


def get_cache_entry(db: Session, cache_key: str, now: datetime | None = None) -> dict | None:
    if now is None:
        now = datetime.utcnow()
    stmt = select(EnvironmentalDataCacheDB).where(
        EnvironmentalDataCacheDB.cache_key == cache_key,
        EnvironmentalDataCacheDB.expires_at > now,
    )
    row = db.execute(stmt).scalar_one_or_none()
    return row.data if row else None


def set_cache_entry(
    db: Session,
    cache_key: str,
    source: str,
    query_hash: str,
    data: dict,
    expires_at: datetime,
) -> None:
    stmt = select(EnvironmentalDataCacheDB).where(
        EnvironmentalDataCacheDB.cache_key == cache_key
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        existing.data = data
        existing.expires_at = expires_at
        existing.created_at = datetime.utcnow()
    else:
        db.add(
            EnvironmentalDataCacheDB(
                cache_key=cache_key,
                source=source,
                query_hash=query_hash,
                data=data,
                expires_at=expires_at,
            )
        )


def get_active_alerts(
    db: Session,
    biome_id: str | None = None,
    region_id: str | None = None,
    limit: int = 50,
) -> list[AlertDB]:
    stmt = select(AlertDB).where(AlertDB.status == "active")
    if biome_id:
        stmt = stmt.where(AlertDB.biome_id == biome_id)
    if region_id:
        stmt = stmt.where(AlertDB.region_id == region_id)
    stmt = stmt.order_by(AlertDB.severity_level, AlertDB.detection_date.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())
