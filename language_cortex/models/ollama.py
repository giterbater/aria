from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger("aria.language_cortex.ollama")


class OllamaModel:
    """Ollama HTTP API adapter implementing the LanguageModel protocol.

    Uses synchronous httpx to avoid event loop lifecycle issues.
    Each generate() call creates a fresh connection.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "deepseek-coder-v2:16b",
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def _payload(self, prompt: str, max_tokens: int, temperature: float, stream: bool) -> dict:
        return {
            "model": self._model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        return self.generate_sync(prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_sync(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        try:
            with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
                resp = client.post(
                    "/api/generate",
                    json=self._payload(prompt, max_tokens, temperature, stream=False),
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.HTTPError as exc:
            logger.error("Ollama HTTP error: %s", exc)
            raise
        except Exception as exc:
            logger.error("Ollama error: %s", exc)
            raise

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        try:
            with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
                with client.stream(
                    "POST",
                    "/api/generate",
                    json=self._payload(prompt, max_tokens, temperature, stream=True),
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPError as exc:
            logger.error("Ollama stream error: %s", exc)
            raise
        except Exception as exc:
            logger.error("Ollama stream error: %s", exc)
            raise

    async def close(self) -> None:
        pass
