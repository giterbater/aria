from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LanguageResponse:
    """Structured response from any LLM provider."""
    text: str
    model: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    error: str = ""
    success: bool = True

    @classmethod
    def fail(cls, error: str, provider: str = "") -> LanguageResponse:
        return cls(text="", error=error, success=False, provider=provider)


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    provider: str = "ollama"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_tokens: int = 2048
    top_p: float = 0.95
    timeout: float = 120.0
    max_retries: int = 2
    stream: bool = False


@runtime_checkable
class LanguageProvider(Protocol):
    """Interface every LLM provider must implement."""

    @property
    def name(self) -> str: ...

    @property
    def is_available(self) -> bool: ...

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LanguageResponse: ...

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ): ...

    def close(self) -> None: ...
