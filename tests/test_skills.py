from __future__ import annotations

import pytest
from aria_core.skills import Skill, SkillResult, SkillMeta, SkillRegistry, SkillRouter, SkillManager
from aria_core.skills.interfaces import SkillResult as SR


class MockSkill:
    def __init__(self, name="test_skill", description="test", tags=None, deps=None, category="general"):
        self._meta = SkillMeta(
            name=name, description=description, category=category,
            tags=tags or [], dependencies=deps or [],
        )

    @property
    def meta(self):
        return self._meta

    def execute(self, **kwargs) -> SkillResult:
        return SkillResult.ok(output=f"executed {self.meta.name}", skill=self.meta.name)

    def validate(self, **kwargs) -> bool:
        return True

    def rollback(self, context) -> SkillResult:
        return SkillResult.ok(output="rolled back")


class FailingSkill(MockSkill):
    def execute(self, **kwargs) -> SkillResult:
        return SkillResult.fail("skill failed")


class ValidationSkill(MockSkill):
    def validate(self, **kwargs) -> bool:
        return "required_key" in kwargs


class TestSkillResult:
    def test_ok(self):
        r = SR.ok(output="done")
        assert r.success is True
        assert r.output == "done"

    def test_fail(self):
        r = SR.fail("error msg")
        assert r.success is False
        assert "error msg" in r.errors


class TestSkillRegistry:
    def test_register_and_get(self):
        reg = SkillRegistry()
        skill = MockSkill()
        reg.register(skill)
        assert reg.get("test_skill") is skill

    def test_get_disabled(self):
        reg = SkillRegistry()
        skill = MockSkill()
        reg.register(skill)
        reg.disable("test_skill")
        assert reg.get("test_skill") is None

    def test_enable_disable(self):
        reg = SkillRegistry()
        skill = MockSkill()
        reg.register(skill)
        reg.disable("test_skill")
        assert reg.enable("test_skill") is True
        assert reg.get("test_skill") is skill

    def test_unregister(self):
        reg = SkillRegistry()
        skill = MockSkill()
        reg.register(skill)
        reg.unregister("test_skill")
        assert reg.get("test_skill") is None

    def test_list_skills(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="a"))
        reg.register(MockSkill(name="b"))
        assert len(reg.list_skills()) == 2

    def test_list_by_category(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="a", category="file"))
        reg.register(MockSkill(name="b", category="git"))
        assert len(reg.list_by_category("file")) == 1

    def test_find_by_tags(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="a", tags=["read", "file"]))
        reg.register(MockSkill(name="b", tags=["write", "file"]))
        found = reg.find_by_tags(["read"])
        assert len(found) == 1
        assert found[0].meta.name == "a"

    def test_find_by_capability(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="file_reader", description="Read files from disk"))
        found = reg.find_by_capability("read files")
        assert len(found) == 1

    def test_count(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="a"))
        reg.register(MockSkill(name="b"))
        assert reg.count == 2
        reg.disable("a")
        assert reg.count == 1


class TestSkillRouter:
    def test_resolve_by_name(self):
        reg = SkillRegistry()
        skill = MockSkill(name="file_reader", description="read files")
        reg.register(skill)
        router = SkillRouter(reg)
        found = router.resolve("read files")
        assert len(found) == 1

    def test_resolve_no_match(self):
        reg = SkillRegistry()
        router = SkillRouter(reg)
        found = router.resolve("quantum computing")
        assert len(found) == 0

    def test_order_by_dependencies(self):
        reg = SkillRegistry()
        a = MockSkill(name="a", deps=[])
        b = MockSkill(name="b", deps=["a"])
        c = MockSkill(name="c", deps=["b"])
        reg.register(a)
        reg.register(b)
        reg.register(c)
        router = SkillRouter(reg)
        ordered = router.order_by_dependencies([c, a, b])
        names = [s.meta.name for s in ordered]
        assert names.index("a") < names.index("b")
        assert names.index("b") < names.index("c")

    def test_can_parallel(self):
        reg = SkillRegistry()
        a = MockSkill(name="a", deps=[])
        b = MockSkill(name="b", deps=[])
        c = MockSkill(name="c", deps=["a"])
        reg.register(a)
        reg.register(b)
        reg.register(c)
        router = SkillRouter(reg)
        batches = router.can_parallel([a, b, c])
        assert len(batches) == 2
        batch_names = [[s.meta.name for s in b] for b in batches]
        assert ["a", "b"] in batch_names or ["b", "a"] in batch_names

    def test_execute(self):
        reg = SkillRegistry()
        reg.register(MockSkill(name="reader", description="read files"))
        router = SkillRouter(reg)
        result = router.execute("read files")
        assert result.success is True

    def test_execute_no_skills(self):
        reg = SkillRegistry()
        router = SkillRouter(reg)
        result = router.execute("nothing matches")
        assert result.success is False


class TestSkillManager:
    def test_register_and_execute(self):
        mgr = SkillManager()
        mgr.register(MockSkill(name="echo", description="echo back"))
        result = mgr.execute_skill("echo")
        assert result.success is True
        assert result.output == "executed echo"

    def test_execute_unknown_skill(self):
        mgr = SkillManager()
        result = mgr.execute_skill("nonexistent")
        assert result.success is False

    def test_execute_task(self):
        mgr = SkillManager()
        mgr.register(MockSkill(name="file_tool", description="read files"))
        result = mgr.execute("read files")
        assert result.success is True

    def test_history(self):
        mgr = SkillManager()
        mgr.register(MockSkill(name="a", description="test a"))
        mgr.execute_skill("a")
        mgr.execute_skill("a")
        assert len(mgr.get_history()) == 2

    def test_summary(self):
        mgr = SkillManager()
        assert "No skills" in mgr.summary()
        mgr.register(MockSkill(name="a", description="test"))
        mgr.execute_skill("a")
        assert "1" in mgr.summary()

    def test_failing_skill(self):
        mgr = SkillManager()
        mgr.register(FailingSkill(name="fail", description="fails"))
        result = mgr.execute_skill("fail")
        assert result.success is False
        assert "skill failed" in result.errors

    def test_validation_blocks(self):
        mgr = SkillManager()
        mgr.register(ValidationSkill(name="val", description="needs key"))
        result = mgr.execute_skill("val")
        assert result.success is False
        assert "Validation failed" in result.errors[0]

    def test_validation_passes(self):
        mgr = SkillManager()
        mgr.register(ValidationSkill(name="val", description="needs key"))
        result = mgr.execute_skill("val", required_key="present")
        assert result.success is True
