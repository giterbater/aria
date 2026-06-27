from __future__ import annotations
import asyncio
from typing import AsyncIterator, Optional
from .interfaces import LanguageModel

class LanguageCortex:
    """
    ARIA's language subsystem – pure text‑in / text‑out.

    Parameters
    ----------
    model : LanguageModel
        The backend responsible for generation. Can be swapped at runtime
        or via dependency injection.
    """
    def __init__(self, model: LanguageModel) -> None:
        self._model = model

    # -----------------------------------------------------------------
    # Core language API
    # -----------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion for *prompt*."""
        return await self._model.generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        )

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield tokens as they are produced."""
        async for token in self._model.stream_generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        ):
            yield token

    # -----------------------------------------------------------------
    # Optional convenience helpers (still pure text)
    # -----------------------------------------------------------------
    async def chat(self, user_input: str, **gen_kwargs) -> str:
        """Convenience wrapper that treats *user_input* as a single turn."""
        return await self.generate(user_input, **gen_kwargs)

    async def chat_stream(
        self, user_input: str, **gen_kwargs
    ) -> AsyncIterator[str]:
        """Streaming version of :meth:`chat`."""
        async for token in self.stream_generate(
            user_input, **gen_kwargs
        ):
            yield token