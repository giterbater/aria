from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from .interfaces import Reflection, Lesson, ReflectionType

logger = logging.getLogger("aria.reflection")


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for LLM calls."""
    def generate(self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3) -> Any: ...


REFLECT_PROMPT = """You are a reflection engine. Analyze what happened and extract lessons.

Action taken: {action}
Result: {result}
Context: {context}

Respond with JSON:
{{
  "reflection_type": "success" | "failure" | "improvement" | "learning",
  "summary": "one-line summary",
  "what_worked": ["list of things that worked"],
  "what_failed": ["list of things that failed"],
  "what_to_improve": ["list of improvements"],
  "lessons": [{{"text": "lesson", "tags": ["tag1"]}}]
}}

Return ONLY the JSON object.
"""


class ReflectionEngine:
    """Reviews outcomes and extracts lessons for future improvement.

    Maintains a history of reflections and provides accumulated
    knowledge for the decision engine.
    """

    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm
        self._reflections: list[Reflection] = []
        self._lessons: list[Lesson] = []

    def reflect(self, action: str, result: str, context: dict | None = None) -> Reflection:
        """Reflect on an action and its result. Returns structured insights."""
        context = context or {}

        if self._llm is not None:
            reflection = self._reflect_with_llm(action, result, context)
        else:
            reflection = self._reflect_stub(action, result, context)

        self._reflections.append(reflection)
        self._lessons.extend(reflection.lessons)
        logger.info(
            "Reflection: %s (%d lessons)",
            reflection.reflection_type.value,
            len(reflection.lessons),
        )
        return reflection

    def get_reflections(self, limit: int = 20) -> list[Reflection]:
        return self._reflections[-limit:]

    def get_lessons(self, tags: list[str] | None = None, limit: int = 50) -> list[Lesson]:
        if tags is None:
            return self._lessons[-limit:]
        tag_set = set(tags)
        return [l for l in self._lessons if tag_set & set(l.tags)][-limit:]

    def get_learned_patterns(self) -> dict[str, int]:
        """Count lesson tags to find recurring patterns."""
        counts: dict[str, int] = {}
        for lesson in self._lessons:
            for tag in lesson.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def summarize(self) -> str:
        """Generate a summary of accumulated reflections."""
        if not self._reflections:
            return "No reflections recorded yet."

        total = len(self._reflections)
        successes = sum(1 for r in self._reflections if r.reflection_type == ReflectionType.SUCCESS)
        failures = sum(1 for r in self._reflections if r.reflection_type == ReflectionType.FAILURE)
        improvements = sum(1 for r in self._reflections if r.reflection_type == ReflectionType.IMPROVEMENT)

        patterns = self.get_learned_patterns()
        top_patterns = list(patterns.items())[:5]

        lines = [
            f"Reflections: {total} total ({successes} success, {failures} failure, {improvements} improvement)",
            f"Lessons learned: {len(self._lessons)}",
        ]
        if top_patterns:
            lines.append("Top patterns: " + ", ".join(f"{k}({v})" for k, v in top_patterns))

        recent = self._reflections[-3:]
        if recent:
            lines.append("Recent insights:")
            for r in recent:
                lines.append(f"  - [{r.reflection_type.value}] {r.summary}")

        return "\n".join(lines)

    def _reflect_with_llm(self, action: str, result: str, context: dict) -> Reflection:
        prompt = REFLECT_PROMPT.format(
            action=action,
            result=result[:1000],
            context=json.dumps(context, default=str)[:500],
        )
        try:
            resp = self._llm.generate(prompt, max_tokens=1024, temperature=0.3)
            text = resp.text if hasattr(resp, "text") else str(resp)
            data = self._parse_response(text)

            if not data:
                return self._reflect_stub(action, result, context)

            rtype = ReflectionType(data.get("reflection_type", "observation"))
            lessons = [
                Lesson(
                    text=l.get("text", ""),
                    reflection_type=rtype,
                    source=action[:100],
                    tags=l.get("tags", []),
                )
                for l in data.get("lessons", [])
            ]

            return Reflection(
                reflection_type=rtype,
                summary=data.get("summary", ""),
                what_worked=data.get("what_worked", []),
                what_failed=data.get("what_failed", []),
                what_to_improve=data.get("what_to_improve", []),
                lessons=lessons,
                context={"action": action, "result": result[:200]},
            )
        except Exception as exc:
            logger.warning("LLM reflection failed: %s", exc)
            return self._reflect_stub(action, result, context)

    def _reflect_stub(self, action: str, result: str, context: dict) -> Reflection:
        """Rule-based fallback reflection."""
        success_indicators = ["success", "ok", "passed", "completed", "done"]
        failure_indicators = ["error", "failed", "exception", "crash", "bug"]

        result_lower = result.lower()
        is_success = any(ind in result_lower for ind in success_indicators)
        is_failure = any(ind in result_lower for ind in failure_indicators)

        if is_failure:
            rtype = ReflectionType.FAILURE
            what_failed = [f"Action '{action}' produced error: {result[:200]}"]
            lessons = [Lesson(text=f"Avoid pattern: {action}", reflection_type=rtype, tags=["failure", "avoid"])]
        elif is_success:
            rtype = ReflectionType.SUCCESS
            what_worked = [f"Action '{action}' succeeded"]
            lessons = [Lesson(text=f"Repeat pattern: {action}", reflection_type=rtype, tags=["success", "repeat"])]
        else:
            rtype = ReflectionType.OBSERVATION
            what_to_improve = [f"Action '{action}' result unclear"]
            lessons = []

        return Reflection(
            reflection_type=rtype,
            summary=f"{rtype.value}: {action[:80]}",
            what_worked=what_worked if is_success else [],
            what_failed=what_failed if is_failure else [],
            what_to_improve=what_to_improve if not is_success and not is_failure else [],
            lessons=lessons,
            context={"action": action, "result": result[:200]},
        )

    def _parse_response(self, text: str) -> dict:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {}
