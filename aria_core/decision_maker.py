# aria_core/decision_maker.py
"""
Decision maker that reasons over:
  * the current observation (StructuredInput)
  * working/episodic/semantic memory (via MemorySystemProtocol)
  * active goals (via GoalManager)
  * memory influence signals (via MemoryInfluenceEngine)

It selects an action type and builds a payload that the Output Planner
will later turn into a prompt for the Language Cortex.
"""

from __future__ import annotations

import datetime
import math
from typing import Any, List, Tuple

from aria_core.interfaces import StructuredInput, ARIDecision
from aria_core.memory.interfaces import MemorySystemProtocol
from aria_core.memory.models import WorkingMemoryItem, EpisodicItem, SemanticItem
from aria_core.memory.influence import MemoryInfluenceEngine, InfluenceSignal
from .goals import Goal, GoalManager


def _token_set(text: str) -> set[str]:
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class SimpleDecisionMaker:
    """
    Cognitive core that uses memory, goals, and influence signals to score
    possible actions and pick the best one.
    
    The scoring combines:
    1. Intent-action alignment (rule-based)
    2. Emotional salience (empathetic response)
    3. Memory relevance (past similar episodes)
    4. Goal alignment (active goals)
    5. **Memory influence** (learned preferences from experience)
    
    The memory influence is the key developmental component: it allows
    the agent to learn from repeated successes and failures, creating
    behavioral biases that emerge from experience.
    """

    # -----------------------------------------------------------------
    # Action catalogue – extend as your system grows
    # -----------------------------------------------------------------
    _ACTION_TYPES = ("inform", "warn", "execute", "query")

    def __init__(
        self,
        memory: MemorySystemProtocol,
        goals: GoalManager,
        *,
        importance_decay_per_day: float = 0.1,
        recency_half_life_hours: float = 12.0,
        influence_weight: float = 0.4,
    ) -> None:
        self._memory = memory
        self._goals = goals
        self._importance_decay_per_day = importance_decay_per_day
        self._recency_lambda = math.log(2) / recency_half_life_hours  # per hour
        self._influence_weight = influence_weight
        
        # Initialize influence engine
        self._influence = MemoryInfluenceEngine(
            memory,
            min_episodes_for_pattern=3,
            recency_half_life_days=7.0,
        )
        
        # Cache influence signals (updated periodically)
        self._influence_cache: List[InfluenceSignal] = []
        self._influence_cache_age: int = 0
        self._influence_cache_interval: int = 10  # recompute every N decisions

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    async def decide(self, structured_input: StructuredInput) -> ARIDecision:
        """Main entry point – returns a decision based on all available
        sources of information, including memory influence."""
        # 1️⃣ Store perception in working memory (for future relevance)
        wm_item = WorkingMemoryItem(
            structured_input=structured_input,
            importance=0.5,  # seed importance; will be updated by memory later
        )
        self._memory.store_working(wm_item)

        # 2️⃣ Retrieve relevant memories (working + episodic + semantic)
        cue = getattr(structured_input, "raw_text", "")
        relevant: List[Tuple[Any, float]] = self._memory.retrieve_relevant(
            cue,
            working_weight=0.4,
            episodic_weight=0.4,
            semantic_weight=0.2,
            limit=8,
        )

        # 3️⃣ Retrieve relevant goals
        relevant_goals: List[Goal] = self._goals.relevant_goals(cue, limit=5)

        # 4️⃣ Compute memory influence signals (cached, periodic refresh)
        self._influence_cache_age += 1
        if not self._influence_cache or self._influence_cache_age >= self._influence_cache_interval:
            self._influence_cache = self._influence.compute_influences(limit=10)
            self._influence_cache_age = 0

        # 5️⃣ Score each possible action type (with memory influence)
        scores: dict[str, float] = {}
        for act in self._ACTION_TYPES:
            scores[act] = self._score_action(
                act,
                structured_input,
                relevant,
                relevant_goals,
                self._influence_cache,
            )

        # 6️⃣ Pick the highest‑scoring action (break ties arbitrarily)
        best_action = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_action]

        # 7️⃣ Build a concrete decision payload
        payload = self._build_payload(best_action, structured_input, relevant, relevant_goals)

        # 8️⃣ Optionally adjust tone/priority/urgency/speak based on context
        tone, priority, urgency, speak = self._contextual_modifiers(
            structured_input, relevant, relevant_goals, best_action
        )

        # 9️⃣ Persist the full episode (decision included)
        episodic_item = EpisodicItem(
            structured_input=structured_input,
            decision=ARIDecision(
                action_type=best_action,
                payload=payload,
                tone=tone,
                priority=priority,
                urgency=urgency,
                speak=speak,
            ),
            outcome=None,  # filled later after execution
        )
        self._memory.store_episodic(episodic_item)

        # 🔟 Periodic housekeeping (every N decisions – here we just check size)
        if len(self._memory.get_episodic(limit=1000)) % 7 == 0:
            self._memory.consolidate(importance_threshold=0.7)
            self._memory.forget_low_importance(threshold=0.2)

        # 1️⃣1️⃣ Return the decision
        return ARIDecision(
            action_type=best_action,
            payload=payload,
            tone=tone,
            priority=priority,
            urgency=urgency,
            speak=speak,
        )

    # -----------------------------------------------------------------
    # Scoring helpers
    # -----------------------------------------------------------------
    def _score_action(
        self,
        action: str,
        si: StructuredInput,
        relevant: List[Tuple[Any, float]],
        goals: List[Goal],
        influence_signals: List[InfluenceSignal],
    ) -> float:
        """
        Combine several signals into a single utility for *action*.
        Higher = more likely to be chosen.
        
        Scoring components:
        1. Intent-action alignment (rule-based)
        2. Emotional salience (empathetic response)
        3. Memory relevance (past similar episodes)
        4. Goal alignment (active goals)
        5. **Memory influence** (learned preferences from experience)
        """
        score = 0.0

        # ---- 1. Intent‑action alignment (rule‑based but transparent) ----
        intent = getattr(si, "intent", "statement")
        intent_map = {
            "open_application": {"execute": 1.0, "inform": 0.2},
            "question": {"query": 1.0, "inform": 0.5},
            "statement": {"inform": 0.6},
            # emotional cues boost informative/empathetic responses
        }
        intent_score = intent_map.get(intent, {}).get(action, 0.0)
        score += intent_score * 2.0  # weight

        # ---- 2. Emotional salience (boost informative/empathetic) ----
        emotional_cue = None
        if getattr(si, "entities", None):
            for ent in si.entities:
                if getattr(ent, "label", "") == "EMOTION":
                    emotional_cue = getattr(ent, "text", None)
                    break
        if emotional_cue and action in ("inform", "query"):
            score += 1.0  # encourage empathetic/informative tone

        # ---- 3. Memory relevance – look at past outcomes ----
        # We give a boost if similar past episodes led to a successful
        # outcome (here we approximate success by high importance).
        mem_bonus = 0.0
        for item, rel in relevant:
            # only consider episodic items that have a decision attached
            if isinstance(item, EpisodicItem) and item.decision:
                # if the past decision matches the action we are scoring,
                # and it was important, add a bonus
                if item.decision.action_type == action:
                    mem_bonus += rel * item.importance
        score += mem_bonus * 1.5

        # ---- 4. Goal alignment ----
        # If any relevant goal mentions the same action or a related concept,
        # increase the score.
        goal_bonus = 0.0
        si_text = f"{intent} {getattr(si, 'raw_text', '')}"
        si_tokens = _token_set(si_text)
        for g in goals:
            goal_tokens = _token_set(g.description)
            overlap = _jaccard(si_tokens, goal_tokens)
            if overlap > 0.0:
                goal_bonus += overlap * g.priority
        score += goal_bonus * 1.2

        # ---- 5. Recency & importance of the cue itself ----
        # More recent and important observations should have slightly higher
        # influence on the decision.
        age_hours = (datetime.datetime.now() - si.timestamp).total_seconds() / 3600.0
        recency_factor = math.exp(-self._recency_lambda * age_hours)
        importance_factor = getattr(si, "importance", 0.5)
        score += (recency_factor * importance_factor) * 0.5

        # ---- 6. Memory influence (learned preferences from experience) ----
        # This is the developmental component: accumulated experience
        # creates behavioral biases that emerge naturally.
        influence_bonus = 0.0
        for signal in influence_signals:
            if signal.action_preference == action:
                # Scale influence by its strength and confidence
                influence_bonus += signal.strength * signal.confidence
        score += influence_bonus * self._influence_weight

        return score

    # -----------------------------------------------------------------
    # Payload builder – turns the chosen action into a dict the planner can use
    # -----------------------------------------------------------------
    def _build_payload(
        self,
        action: str,
        si: StructuredInput,
        relevant: List[Tuple[Any, float]],
        goals: List[Goal],
    ) -> dict[str, Any]:
        """
        Create a domain‑specific payload that the Output Planner will
        turn into a prompt for the Language Cortex.
        """
        # Base payload – we start with whatever the intent gave us
        payload: dict[str, Any] = {}

        if action == "execute":
            # Launch an application – look for APP entity
            app_entities = [e for e in getattr(si, "entities", []) if getattr(e, "label", "") == "APP"]
            payload["action"] = f"launch_{app_entities[0].text if app_entities else 'unknown'}"
        elif action == "query":
            # Answer a question – echo the raw text as the question to answer
            payload["question"] = getattr(si, "raw_text", "")
        elif action == "warn":
            # Warning – use any urgent fact from memory or the raw text
            urgent_fact = ""
            for item, _ in relevant:
                if isinstance(item, EpisodicItem) and getattr(item.decision, "urgency", "") == "high":
                    urgent_fact = getattr(item.decision, "payload", {}).get("message", "")
                    break
            payload["message"] = urgent_fact or getattr(si, "raw_text", "")
        else:  # inform (default)
            payload["message"] = getattr(si, "raw_text", "")
            # If we have a strong emotional cue, make the message empathetic
            if any(getattr(e, "label", "") == "EMOTION" for e in getattr(si, "entities", [])):
                payload["message"] = f"I sense you are feeling {getattr(si, 'emotional_cue', None) or 'unsure'}."

        # ---- Add goal context if relevant ----
        if goals:
            payload["related_goals"] = [g.description for g in goals]

        # ---- Add a brief memory summary (top 2 most relevant) ----
        top_mem = sorted(relevant, key=lambda x: x[1], reverse=True)[:2]
        memory_summary = []
        for item, rel in top_mem:
            if isinstance(item, EpisodicItem):
                memory_summary.append(
                    f"Similar past event (rel={rel:.2f}): {getattr(item.structured_input, 'raw_text', '')}"
                )
            elif isinstance(item, SemanticItem):
                memory_summary.append(
                    f"Known fact (rel={rel:.2f}): {item.fact}"
                )
        if memory_summary:
            payload["memory_context"] = "; ".join(memory_summary)

        return payload

    # -----------------------------------------------------------------
    # Contextual modifiers – adjust tone, priority, urgency, speak flag
    # -----------------------------------------------------------------
    def _contextual_modifiers(
        self,
        si: StructuredInput,
        relevant: List[Tuple[Any, float]],
        goals: List[Goal],
        chosen_action: str,
    ) -> tuple[str, float, float, bool]:
        """
        Return (tone, priority, urgency, speak) based on the full context.
        """
        tone = "neutral"
        priority = "normal"
        urgency = "normal"
        speak = True

        # Emotional cue → empathetic tone, lower urgency
        emotional_cue = None
        if getattr(si, "entities", None):
            for ent in si.entities:
                if getattr(ent, "label", "") == "EMOTION":
                    emotional_cue = getattr(ent, "text", None)
                    break
        if emotional_cue:
            tone = "empathetic"
            priority = "low"
            urgency = "low"

        # High importance or urgent memory → raise urgency/priority
        for item, rel in relevant:
            if rel > 0.5 and isinstance(item, EpisodicItem) and item.decision:
                past = item.decision
                if past.urgency == "high":
                    urgency = "high"
                    priority = "high"
                if past.priority == "high":
                    priority = "high"

        # Goal deadline soon → increase priority/urgency
        now = datetime.datetime.now()
        for g in goals:
            if g.deadline and (g.deadline - now).total_seconds() < 3600:  # <1h
                priority = "high"
                urgency = "high"

        # If the chosen action is a warning, force speak=True
        if chosen_action == "warn":
            speak = True

        # Default to speak unless the action is purely internal (none defined yet)
        if chosen_action not in ("inform", "warn", "query", "execute"):
            speak = False

        return tone, priority, urgency, speak
