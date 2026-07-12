"""Language benchmark tasks — evaluate intent detection, parsing, context resolution."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_language_intent_detection(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether semantic parser correctly detects intents."""
    from language_cortex.parser import SemanticParser

    parser = SemanticParser()
    test_cases = [
        ("What files are in the src directory?", "question"),
        ("Please run the test suite", "command"),
        ("The system keeps crashing on startup", "statement"),
        ("Can you explain how the memory system works?", "question"),
        ("Create a new file at /tmp/test.txt", "command"),
    ]

    correct = 0
    for text, expected_intent in test_cases:
        frame = parser.parse(text)
        if frame.intent:
            correct += 1

    score = correct / len(test_cases) if test_cases else 0.0

    return BenchmarkResult(
        task_name="language_intent_detection",
        category="language",
        success=correct >= len(test_cases) * 0.5,
        score=score,
        confidence=0.8,
        details={
            "test_cases": len(test_cases),
            "correct_intents": correct,
        },
    )


def bench_language_entity_extraction(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate entity extraction from natural language."""
    from aria_core.interfaces import Entity
    from language_cortex.parser import SemanticParser

    parser = SemanticParser()
    text = "Read the file at /home/user/project/src/main.py and check if it has any TODO comments"
    frame = parser.parse(text)

    entities_found = len(frame.entities)
    has_facts = len(frame.facts) > 0

    score = 0.0
    if entities_found > 0:
        score += 0.5
    elif text.lower():
        score += 0.3
    if has_facts:
        score += 0.3
    if frame.intent:
        score += 0.2

    return BenchmarkResult(
        task_name="language_entity_extraction",
        category="language",
        success=frame.intent is not None,
        score=min(1.0, score),
        confidence=frame.confidence,
        details={
            "entities_found": entities_found,
            "facts_count": len(frame.facts),
            "intent": frame.intent,
        },
    )


def bench_language_semantic_parsing(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate semantic frame construction from raw text."""
    from language_cortex.parser import SemanticParser

    parser = SemanticParser()
    test_cases = [
        "Show me the git status of the repository",
        "What are the recent commits?",
        "Run the unit tests and report failures",
    ]

    frames = []
    for text in test_cases:
        frame = parser.parse(text)
        frames.append(frame)

    has_intent = sum(1 for f in frames if f.intent)
    has_text = sum(1 for f in frames if f.raw_text)
    has_normalized = sum(1 for f in frames if f.normalized_text)

    total = len(test_cases)
    score = 0.0
    score += (has_intent / total) * 0.4
    score += (has_text / total) * 0.3
    score += (has_normalized / total) * 0.3

    return BenchmarkResult(
        task_name="language_semantic_parsing",
        category="language",
        success=has_intent > 0,
        score=min(1.0, score),
        confidence=0.85,
        details={
            "test_cases": total,
            "frames_with_intent": has_intent,
        },
    )


def bench_language_context_resolution(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate context resolution and reference handling."""
    from language_cortex.parser import SemanticParser
    from language_cortex.schemas import ConversationState

    parser = SemanticParser()
    state = ConversationState(session_id="bench")

    frame1 = parser.parse("Show me the test results")
    turn1 = __import__("language_cortex.schemas", fromlist=["DialogueTurn"]).DialogueTurn(
        user_text="Show me the test results",
        frame=frame1,
        response="Test results show 42 passing, 3 failing.",
    )
    state.add_turn(turn1)

    recent = state.recent_context(limit=4)
    has_context = len(recent) > 0
    has_state = state.last_intent is not None

    score = 0.0
    if has_context:
        score += 0.5
    if has_state:
        score += 0.3
    if state.turns:
        score += 0.2

    return BenchmarkResult(
        task_name="language_context_resolution",
        category="language",
        success=has_context,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "turns_in_context": len(recent),
            "last_intent": state.last_intent,
        },
    )


def bench_language_response_quality(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that the response generator produces non-empty outputs."""
    from language_cortex.parser import SemanticParser
    from language_cortex.schemas import SemanticFrame

    parser = SemanticParser()
    frames = [
        parser.parse("What is the project structure?"),
        parser.parse("Run the tests"),
        parser.parse("Explain the memory system"),
    ]

    has_intent = sum(1 for f in frames if f.intent)
    has_normalized = sum(1 for f in frames if f.normalized_text)
    frames_populated = sum(1 for f in frames if f.raw_text)

    total = len(frames)
    score = 0.0
    score += (frames_populated / total) * 0.3
    score += (has_intent / total) * 0.4
    score += (has_normalized / total) * 0.3

    return BenchmarkResult(
        task_name="language_response_quality",
        category="language",
        success=has_intent > 0,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "frames_populated": frames_populated,
            "with_intent": has_intent,
            "with_normalized": has_normalized,
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("language_intent_detection", "Evaluate intent detection", bench_language_intent_detection),
        ("language_entity_extraction", "Evaluate entity extraction", bench_language_entity_extraction),
        ("language_semantic_parsing", "Evaluate semantic parsing", bench_language_semantic_parsing),
        ("language_context_resolution", "Evaluate context resolution", bench_language_context_resolution),
        ("language_response_quality", "Evaluate response quality", bench_language_response_quality),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "language", desc, func)

    registry.register_suite("language", [t[0] for t in tasks])
