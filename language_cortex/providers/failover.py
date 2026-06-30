from __future__ import annotations

import logging
import time
from typing import Iterator

from .base import LanguageProvider, LanguageResponse, ProviderConfig

logger = logging.getLogger("aria.providers.failover")


class FailoverProvider:
    """Provider with automatic retry and failover.

    Primary provider → retry on failure → fallback provider → error.
    """

    def __init__(
        self,
        primary: LanguageProvider,
        fallback: LanguageProvider | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    @property
    def name(self) -> str:
        return f"failover({self._primary.name})"

    @property
    def is_available(self) -> bool:
        return self._primary.is_available or (
            self._fallback is not None and self._fallback.is_available
        )

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LanguageResponse:
        last_error = None

        for attempt in range(1 + self._max_retries):
            result = self._primary.generate(
                prompt, max_tokens=max_tokens, temperature=temperature
            )
            if result.success:
                return result
            last_error = result.error
            logger.warning(
                "Primary provider %s failed (attempt %d/%d): %s",
                self._primary.name, attempt + 1, 1 + self._max_retries, last_error,
            )
            if attempt < self._max_retries:
                time.sleep(self._retry_delay)

        if self._fallback is not None:
            logger.info("Falling back to %s", self._fallback.name)
            result = self._fallback.generate(
                prompt, max_tokens=max_tokens, temperature=temperature
            )
            if result.success:
                return result
            return LanguageResponse.fail(
                f"All providers failed. Primary: {last_error}. "
                f"Fallback: {result.error}",
                f"{self._primary.name}+{self._fallback.name}",
            )

        return LanguageResponse.fail(
            f"Primary provider {self._primary.name} failed after "
            f"{1 + self._max_retries} attempts: {last_error}",
            self._primary.name,
        )

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        try:
            yield from self._primary.generate_stream(
                prompt, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as exc:
            logger.warning("Primary stream failed: %s", exc)
            if self._fallback is not None:
                logger.info("Falling back to %s for stream", self._fallback.name)
                yield from self._fallback.generate_stream(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )
            else:
                yield f"[ERROR: {exc}]"

    def close(self) -> None:
        self._primary.close()
        if self._fallback:
            self._fallback.close()
