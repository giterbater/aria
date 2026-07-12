"""Trading skill — exchange resources between agents."""

from __future__ import annotations

from typing import Any

from aria_core.skills.interfaces import SkillMeta, SkillResult


class TradingSkill:
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="trading",
            description="Trade resources with other agents",
            category="village",
            tags=["trading", "merchant", "exchange"],
            timeout_seconds=5.0,
        )

    def execute(self, **kwargs: Any) -> SkillResult:
        offer_resource = kwargs.get("offer_resource", "")
        offer_amount = kwargs.get("offer_amount", 0)
        request_resource = kwargs.get("request_resource", "")
        request_amount = kwargs.get("request_amount", 0)

        if not offer_resource or not request_resource:
            return SkillResult.fail("Must specify offer and request resources")
        if offer_amount <= 0 or request_amount <= 0:
            return SkillResult.fail("Amounts must be positive")

        return SkillResult.ok(
            output=f"Traded {offer_amount} {offer_resource} for {request_amount} {request_resource}",
            offer_resource=offer_resource,
            offer_amount=offer_amount,
            request_resource=request_resource,
            request_amount=request_amount,
        )

    def validate(self, **kwargs: Any) -> bool:
        return bool(kwargs.get("offer_resource")) and bool(kwargs.get("request_resource"))

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.ok(output="Trade rolled back")
