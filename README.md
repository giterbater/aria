# ARIA

ARIA is a modular assistant prototype split into focused subsystems:

- `input_interpreter`: converts user input into structured intent, entities, facts, and questions.
- `aria_core`: owns goals, memory, and decision making.
- `output_planner`: converts decisions into language generation plans.
- `language_cortex`: wraps language model backends behind an async text interface.
- `ui`: displays status, events, and ALang-style debug state.

## Current Stability Baseline

The runnable demo path is rule-based input interpretation, simple in-memory cognition, rule-based output planning, and the mock language model fallback. Voice input and the CustomTkinter UI remain part of the interactive entry point in `main.py`.

Run the current smoke tests with:

```powershell
python -m unittest discover -s tests
```

`pytest` is not required for the current baseline.

## Assistant Ownership

- Mimo: `aria_core`, `aria_core/memory`, goal management, learning, decision logic, and civilization-research extensions.
- Nemotron: `input_interpreter`, `language_cortex`, `output_planner`, `ui`, ALang display, speech, conversation, and communication systems.
- Project Manager: roadmap, task slicing, integration review, tests, docs, commits, regression detection, and module boundary enforcement.
