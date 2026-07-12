from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from delegation.interfaces import SpecialistRequest, SpecialistResponse
from delegation.subprocess_agent import SubprocessAgent
from delegation.manager import SpecialistManager


class TestSpecialistRequest:
    def test_frozen(self):
        req = SpecialistRequest(
            specialist_name="mimo",
            task_description="fix bug",
        )
        assert req.specialist_name == "mimo"
        with pytest.raises(AttributeError):
            req.specialist_name = "nemotron"


class TestSpecialistResponse:
    def test_defaults(self):
        resp = SpecialistResponse(specialist_name="mimo", status="success", output="done")
        assert resp.files_modified == []
        assert resp.diff == ""
        assert resp.reasoning == ""


class TestSubprocessAgent:
    def test_spawn_success(self):
        agent = SubprocessAgent(timeout=5)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "status": "success",
            "output": "done",
            "summary": "fixed it",
            "files_modified": ["a.py"],
        })
        mock_result.stderr = ""

        with patch("delegation.subprocess_agent.subprocess.run", return_value=mock_result):
            req = SpecialistRequest(
                specialist_name="mimo",
                task_description="fix the bug",
            )
            resp = agent.spawn(req)
            assert resp.status == "success"
            assert resp.files_modified == ["a.py"]

    def test_spawn_failure(self):
        agent = SubprocessAgent(timeout=5)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error occurred"

        with patch("delegation.subprocess_agent.subprocess.run", return_value=mock_result):
            req = SpecialistRequest(
                specialist_name="mimo",
                task_description="fix the bug",
            )
            resp = agent.spawn(req)
            assert resp.status == "failed"

    def test_spawn_invalid_json(self):
        agent = SubprocessAgent(timeout=5)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        mock_result.stderr = ""

        with patch("delegation.subprocess_agent.subprocess.run", return_value=mock_result):
            req = SpecialistRequest(
                specialist_name="mimo",
                task_description="fix the bug",
            )
            resp = agent.spawn(req)
            assert resp.status == "failed"


class TestSpecialistManager:
    def test_select_specialist_core(self):
        manager = SpecialistManager()
        name = manager.select_specialist("implement a new data structure for memory")
        assert name == "mimo"

    def test_select_specialist_testing(self):
        manager = SpecialistManager()
        name = manager.select_specialist("write unit tests for the input pipeline")
        assert name == "nemotron"

    def test_select_specialist_default(self):
        manager = SpecialistManager()
        name = manager.select_specialist("do something random")
        assert name == "mimo"
