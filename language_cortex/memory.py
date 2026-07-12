from __future__ import annotations

from .schemas import DialogueTurn, SemanticFrame


class LanguageMemory:
    """Short-term language memory for dialogue continuity."""

    def __init__(self, capacity: int = 50, *, summary_threshold: int = 20) -> None:
        self._capacity = capacity
        self._summary_threshold = summary_threshold
        self._turns: list[DialogueTurn] = []
        self._facts: list[str] = []
        self._topics: list[str] = []
        self._preferences: dict[str, str] = {}
        self._active_subjects: list[str] = []
        self._unresolved_questions: list[str] = []
        self._conversational_goals: list[str] = []
        self._summaries: list[str] = []

    def remember_turn(self, turn: DialogueTurn) -> None:
        self._turns.append(turn)
        self._turns = self._turns[-self._capacity:]
        topic = turn.frame.metadata.get("topic")
        if topic:
            self.remember_topic(str(topic))
            self.remember_active_subject(str(topic))
        if turn.frame.intent == "question" and turn.frame.questions and not turn.response:
            self._unresolved_questions.extend(turn.frame.questions)
        if turn.frame.intent in {"create", "open_application", "search", "summarize"}:
            self._conversational_goals.append(turn.user_text)
            self._conversational_goals = self._conversational_goals[-self._capacity:]
        for fact in turn.frame.facts:
            self.remember_fact(fact)
        self._learn_preferences(turn.frame)
        self._summarize_if_needed()

    def remember_fact(self, fact: str) -> None:
        fact = fact.strip()
        if fact and fact not in self._facts:
            self._facts.append(fact)
            self._facts = self._facts[-self._capacity:]

    def recent_turns(self, limit: int = 5) -> list[DialogueTurn]:
        return self._turns[-limit:]

    def recent_topics(self, limit: int = 10) -> list[str]:
        return self._topics[-limit:]

    def active_subjects(self, limit: int = 10) -> list[str]:
        return self._active_subjects[-limit:]

    def preferences(self) -> dict[str, str]:
        return dict(self._preferences)

    def unresolved_questions(self, limit: int = 10) -> list[str]:
        return self._unresolved_questions[-limit:]

    def conversational_goals(self, limit: int = 10) -> list[str]:
        return self._conversational_goals[-limit:]

    def summaries(self, limit: int = 5) -> list[str]:
        return self._summaries[-limit:]

    def facts(self, limit: int = 10) -> list[str]:
        return self._facts[-limit:]

    def search(self, query: str, limit: int = 5) -> list[str]:
        tokens = set(query.lower().split())
        scored: list[tuple[str, int]] = []
        for fact in self._facts:
            score = len(tokens & set(fact.lower().split()))
            if score:
                scored.append((fact, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [fact for fact, _ in scored[:limit]]

    def latest_topic(self) -> str | None:
        return self._topics[-1] if self._topics else None

    def remember_frame(self, frame: SemanticFrame) -> None:
        for fact in frame.facts:
            self.remember_fact(fact)
        topic = frame.metadata.get("topic")
        if topic:
            self.remember_topic(str(topic))
            self.remember_active_subject(str(topic))

    def remember_topic(self, topic: str) -> None:
        topic = topic.strip()
        if topic and (not self._topics or self._topics[-1].lower() != topic.lower()):
            self._topics.append(topic)
            self._topics = self._topics[-self._capacity:]

    def remember_active_subject(self, subject: str) -> None:
        subject = subject.strip()
        if not subject:
            return
        self._active_subjects = [s for s in self._active_subjects if s.lower() != subject.lower()]
        self._active_subjects.append(subject)
        self._active_subjects = self._active_subjects[-self._capacity:]

    def clear_unresolved_question(self, question: str) -> None:
        self._unresolved_questions = [q for q in self._unresolved_questions if q != question]

    def _learn_preferences(self, frame: SemanticFrame) -> None:
        for subject, relation, obj in frame.metadata.get("graph_facts", []):
            if subject.lower() == "user" and relation in {"likes", "prefers"}:
                self._preferences[relation] = obj

    def _summarize_if_needed(self) -> None:
        if len(self._turns) < self._summary_threshold:
            return
        window = self._turns[: max(1, self._summary_threshold // 2)]
        topics = [str(t.frame.metadata.get("topic")) for t in window if t.frame.metadata.get("topic")]
        intents = [t.frame.intent for t in window]
        summary = f"{len(window)} turns; topics={', '.join(topics[-5:]) or 'none'}; intents={', '.join(intents[-5:])}"
        self._summaries.append(summary)
        self._turns = self._turns[len(window):]
