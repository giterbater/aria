from ..interfaces import LanguageModel

class MockModel:
    """A simple mock language model that returns an echo or a canned response."""
    def __init__(self, **kwargs):
        # ignore any config
        pass

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        # Simple echo: return the prompt prefixed with "Echo: "
        return f"Echo: {prompt[:100]}"

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ):
        # Yield each character as a token for demo
        for ch in f"Echo: {prompt}":
            yield ch
            # small delay not needed