from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select

from src.database.connection import get_db_session
from src.database.models import EnvironmentalDataCacheDB
from src.database.queries import get_cache_entry, set_cache_entry
from src.utils.logging import get_logger

_log = get_logger(__name__)


class CacheManager:
    """SQLite-backed persistent cache for INPE API responses.

    Cache key format: ``{source}:{query_hash}:{version}``
    """

    def get(self, cache_key: str) -> dict[str, Any] | None:
        with get_db_session() as db:
            data = get_cache_entry(db, cache_key)
        if data is not None:
            _log.debug("cache_hit", key=cache_key)
        else:
            _log.debug("cache_miss", key=cache_key)
        return data

    def set(
        self,
        cache_key: str,
        source: str,
        data: dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> None:
        parts = cache_key.split(":")
        query_hash = parts[1] if len(parts) >= 2 else cache_key
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        with get_db_session() as db:
            set_cache_entry(db, cache_key, source, query_hash, data, expires_at)

        _log.debug("cache_set", key=cache_key, ttl_seconds=ttl_seconds)

    def delete(self, cache_key: str) -> None:
        with get_db_session() as db:
            db.execute(
                delete(EnvironmentalDataCacheDB).where(
                    EnvironmentalDataCacheDB.cache_key == cache_key
                )
            )
        _log.debug("cache_delete", key=cache_key)

    def invalidate_by_pattern(self, pattern: str) -> int:
        """Delete all entries whose cache_key starts with *pattern*."""
        with get_db_session() as db:
            rows = db.scalars(
                select(EnvironmentalDataCacheDB).where(
                    EnvironmentalDataCacheDB.cache_key.like(f"{pattern}%")
                )
            ).all()
            count = len(rows)
            for row in rows:
                db.delete(row)
        _log.info("cache_invalidated", pattern=pattern, count=count)
        return count

    def purge_expired(self) -> int:
        """Remove all expired entries; returns number deleted."""
        with get_db_session() as db:
            result = db.execute(
                delete(EnvironmentalDataCacheDB).where(
                    EnvironmentalDataCacheDB.expires_at <= datetime.utcnow()
                )
            )
            count = result.rowcount
        _log.info("cache_purge_expired", count=count)
        return count


_instance: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    global _instance
    if _instance is None:
        _instance = CacheManager()
    return _instance
