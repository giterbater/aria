from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import ProviderConfig

if TYPE_CHECKING:
    from .base import LanguageProvider

logger = logging.getLogger("aria.providers.factory")


def create_provider(config: ProviderConfig) -> LanguageProvider:
    """Create a provider instance from config.

    Supports: ollama, nvidia. Extensible for future providers.
    """
    provider_name = config.provider.lower()

    if provider_name == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(config)

    elif provider_name == "nvidia":
        from .nvidia_provider import NvidiaProvider
        return NvidiaProvider(config)

    else:
        raise ValueError(
            f"Unknown provider: {provider_name!r}. "
            f"Supported: ollama, nvidia"
        )
