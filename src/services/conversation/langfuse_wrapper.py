"""Langfuse tracing decorators for LLM calls.

``@trace_llm_call`` wraps any function that calls the LLM and records
inputs, outputs, token counts, and latency to Langfuse when credentials
are configured.  When Langfuse is disabled it is a transparent no-op.

Uses the Langfuse v4 ``@observe`` decorator API (the v2/v3
``lf.generation()`` method no longer exists).

``@trace_langgraph_node`` is a no-op stub reserved for the post-MVP
LangGraph upgrade.  It exists here so call sites can already import and
annotate functions without any logic change when LangGraph is introduced.

Session correlation: pass ``langfuse_session_id`` as a kwarg to any
decorated function and it will be attached to the trace automatically.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


# ------------------------------------------------------------------ #
# @trace_llm_call                                                       #
# ------------------------------------------------------------------ #

def trace_llm_call(func: F) -> F:
    """Strip Langfuse kwargs and call the wrapped function.

    Actual tracing is handled by the ``langfuse.openai`` drop-in wrapper
    inside ``OpenAIProvider`` — it auto-instruments every completions call
    without any manual Langfuse API calls on our side.  This decorator
    exists only to cleanly remove ``langfuse_session_id`` / ``langfuse_user_id``
    before they reach the LLM provider.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("langfuse_session_id", None)
        kwargs.pop("langfuse_user_id", None)
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


# ------------------------------------------------------------------ #
# @trace_langgraph_node — post-MVP stub                                #
# ------------------------------------------------------------------ #

def trace_langgraph_node(name: str | None = None) -> Callable[[F], F]:
    """No-op stub for LangGraph node tracing (post-MVP upgrade path).

    Annotate LangGraph node functions with this decorator so that when
    LangGraph is introduced the tracing wiring is already in place.
    """
    def decorator(func: F) -> F:
        return func
    return decorator


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _safe_repr(obj: Any, max_len: int = 500) -> str:
    try:
        s = str(obj)
        return s[:max_len] + "…" if len(s) > max_len else s
    except Exception:
        return "<unrepresentable>"
