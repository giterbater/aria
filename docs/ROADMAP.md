# ARIA Roadmap

## Priority 0: Keep The Repo Runnable

Owner: Project Manager

- Maintain a passing standard-library smoke test suite.
- Keep the rule-based pipeline usable without external API keys.
- Avoid coupling UI, speech, cognition, and language model backends directly.
- Commit meaningful milestones after tests pass.

## Priority 1: Stabilize Async Boundaries

Owner: Project Manager integration, Mimo/Nemotron by subsystem

- Ensure every async protocol call is awaited or run through a clear sync bridge.
- Add tests for interpreter, core decision maker, output planner, and mock language generation.
- Document which entry points are interactive and which are test-safe.

## Priority 2: Cognitive Core Improvements

Owner: Mimo

- Improve memory relevance so it uses structured input fields instead of object string representations.
- Preserve concrete memory item types when updating importance.
- Add goal lifecycle tests for add, remove, relevance, deadlines, and completion signals.

## Priority 3: Communication Layer Improvements

Owner: Nemotron

- Harden input interpretation confidence handling.
- Add ALang serialization helpers outside UI code so debug rendering is reusable.
- Add a text-mode conversation loop that does not require microphone or CustomTkinter.

## Priority 4: UI And Speech Reliability

Owner: Nemotron

- Guard optional UI and speech dependencies with clear error messages.
- Add event bus subscriptions tests for key UI events.
- Keep the UI a consumer of events, not a direct owner of cognition.

## Review Rules

- Mimo and Nemotron should not work on the same module in the same milestone.
- Changes that cross subsystem boundaries require Project Manager integration review.
- Run `python -m unittest discover -s tests` after each major change.
- Update this roadmap when priorities or ownership change.
