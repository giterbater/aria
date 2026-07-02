from __future__ import annotations

import time

from ..interfaces import Skill, SkillResult, SkillMeta


class WebResearchSkill:
    """Web research: fetch URLs, search, summarize."""

    def __init__(self) -> None:
        pass

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="web_research",
            description="Fetch and analyze web content",
            category="research",
            tags=["web", "search", "fetch", "research", "url"],
            timeout_seconds=30.0,
        )

    def validate(self, action: str = "fetch", **kwargs) -> bool:
        if action == "fetch":
            return bool(kwargs.get("url"))
        if action == "summarize":
            return bool(kwargs.get("text"))
        return False

    def execute(self, action: str = "fetch", **kwargs) -> SkillResult:
        t0 = time.monotonic()
        try:
            if action == "fetch":
                result = self._fetch(kwargs["url"])
            elif action == "summarize":
                result = self._summarize(kwargs["text"])
            else:
                result = SkillResult.fail(f"Unknown web action: {action}")

            elapsed = (time.monotonic() - t0) * 1000
            result.metadata["duration_ms"] = round(elapsed, 1)
            return result
        except Exception as exc:
            return SkillResult.fail(f"Web research error: {exc}")

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.fail("Web research has no rollback")

    def _fetch(self, url: str) -> SkillResult:
        try:
            import httpx
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            return SkillResult.ok(
                output=resp.text[:5000],
                status_code=resp.status_code,
                url=url,
                content_length=len(resp.text),
            )
        except ImportError:
            return SkillResult.fail("httpx not installed")
        except Exception as exc:
            return SkillResult.fail(f"Fetch failed: {exc}")

    def _summarize(self, text: str) -> SkillResult:
        sentences = text.split(". ")
        summary = ". ".join(sentences[:3]) + "." if len(sentences) > 3 else text
        return SkillResult.ok(output=summary, original_length=len(text), summary_length=len(summary))
