from __future__ import annotations

import json
import logging
import time

import httpx

from .base import LanguageProvider, LanguageResponse, ProviderConfig

logger = logging.getLogger("aria.providers.ollama")


class OllamaProvider:
    """Ollama local LLM provider."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._base_url = (config.base_url or "http://localhost:11434").rstrip("/")
        self._model = config.model or "deepseek-coder-v2:16b"
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=config.timeout,
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def is_available(self) -> bool:
        try:
            resp = self._client.get("/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LanguageResponse:
        t0 = time.monotonic()
        try:
            resp = self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            latency = (time.monotonic() - t0) * 1000
            return LanguageResponse(
                text=data.get("response", ""),
                model=self._model,
                provider=self.name,
                tokens_in=data.get("prompt_eval_count", 0),
                tokens_out=data.get("eval_count", 0),
                latency_ms=round(latency, 1),
            )
        except httpx.HTTPError as exc:
            latency = (time.monotonic() - t0) * 1000
            logger.error("Ollama HTTP error: %s", exc)
            return LanguageResponse.fail(f"Ollama HTTP error: {exc}", self.name)
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            logger.error("Ollama error: %s", exc)
            return LanguageResponse.fail(f"Ollama error: {exc}", self.name)

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        try:
            with self._client.stream(
                "POST",
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                },
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
        except Exception as exc:
            logger.error("Ollama stream error: %s", exc)
            yield f"[ERROR: {exc}]"

    def close(self) -> None:
        self._client.close()
