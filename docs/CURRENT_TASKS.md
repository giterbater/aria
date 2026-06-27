# Current Tasks

## In Progress

- Project Manager: maintain the rule-based smoke baseline and review cross-module integration.

## Next Up

1. Mimo: improve memory relevance by extracting text from `StructuredInput` fields instead of relying on object string output.
2. Mimo: preserve memory item subclasses when `update_importance` creates updated copies.
3. Nemotron: extract ALang rendering from `ui/aria_ui.py` into a reusable communication utility.
4. Nemotron: add a text-mode conversation loop for testing without microphone or CustomTkinter.
5. Project Manager: add regression tests for goal relevance, event bus publish/subscribe, and the sync worker bridge.

## Done

- Project Manager: documented subsystem ownership and roadmap priorities.
- Project Manager: added a standard-library rule-based pipeline smoke test.
- Project Manager: fixed the worker path so async interpreter, decision, planner, and language calls execute correctly from the synchronous speech loop.
