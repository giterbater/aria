from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from language_cortex.models.ollama import OllamaModel


class TestOllamaModel:
    def test_generate_sync(self):
        model = OllamaModel(base_url="http://localhost:11434", model="test")
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "hello world"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("language_cortex.models.ollama.httpx.Client", return_value=mock_client):
            result = model.generate_sync("test prompt")
            assert result == "hello world"

    def test_generate_sync_error(self):
        import httpx
        model = OllamaModel(base_url="http://localhost:11434", model="test")
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("language_cortex.models.ollama.httpx.Client", return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                model.generate_sync("test prompt")

    def test_model_attributes(self):
        model = OllamaModel(base_url="http://example.com:11434", model="mymodel")
        assert model._base_url == "http://example.com:11434"
        assert model._model == "mymodel"

    def test_generate_async_delegates_to_sync(self):
        model = OllamaModel(base_url="http://localhost:11434", model="test")
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "async result"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("language_cortex.models.ollama.httpx.Client", return_value=mock_client):
            import asyncio
            result = asyncio.run(model.generate("test prompt"))
            assert result == "async result"

    def test_close_is_noop(self):
        model = OllamaModel()
        import asyncio
        asyncio.run(model.close())
