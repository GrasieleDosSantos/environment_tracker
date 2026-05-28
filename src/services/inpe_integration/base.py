import asyncio
import hashlib
import json
import time
from abc import ABC
from enum import Enum
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from src.utils.logging import get_logger

T = TypeVar("T", bound=BaseModel)


class _CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
        self._state = _CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> _CircuitState:
        if self._state == _CircuitState.OPEN:
            if time.monotonic() - self._opened_at > self._recovery:
                self._state = _CircuitState.HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        return self.state == _CircuitState.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        self._opened_at = time.monotonic()
        if self._failures >= self._threshold:
            self._state = _CircuitState.OPEN


class _TokenBucket:
    """Async token-bucket rate limiter."""

    def __init__(self, rate: float) -> None:
        self.rate = rate
        self._capacity = max(rate * 2.0, 1.0)
        self._tokens: float = self._capacity
        self._last: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self.rate)
            self._last = now
            if self._tokens < 1.0:
                await asyncio.sleep((1.0 - self._tokens) / self.rate)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


class BaseINPEClient(ABC):
    """Async base client for TerraBrasilis OGC WFS services.

    Subclasses must set class-level attributes:
        source_name       – e.g. "DETER"
        wfs_endpoint      – full URL of the GeoServer OWS endpoint
        layer_name        – qualified WFS type name (workspace:layer)
        default_cache_ttl – TTL in seconds for cached responses
    """

    source_name: str = ""
    wfs_endpoint: str = ""
    layer_name: str = ""
    default_cache_ttl: int = 3600

    def __init__(self, rate_limit: float = 1.0) -> None:
        self._rate_limiter = _TokenBucket(rate=rate_limit)
        self._circuit_breaker = _CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        self._client: httpx.AsyncClient | None = None
        self._log = get_logger(self.__class__.__module__)

    async def __aenter__(self) -> "BaseINPEClient":
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ #
    # Cache key helpers                                                     #
    # ------------------------------------------------------------------ #

    def build_cache_key(self, params: dict[str, Any], version: str = "v1") -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        query_hash = hashlib.md5(raw.encode()).hexdigest()[:16]
        return f"{self.source_name.lower()}:{query_hash}:{version}"

    # ------------------------------------------------------------------ #
    # Core WFS request                                                      #
    # ------------------------------------------------------------------ #

    async def _wfs_hits_count(
        self,
        cql_filter: str | None = None,
    ) -> int:
        """Return the total feature count matching *cql_filter*.

        Strategy (in order):
        1. Regular GetFeature with count=1 — WFS 2.0.0 always returns
           ``numberMatched`` (total) and ``numberReturned`` (fetched) in the
           GeoJSON FeatureCollection envelope.  Reading ``numberMatched`` gives
           the exact total without downloading all features.
        2. If ``numberMatched`` is absent (older server), fall back to
           ``totalFeatures`` (GeoServer legacy field).
        3. If neither field is present, return the length of the features
           array in the response (inaccurate for truncated results but better
           than returning -1 silently).

        Note: ``resultType=hits`` is intentionally NOT used here because the
        INPE WFS server returns an empty or non-JSON body for hits requests.
        """
        if self._circuit_breaker.is_open():
            raise RuntimeError(
                f"{self.source_name} circuit breaker is OPEN — "
                "service is temporarily unavailable"
            )
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} must be used as an async context manager"
            )

        await self._rate_limiter.acquire()

        params: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": self.layer_name,
            "outputFormat": "application/json",
            "count": "1",   # fetch only 1 record; numberMatched reports the total
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter

        self._log.debug(
            "wfs_count_request",
            source=self.source_name,
            layer=self.layer_name,
            filter=cql_filter,
        )

        # Historical biome queries can take 30–60 s on the INPE WFS; use a longer
        # per-request timeout so slow-but-valid responses aren't dropped.
        _count_timeout = httpx.Timeout(120.0, connect=10.0)

        try:
            resp = await self._client.get(
                self.wfs_endpoint, params=params, timeout=_count_timeout
            )
            resp.raise_for_status()
            self._circuit_breaker.record_success()
            data = resp.json()
            # Prefer numberMatched (WFS 2.0.0 standard)
            for field in ("numberMatched", "totalFeatures"):
                val = data.get(field)
                if val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
            # Last resort: count the features actually returned
            return len(data.get("features", []))
        except Exception as exc:
            self._log.warning("wfs_hits_error", source=self.source_name, error=str(exc))
            return -1

    async def _wfs_get_feature(
        self,
        cql_filter: str | None = None,
        count: int = 1000,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute a WFS 2.0.0 GetFeature request; return raw GeoJSON dict."""
        if self._circuit_breaker.is_open():
            raise RuntimeError(
                f"{self.source_name} circuit breaker is OPEN — "
                "service is temporarily unavailable"
            )
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} must be used as an async context manager"
            )

        await self._rate_limiter.acquire()

        params: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": self.layer_name,
            "outputFormat": "application/json",
            "count": str(count),
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        if extra_params:
            params.update(extra_params)

        self._log.info(
            "wfs_request",
            source=self.source_name,
            layer=self.layer_name,
            count=count,
            filter=cql_filter,
        )

        try:
            resp = await self._client.get(self.wfs_endpoint, params=params)
            if resp.status_code >= 500:
                self._circuit_breaker.record_failure()
                resp.raise_for_status()
            resp.raise_for_status()
            self._circuit_breaker.record_success()
            return resp.json()  # type: ignore[no-any-return]

        except httpx.HTTPStatusError as exc:
            self._log.error(
                "wfs_http_error", source=self.source_name, status=exc.response.status_code
            )
            raise
        except httpx.RequestError as exc:
            self._log.error("wfs_request_error", source=self.source_name, error=str(exc))
            raise

    # ------------------------------------------------------------------ #
    # Response validation helper                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_features(
        raw: dict[str, Any], model_class: type[T]
    ) -> list[T]:
        """Validate GeoJSON FeatureCollection features into a list of Pydantic models."""
        log = get_logger(__name__)
        result: list[T] = []
        for feat in raw.get("features", []):
            try:
                result.append(model_class.model_validate(feat))
            except Exception as exc:
                log.warning("feature_validation_failed", error=str(exc))
        return result
