"""Langfuse SDK initialisation.

Provides a ``get_langfuse_client()`` singleton.  Returns ``None`` when
Langfuse credentials are absent so callers can safely skip tracing.

Environment variables (read via Settings):
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY
  LANGFUSE_HOST  (default: https://cloud.langfuse.com)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.settings import get_settings

if TYPE_CHECKING:
    from langfuse import Langfuse

_client: "Langfuse | None" = None
_initialised = False


def get_langfuse_client() -> "Langfuse | None":
    """Return the Langfuse singleton, or None if credentials are missing."""
    global _client, _initialised
    if _initialised:
        return _client

    _initialised = True
    settings = get_settings()

    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse import Langfuse
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        _client = None

    return _client


def flush_langfuse() -> None:
    """Flush pending Langfuse events — call at app shutdown or end of request."""
    client = get_langfuse_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass
