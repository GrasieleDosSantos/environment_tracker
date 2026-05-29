"""Integration tests for CacheManager against a real (temp) SQLite database.

Uses a temporary database file isolated per test to avoid polluting the
development cache and to allow parallel test execution.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest

# Override DATABASE_URL before any src imports touch the DB
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at an isolated temporary SQLite database."""
    db_path = tmp_path / "test_cache.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # Reset settings singleton so it picks up the new env var
    import src.config.settings as _settings_mod
    _settings_mod._settings = None

    # Reset DB connection singletons (both engine AND session factory)
    import src.database.connection as _conn_mod
    _conn_mod._engine = None  # type: ignore[attr-defined]
    _conn_mod._SessionLocal = None  # type: ignore[attr-defined]

    # Reset CacheManager singleton so it opens a fresh session against the new DB
    import src.services.inpe_integration.cache_manager as _cache_mod
    _cache_mod._instance = None

    # Create all tables on the temp DB
    from src.database.connection import get_engine
    from src.database.models import Base
    Base.metadata.create_all(get_engine())

    yield

    # Re-reset after test so later tests don't inherit this DB
    _settings_mod._settings = None
    _conn_mod._engine = None  # type: ignore[attr-defined]
    _conn_mod._SessionLocal = None  # type: ignore[attr-defined]
    _cache_mod._instance = None


@pytest.fixture
def cache():
    from src.services.inpe_integration.cache_manager import CacheManager
    return CacheManager()


# ------------------------------------------------------------------ #
# Basic get / set                                                        #
# ------------------------------------------------------------------ #

class TestCacheManagerBasic:
    def test_miss_returns_none(self, cache):
        assert cache.get("nonexistent:key:v1") is None

    def test_set_then_get_returns_data(self, cache):
        payload = {"features": [{"year": 2024, "area_km": 10.0}]}
        cache.set("prodes:abc123:v1", "PRODES", payload, ttl_seconds=3600)
        result = cache.get("prodes:abc123:v1")
        assert result == payload

    def test_overwrite_existing_key(self, cache):
        cache.set("deter:x:v1", "DETER", {"v": 1}, ttl_seconds=3600)
        cache.set("deter:x:v1", "DETER", {"v": 2}, ttl_seconds=3600)
        result = cache.get("deter:x:v1")
        assert result["v"] == 2

    def test_delete_removes_entry(self, cache):
        cache.set("fogo:del:v1", "FOGO", {"count": 5}, ttl_seconds=3600)
        cache.delete("fogo:del:v1")
        assert cache.get("fogo:del:v1") is None

    def test_delete_missing_key_is_safe(self, cache):
        cache.delete("does:not:exist")  # should not raise


# ------------------------------------------------------------------ #
# TTL / expiry                                                          #
# ------------------------------------------------------------------ #

class TestCacheManagerTTL:
    def test_expired_entry_not_returned(self, cache):
        from src.database.connection import get_db_session
        from src.database.models import EnvironmentalDataCacheDB
        import json

        # Write an entry that is already expired
        cache_key = "deter:expired:v1"
        with get_db_session() as db:
            db.merge(EnvironmentalDataCacheDB(
                cache_key=cache_key,
                source="DETER",
                query_hash="expired",
                data=json.dumps({"features": []}),
                created_at=datetime.utcnow() - timedelta(hours=2),
                expires_at=datetime.utcnow() - timedelta(hours=1),
            ))

        assert cache.get(cache_key) is None

    def test_purge_expired_removes_old_entries(self, cache):
        from src.database.connection import get_db_session
        from src.database.models import EnvironmentalDataCacheDB
        import json

        # Insert one fresh and one expired entry
        with get_db_session() as db:
            db.merge(EnvironmentalDataCacheDB(
                cache_key="deter:stale:v1",
                source="DETER",
                query_hash="stale",
                data=json.dumps({}),
                created_at=datetime.utcnow() - timedelta(hours=2),
                expires_at=datetime.utcnow() - timedelta(seconds=1),
            ))
        cache.set("deter:fresh:v1", "DETER", {}, ttl_seconds=3600)

        removed = cache.purge_expired()
        assert removed >= 1
        assert cache.get("deter:fresh:v1") is not None


# ------------------------------------------------------------------ #
# invalidate_by_pattern                                                 #
# ------------------------------------------------------------------ #

class TestCacheManagerInvalidate:
    def test_invalidate_by_prefix(self, cache):
        cache.set("prodes:a:v1", "PRODES", {"n": 1}, ttl_seconds=3600)
        cache.set("prodes:b:v1", "PRODES", {"n": 2}, ttl_seconds=3600)
        cache.set("deter:c:v1", "DETER", {"n": 3}, ttl_seconds=3600)

        removed = cache.invalidate_by_pattern("prodes:")
        assert removed == 2
        assert cache.get("prodes:a:v1") is None
        assert cache.get("prodes:b:v1") is None
        assert cache.get("deter:c:v1") is not None
