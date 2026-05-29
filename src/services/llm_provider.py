"""LLM provider abstraction layer.

All conversation and analysis services call ``LLMProvider``, never the
OpenAI SDK directly.  This keeps the SDK import in one place and makes
switching providers (Claude, local LLaMA, etc.) a one-line change.

Usage::

    provider = get_llm_provider()
    response = provider.chat(messages, temperature=0.3)
    text = response.content
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.config.settings import get_settings


# ------------------------------------------------------------------ #
# Domain types                                                          #
# ------------------------------------------------------------------ #

class LLMMessage:
    """Thin wrapper around an LLM chat message."""

    __slots__ = ("role", "content")

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        return cls("system", content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        return cls("user", content)

    @classmethod
    def assistant(cls, content: str) -> "LLMMessage":
        return cls("assistant", content)


class LLMResponse:
    """Normalised response from any LLM provider."""

    __slots__ = ("content", "model", "input_tokens", "output_tokens", "raw")

    def __init__(
        self,
        content: str,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        raw: Any = None,
    ) -> None:
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.raw = raw


# ------------------------------------------------------------------ #
# Abstract base                                                         #
# ------------------------------------------------------------------ #

class LLMProvider(ABC):
    """Abstract LLM provider.  Concrete implementations are swappable."""

    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a list of chat messages and return a normalised response."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string used for this provider."""


# ------------------------------------------------------------------ #
# OpenAI implementation (uses langfuse.openai drop-in for tracing)     #
# ------------------------------------------------------------------ #

class OpenAIProvider(LLMProvider):
    """OpenAI chat completions via the Langfuse drop-in wrapper.

    When Langfuse keys are absent the plain ``openai`` SDK is used instead
    so the app works without observability credentials.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.openai_model or "gpt-4o"

        if settings.langfuse_enabled:
            from langfuse.openai import OpenAI
        else:
            from openai import OpenAI  # type: ignore[no-redef]

        self._client = OpenAI(api_key=settings.openai_api_key or None)

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        payload = [m.to_dict() for m in messages]
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=payload,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        choice = completion.choices[0]
        usage = completion.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=completion.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw=completion,
        )


# ------------------------------------------------------------------ #
# Singleton factory                                                     #
# ------------------------------------------------------------------ #

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider (singleton per process)."""
    global _provider
    if _provider is None:
        _provider = OpenAIProvider()
    return _provider
