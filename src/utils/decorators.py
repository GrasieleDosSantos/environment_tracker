import asyncio
import functools
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import retry, stop_after_attempt, wait_exponential

F = TypeVar("F", bound=Callable[..., Any])

# Simple in-memory cache for short-lived results; for persistent cache use CacheManager
_mem_cache: dict[str, tuple[Any, float]] = {}


def cache_result(ttl_seconds: int = 300) -> Callable[[F], F]:
    """In-memory TTL cache keyed by function name + serialised arguments."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key_data = {"fn": func.__qualname__, "args": args, "kwargs": kwargs}
            cache_key = hashlib.md5(
                json.dumps(key_data, default=str, sort_keys=True).encode()
            ).hexdigest()
            now = time.monotonic()
            if cache_key in _mem_cache:
                value, expires_at = _mem_cache[cache_key]
                if now < expires_at:
                    return value
            result = func(*args, **kwargs)
            _mem_cache[cache_key] = (result, now + ttl_seconds)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def async_safe(func: F) -> F:
    """Run an async function from synchronous code via asyncio.run(), handling existing loops."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
            # Running inside an existing event loop — use run_coroutine_threadsafe
            import concurrent.futures

            future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
            return future.result()
        except RuntimeError:
            return asyncio.run(func(*args, **kwargs))

    return wrapper  # type: ignore[return-value]


# Pre-configured retry decorator for INPE API calls
inpe_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
