from __future__ import annotations

import pytest
from memory_ext.project_memory import ProjectMemorySQLite


@pytest.fixture
def db():
    mem = ProjectMemorySQLite(":memory:")
    yield mem
    mem.close()


class TestProjectMemoryDecisions:
    def test_store_and_retrieve(self, db):
        db.store_decision({"action": "edit", "files": ["a.py"], "outcome": "success"})
        decisions = db.get_recent_decisions(limit=5)
        assert len(decisions) == 1
        assert decisions[0]["value"]["action"] == "edit"

    def test_multiple_decisions_ordered(self, db):
        db.store_decision({"action": "first"})
        db.store_decision({"action": "second"})
        decisions = db.get_recent_decisions()
        assert decisions[0]["value"]["action"] == "second"
        assert decisions[1]["value"]["action"] == "first"

    def test_limit(self, db):
        for i in range(10):
            db.store_decision({"action": f"action_{i}"})
        decisions = db.get_recent_decisions(limit=3)
        assert len(decisions) == 3


class TestProjectMemoryRoadmap:
    def test_store_and_retrieve(self, db):
        db.store_roadmap_item({"id": "M1", "title": "Foundation", "status": "pending"})
        roadmap = db.get_roadmap()
        assert len(roadmap) == 1
        assert roadmap[0]["id"] == "M1"

    def test_update_status(self, db):
        db.store_roadmap_item({"id": "M1", "title": "Foundation", "status": "pending"})
        db.update_roadmap_status("M1", "in_progress")
        roadmap = db.get_roadmap()
        assert roadmap[0]["value"]["status"] == "in_progress"


class TestProjectMemorySpecialists:
    def test_store_profile(self, db):
        db.store_specialist_profile("mimo", ["core", "architecture"])
        profiles = db.get_specialist_profiles()
        assert "mimo" in profiles
        assert "core" in profiles["mimo"]

    def test_record_outcome(self, db):
        db.store_specialist_profile("mimo", ["core"])
        db.record_specialist_outcome("mimo", True)
        db.record_specialist_outcome("mimo", True)
        db.record_specialist_outcome("mimo", False)
        profiles = db.get_specialist_profiles()
        # The profile should have successes and failures
        # (values are stored in the JSON blob)


class TestProjectMemoryCodebaseFacts:
    def test_store_and_retrieve(self, db):
        db.store_codebase_fact("entry_point", "main.py")
        db.store_codebase_fact("test_runner", "pytest")
        facts = db.get_codebase_facts()
        assert len(facts) == 2

    def test_query_filter(self, db):
        db.store_codebase_fact("entry_point", "main.py")
        db.store_codebase_fact("test_runner", "pytest")
        facts = db.get_codebase_facts(query="main")
        assert len(facts) == 1
        assert facts[0][0] == "entry_point"


class TestProjectMemoryDirectoryCreation:
    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / ".aria" / "project_memory.db"
        mem = ProjectMemorySQLite(str(nested))
        try:
            assert nested.parent.exists()
            mem.store_decision({"action": "test"})
            decisions = mem.get_recent_decisions()
            assert len(decisions) == 1
        finally:
            mem.close()

    def test_deeply_nested_path(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "db.sqlite"
        mem = ProjectMemorySQLite(str(deep))
        try:
            assert deep.parent.exists()
            mem.store_codebase_fact("key", "value")
            facts = mem.get_codebase_facts()
            assert len(facts) == 1
        finally:
            mem.close()

    def test_memory_db_path_still_works(self):
        mem = ProjectMemorySQLite(":memory:")
        try:
            mem.store_decision({"action": "test"})
            assert len(mem.get_recent_decisions()) == 1
        finally:
            mem.close()
