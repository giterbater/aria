from __future__ import annotations
import asyncio
from typing import AsyncIterator
from .consistency import ConsistencyChecker
from .interfaces import LanguageModel
from .dialogue import DialogueManager
from .memory import LanguageMemory
from .metrics import LanguageDiagnostics, LanguageMetrics
from .parser import SemanticParser
from .response import ResponseGenerator
from .schemas import ConversationState, DialogueTurn, ResponsePlan, SemanticFrame
from .semantic_graph import SemanticGraph

class LanguageCortex:
    """
    ARIA's language subsystem – pure text‑in / text‑out.

    Parameters
    ----------
    model : LanguageModel
        The backend responsible for generation. Can be swapped at runtime
        or via dependency injection.
    """
    def __init__(
        self,
        model: LanguageModel,
        *,
        parser: SemanticParser | None = None,
        memory: LanguageMemory | None = None,
        state: ConversationState | None = None,
        semantic_graph: SemanticGraph | None = None,
        metrics: LanguageMetrics | None = None,
    ) -> None:
        self._model = model
        self._parser = parser or SemanticParser()
        self._memory = memory or LanguageMemory()
        self._semantic_graph = semantic_graph or SemanticGraph()
        self._metrics = metrics or LanguageMetrics()
        self._response_generator = ResponseGenerator(model)
        self._dialogue = DialogueManager(
            self._parser,
            self._memory,
            self._response_generator,
            state=state,
            graph=self._semantic_graph,
            metrics=self._metrics,
        )

    @property
    def dialogue(self) -> DialogueManager:
        return self._dialogue

    @property
    def memory(self) -> LanguageMemory:
        return self._memory

    @property
    def semantic_graph(self) -> SemanticGraph:
        return self._semantic_graph

    @property
    def metrics(self) -> LanguageMetrics:
        return self._metrics

    @property
    def state(self) -> ConversationState:
        return self._dialogue.state

    # -----------------------------------------------------------------
    # Core language API
    # -----------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion for *prompt*."""
        return await self._model.generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        )

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield tokens as they are produced."""
        async for token in self._model.stream_generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        ):
            yield token

    # -----------------------------------------------------------------
    # Optional convenience helpers (still pure text)
    # -----------------------------------------------------------------
    async def chat(self, user_input: str, **gen_kwargs) -> str:
        """Convenience wrapper that treats *user_input* as a single turn."""
        return await self.generate(user_input, **gen_kwargs)

    async def chat_stream(
        self, user_input: str, **gen_kwargs
    ) -> AsyncIterator[str]:
        """Streaming version of :meth:`chat`."""
        async for token in self.stream_generate(
            user_input, **gen_kwargs
        ):
            yield token

    # -----------------------------------------------------------------
    # Language-layer API
    # -----------------------------------------------------------------
    def parse(self, raw_text: str) -> SemanticFrame:
        """Parse text into a semantic frame."""
        return self._dialogue.parse(raw_text)

    async def interpret(self, raw_text: str):
        """Return the existing ARIA StructuredInput contract."""
        return self.parse(raw_text).to_structured_input()

    def resolve_context(self, frame: SemanticFrame) -> dict:
        """Resolve references and retrieve relevant language memory."""
        return self._dialogue.resolve_context(frame)

    async def converse(self, user_input: str, **gen_kwargs) -> DialogueTurn:
        """Run a full dialogue turn with state and memory updates."""
        return await self._dialogue.handle_turn(user_input, **gen_kwargs)

    def plan_response(self, frame: SemanticFrame, context: dict | None = None) -> ResponsePlan:
        return self._dialogue.response_plan(frame, context)

    def check_consistency(self, draft: str, frame: SemanticFrame, context: dict, plan: ResponsePlan | None = None):
        response_plan = plan or self.plan_response(frame, context)
        return ConsistencyChecker().check(draft, frame, context, response_plan)

    def intent_accuracy(self) -> float:
        return self._metrics.intent_accuracy()

    def entity_accuracy(self) -> float:
        return self._metrics.entity_accuracy()

    def reference_resolution_rate(self) -> float:
        return self._metrics.reference_resolution_rate()

    def average_response_length(self) -> float:
        return self._metrics.average_response_length()

    def conversation_depth(self) -> int:
        return self._metrics.conversation_depth()

    def clarification_rate(self) -> float:
        return self._metrics.clarification_rate()

    def context_resolution_rate(self) -> float:
        return self._metrics.context_resolution_rate()

    def diagnostics(self) -> LanguageDiagnostics:
        """Return a typed snapshot of language-layer quality metrics."""
        return self._metrics.diagnostics()
