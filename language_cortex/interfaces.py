from __future__ import annotations
from typing import Protocol, AsyncIterator

class LanguageModel(Protocol):
    """Async language‑model interface – text in, text out."""
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str: ...

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...