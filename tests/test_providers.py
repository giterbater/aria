from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from language_cortex.providers.base import LanguageProvider, LanguageResponse, ProviderConfig
from language_cortex.providers.ollama_provider import OllamaProvider
from language_cortex.providers.nvidia_provider import NvidiaProvider
from language_cortex.providers.factory import create_provider
from language_cortex.providers.failover import FailoverProvider


# ── LanguageResponse ──────────────────────────────────────────────

class TestLanguageResponse:
    def test_success_response(self):
        resp = LanguageResponse(text="hello", model="m", provider="p")
        assert resp.success is True
        assert resp.text == "hello"

    def test_fail_response(self):
        resp = LanguageResponse.fail("error msg", "test_provider")
        assert resp.success is False
        assert resp.error == "error msg"
        assert resp.provider == "test_provider"


# ── ProviderConfig ────────────────────────────────────────────────

class TestProviderConfig:
    def test_defaults(self):
        cfg = ProviderConfig()
        assert cfg.provider == "ollama"
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 2048

    def test_nvidia_config(self):
        cfg = ProviderConfig(provider="nvidia", model="nvidia/test", api_key="nv-xxx")
        assert cfg.provider == "nvidia"
        assert cfg.api_key == "nv-xxx"


# ── Factory ───────────────────────────────────────────────────────

class TestFactory:
    def test_create_ollama(self):
        cfg = ProviderConfig(provider="ollama", base_url="http://localhost:11434")
        provider = create_provider(cfg)
        assert isinstance(provider, OllamaProvider)
        assert provider.name == "ollama"

    def test_create_nvidia(self):
        cfg = ProviderConfig(provider="nvidia", api_key="test-key")
        provider = create_provider(cfg)
        assert isinstance(provider, NvidiaProvider)
        assert provider.name == "nvidia"

    def test_unknown_provider(self):
        cfg = ProviderConfig(provider="unknown")
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider(cfg)


# ── OllamaProvider ────────────────────────────────────────────────

