from __future__ import annotations

import sys
import pytest
from cto.cli import _parse_response

_has_console = sys.stdin.isatty() and sys.stdout.isatty()


@pytest.mark.skipif(not _has_console, reason="No console (headless environment)")
class TestCreatePromptSession:
    def test_creates_session(self):
        from cto.cli import _create_prompt_session
        session = _create_prompt_session()
        assert session is not None
        assert session.history is not None

    def test_session_has_key_bindings(self):
        from cto.cli import _create_prompt_session
        session = _create_prompt_session()
        assert session.key_bindings is not None


class TestParseResponseMultiLine:
    def test_multiline_json(self):
        raw = '{\n  "action": "read_file",\n  "args": {"path": "test.py"}\n}'
        result = _parse_response(raw)
        assert result["action"] == "read_file"

    def test_multiline_in_codeblock(self):
        raw = '```json\n{\n  "action": "search_code",\n  "args": {"pattern": "TODO"}\n}\n```'
        result = _parse_response(raw)
        assert result["action"] == "search_code"

    def test_pasted_multiline_text(self):
        raw = "Review the repository\nIdentify three problems\nPropose improvements"
        result = _parse_response(raw)
        assert result["action"] is None
        assert "Review" in result["response"]
