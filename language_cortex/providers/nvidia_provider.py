from __future__ import annotations

import logging
import os
import time

from .base import LanguageProvider, LanguageResponse, ProviderConfig

logger = logging.getLogger("aria.providers.nvidia")


class NvidiaProvider:
    """NVIDIA NIM provider via OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._model = config.model or "nvidia/nemotron-3-ultra-550b-a55b"
        self._api_key = config.api_key or os.environ.get("NVIDIA_API_KEY", "")
        self._base_url = config.base_url or "https://integrate.api.nvidia.com/v1"
        self._client = None

    @property
    def name(self) -> str:
        return "nvidia"

    @property
    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=self._config.timeout,
                max_retries=0,
            )
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LanguageResponse:
        if not self._api_key:
            return LanguageResponse.fail("NVIDIA_API_KEY not set", self.name)

        t0 = time.monotonic()
        try:
            client = self._get_client()
            completion = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                top_p=self._config.top_p,
                max_tokens=max_tokens,
                stream=False,
            )
            latency = (time.monotonic() - t0) * 1000
            text = completion.choices[0].message.content or ""
            usage = completion.usage
            return LanguageResponse(
                text=text,
                model=self._model,
                provider=self.name,
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
                latency_ms=round(latency, 1),
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            logger.error("NVIDIA API error: %s", exc)
            return LanguageResponse.fail(f"NVIDIA API error: {exc}", self.name)

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        if not self._api_key:
            yield f"[ERROR: NVIDIA_API_KEY not set]"
            return

        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                top_p=self._config.top_p,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.error("NVIDIA stream error: %s", exc)
            yield f"[ERROR: {exc}]"

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
