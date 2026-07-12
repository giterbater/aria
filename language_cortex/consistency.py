from __future__ import annotations

import re

from .schemas import ConsistencyReport, ResponsePlan, SemanticFrame


class ConsistencyChecker:
    """Check and repair language-level response issues."""

    _PRONOUN_RE = re.compile(r"\b(it|that|this|they|them|he|she|him)\b", re.I)

    def check(self, draft: str, frame: SemanticFrame, context: dict, plan: ResponsePlan) -> ConsistencyReport:
        report = ConsistencyReport()
        if frame.references and not context.get("resolved_reference"):
            report.missing_references.extend(frame.references)
            report.unresolved_pronouns.extend(frame.references)
        if plan.missing_information and "?" not in draft:
            report.incomplete_answers.append("Response does not ask for required clarification")
        if plan.citations_needed and not any(mark in draft.lower() for mark in ("source", "according", "http", "citation")):
            report.unsupported_claims.append("Citations were requested but not present")
        self._check_terminology(draft, frame, report)
        self._check_contradictions(draft, context, report)
        return report

    def improve(self, draft: str, report: ConsistencyReport, plan: ResponsePlan) -> str:
        if report.passed:
            return draft
        if report.unresolved_pronouns or plan.follow_up_questions:
            question = plan.follow_up_questions[0] if plan.follow_up_questions else "What are you referring to?"
            return question
        if report.unsupported_claims:
            return draft.rstrip() + " I would need a source check before treating that as verified."
        if report.incomplete_answers and plan.follow_up_questions:
            return plan.follow_up_questions[0]
        return draft

    @staticmethod
    def _check_terminology(draft: str, frame: SemanticFrame, report: ConsistencyReport) -> None:
        for entity in frame.entities:
            if entity.label in {"APP", "PERSON"} and entity.text.lower() not in draft.lower():
                report.inconsistent_terminology.append(f"Expected mention of {entity.text}")

    @staticmethod
    def _check_contradictions(draft: str, context: dict, report: ConsistencyReport) -> None:
        lower = draft.lower()
        for fact in context.get("relevant_facts", []):
            if " not " in lower and fact.lower() in lower:
                report.contradictions.append(f"Potential contradiction with memory: {fact}")
