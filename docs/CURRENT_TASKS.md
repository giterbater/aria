# Current Tasks

## In Progress

- Project Manager: maintain the rule-based smoke baseline and review cross-module integration.

## Next Up

1. Nemotron: extract ALang rendering from `ui/aria_ui.py` into a reusable communication utility.
2. Nemotron: add a text-mode conversation loop for testing without microphone or CustomTkinter.
3. Project Manager: add regression tests for goal relevance, event bus publish/subscribe, and the sync worker bridge.

## Done

- Mimo: improved memory relevance by extracting structured text from StructuredInput, ARIDecision, and dicts instead of relying on dataclass repr.
- Mimo: preserved memory item subclasses (WorkingMemoryItem, EpisodicItem, SemanticItem) with type-safe `with_importance` overrides.
- Project Manager: documented subsystem ownership and roadmap priorities.
- Project Manager: added a standard-library rule-based pipeline smoke test.
- Project Manager: fixed the worker path so async interpreter, decision, planner, and language calls execute correctly from the synchronous speech loop.