class TestOllamaProvider:
    def test_generate_success(self):
        cfg = ProviderConfig(provider="ollama", base_url="http://localhost:11434")
        provider = OllamaProvider(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "hello world", "eval_count": 10}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, "post", return_value=mock_response):
            result = provider.generate("test prompt")
            assert result.success is True
            assert result.text == "hello world"
            assert result.provider == "ollama"
            assert result.tokens_out == 10

    def test_generate_http_error(self):
        import httpx
        cfg = ProviderConfig(provider="ollama")
        provider = OllamaProvider(cfg)

        with patch.object(provider._client, "post", side_effect=httpx.ConnectError("refused")):
            result = provider.generate("test")
            assert result.success is False
            assert "Ollama" in result.error

    def test_generate_generic_error(self):
        cfg = ProviderConfig(provider="ollama")
        provider = OllamaProvider(cfg)

        with patch.object(provider._client, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("test")
            assert result.success is False

    def test_close(self):
        cfg = ProviderConfig(provider="ollama")
        provider = OllamaProvider(cfg)
        with patch.object(provider._client, "close") as mock_close:
            provider.close()
            mock_close.assert_called_once()


# ── NvidiaProvider ────────────────────────────────────────────────

class TestNvidiaProvider:
    def test_generate_success(self):
        cfg = ProviderConfig(provider="nvidia", api_key="nv-test")
        provider = NvidiaProvider(cfg)

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "nvidia response"
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 5
        mock_completion.usage.completion_tokens = 15

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = provider.generate("test prompt")
            assert result.success is True
            assert result.text == "nvidia response"
            assert result.provider == "nvidia"
            assert result.tokens_in == 5
            assert result.tokens_out == 15

    def test_generate_no_api_key(self):
        cfg = ProviderConfig(provider="nvidia", api_key="")

        with patch.dict("os.environ", {}, clear=True):
            provider = NvidiaProvider(cfg)
            result = provider.generate("test")
            assert result.success is False
            assert "NVIDIA_API_KEY" in result.error

    def test_generate_api_error(self):
        cfg = ProviderConfig(provider="nvidia", api_key="nv-test")
        provider = NvidiaProvider(cfg)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = provider.generate("test")
            assert result.success is False
            assert "NVIDIA" in result.error

    def test_stream_success(self):
        cfg = ProviderConfig(provider="nvidia", api_key="nv-test")
        provider = NvidiaProvider(cfg)

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [chunk1, chunk2]

        with patch.object(provider, "_get_client", return_value=mock_client):
            tokens = list(provider.generate_stream("test"))
            assert tokens == ["hello", " world"]

    def test_stream_no_api_key(self):
        cfg = ProviderConfig(provider="nvidia", api_key="")

        with patch.dict("os.environ", {}, clear=True):
            provider = NvidiaProvider(cfg)
            tokens = list(provider.generate_stream("test"))
            assert len(tokens) == 1
            assert "NVIDIA_API_KEY" in tokens[0]


# ── FailoverProvider ──────────────────────────────────────────────

class TestFailoverProvider:
    def test_primary_success(self):
        primary = MagicMock()
        primary.name = "primary"
        primary.generate.return_value = LanguageResponse(text="ok", success=True)

        fallback = MagicMock()
        fallback.name = "fallback"

        fp = FailoverProvider(primary=primary, fallback=fallback)
        result = fp.generate("test")
        assert result.success is True
        assert result.text == "ok"
        fallback.generate.assert_not_called()

    def test_primary_fail_fallback_success(self):
        primary = MagicMock()
        primary.name = "primary"
        primary.generate.return_value = LanguageResponse.fail("error", "primary")

        fallback = MagicMock()
        fallback.name = "fallback"
        fallback.generate.return_value = LanguageResponse(text="fallback ok", success=True)

        fp = FailoverProvider(primary=primary, fallback=fallback, max_retries=0)
        result = fp.generate("test")
        assert result.success is True
        assert result.text == "fallback ok"

    def test_all_fail(self):
        primary = MagicMock()
        primary.name = "primary"
        primary.generate.return_value = LanguageResponse.fail("error1", "primary")

        fallback = MagicMock()
        fallback.name = "fallback"
        fallback.generate.return_value = LanguageResponse.fail("error2", "fallback")

        fp = FailoverProvider(primary=primary, fallback=fallback, max_retries=0)
        result = fp.generate("test")
        assert result.success is False
        assert "All providers failed" in result.error

    def test_no_fallback_all_fail(self):
        primary = MagicMock()
        primary.name = "primary"
        primary.generate.return_value = LanguageResponse.fail("error", "primary")

        fp = FailoverProvider(primary=primary, fallback=None, max_retries=0)
        result = fp.generate("test")
        assert result.success is False
        assert "Primary provider primary failed" in result.error

    def test_retry_on_primary_failure(self):
        primary = MagicMock()
        primary.name = "primary"
        primary.generate.side_effect = [
            LanguageResponse.fail("err1", "primary"),
            LanguageResponse.fail("err2", "primary"),
            LanguageResponse(text="ok after retry", success=True),
        ]

        fp = FailoverProvider(primary=primary, fallback=None, max_retries=2, retry_delay=0)
        result = fp.generate("test")
        assert result.success is True
        assert primary.generate.call_count == 3

    def test_close(self):
        primary = MagicMock()
        fallback = MagicMock()
        fp = FailoverProvider(primary=primary, fallback=fallback)
        fp.close()
        primary.close.assert_called_once()
        fallback.close.assert_called_once()


# ── CTOConfig provider fields ─────────────────────────────────────

class TestCTOConfigProviders:
    def test_provider_field(self):
        from cto.config import CTOConfig
        cfg = CTOConfig(repo_path=".", provider="nvidia", model="nvidia/test")
        assert cfg.provider == "nvidia"
        assert cfg.model == "nvidia/test"

    def test_resolve_api_key_from_config(self):
        from cto.config import CTOConfig
        cfg = CTOConfig(repo_path=".", provider="nvidia", api_key="nv-direct")
        assert cfg.resolve_api_key() == "nv-direct"

    def test_resolve_api_key_from_env(self):
        from cto.config import CTOConfig
        cfg = CTOConfig(repo_path=".", provider="nvidia")
        with patch.dict("os.environ", {"NVIDIA_API_KEY": "nv-env-key"}):
            assert cfg.resolve_api_key() == "nv-env-key"

    def test_resolve_api_key_missing(self):
        from cto.config import CTOConfig
        cfg = CTOConfig(repo_path=".", provider="nvidia")
        with patch.dict("os.environ", {}, clear=True):
            assert cfg.resolve_api_key() == ""
