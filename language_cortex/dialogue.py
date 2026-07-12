from __future__ import annotations

from .context import ContextResolver
from .memory import LanguageMemory
from .metrics import LanguageMetrics
from .parser import SemanticParser
from .response import ResponseGenerator
from .schemas import ConversationState, DialogueTurn, SemanticFrame
from .semantic_graph import SemanticGraph


class DialogueManager:
    """Coordinates semantic parsing, state, memory, and response generation."""

    def __init__(
        self,
        parser: SemanticParser,
        memory: LanguageMemory,
        response_generator: ResponseGenerator,
        state: ConversationState | None = None,
        graph: SemanticGraph | None = None,
        metrics: LanguageMetrics | None = None,
    ) -> None:
        self._parser = parser
        self._memory = memory
        self._graph = graph or SemanticGraph()
        self._metrics = metrics or LanguageMetrics()
        self._resolver = ContextResolver(memory, self._graph)
        self._responses = response_generator
        self._state = state or ConversationState()

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def memory(self) -> LanguageMemory:
        return self._memory

    @property
    def graph(self) -> SemanticGraph:
        return self._graph

    @property
    def metrics(self) -> LanguageMetrics:
        return self._metrics

    def parse(self, raw_text: str) -> SemanticFrame:
        frame = self._parser.parse(raw_text)
        self._resolver.resolve(frame, self._state)
        self._remember_graph_facts(frame)
        self._metrics.record_frame(frame)
        return frame

    def resolve_context(self, frame: SemanticFrame) -> dict:
        return self._resolver.resolve(frame, self._state)

    async def handle_turn(self, raw_text: str, **gen_kwargs) -> DialogueTurn:
        frame = self._parser.parse(raw_text)
        self._remember_graph_facts(frame)
        context = self._resolver.resolve(frame, self._state)
        response = await self._responses.generate(frame, context, **gen_kwargs)
        turn = DialogueTurn(user_text=raw_text, frame=frame, response=response)
        self._state.add_turn(turn)
        self._memory.remember_turn(turn)
        self._metrics.record_frame(frame)
        self._metrics.record_turn(turn)
        return turn

    def response_plan(self, frame: SemanticFrame, context: dict | None = None):
        return self._responses.plan(frame, context or self.resolve_context(frame))

    def _remember_graph_facts(self, frame: SemanticFrame) -> None:
        for subject, relation, obj in frame.metadata.get("graph_facts", []):
            self._graph.add_fact(
                subject,
                relation,
                obj,
                confidence=frame.confidence,
                source=frame.raw_text,
            )
