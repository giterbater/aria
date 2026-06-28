# ARIA Project — New CTO Audit Report

**Date**: 2026-06-28
**Auditor**: Incoming CTO and Engineering Manager
**Scope**: All commits, all architecture, all documentation, all tests, all reports
**Verdict on prior CTO**: **Refuted.** The "production-ready, professional-grade foundation" claim is misleading. The codebase is a runnable prototype with disciplined hygiene. Operational, persistence, and concurrency scaffolding are missing or wrong.

---

## 1. Independent Architecture Review

### 1.1 What is genuinely well-architected

Credit where due. These are real wins:

- **`MemorySystemProtocol` with `@runtime_checkable`** (`aria_core/memory/interfaces.py`). True dependency inversion: `SimpleDecisionMaker` never imports `SimpleMemorySystem`. The protocol is well-named, minimal, and the decision maker can be tested with any conforming memory.
- **`MemoryItem.with_importance()` preserves concrete subclasses** (`aria_core/memory/models.py:26`). The `dataclasses.replace` idiom correctly maintains `WorkingMemoryItem`/`EpisodicItem`/`SemanticItem` types through immutable updates, including the clamp. Tested.
- **Event bus lock + callback snapshot copy** (`event_bus.py:36-44`). Avoids the classic "list mutated during iteration" bug. Subscriber errors are isolated.
- **Recursive `_extract_text_into`** (`simple_memory_system.py:38-73`). Robust to dicts, lists, dataclasses, `None`. Genuinely good.
- **Layered pipeline**: `input_interpreter → aria_core → output_planner → language_cortex → ui`. Each stage has a typed Protocol seam. This is the right shape.
- **Test suite runs**: 56/56 pass in 0.1s. Verified.

### 1.2 Architectural mistakes — CRITICAL

**C1. Duplicated `_load_config()` across two entry points.**
`main.py:38-77` and `text_mode_loop.py:34-69` are 36 lines of copy-paste that has already drifted: `main.py` declares an `llm_based` interpreter config and `confidence_threshold`; `text_mode_loop.py` does not. A contributor will fix one and miss the other. The two entry points have different effective configs today.

**C2. `asyncio.run()` per call inside a worker thread.**
`main.py:109-111`, `text_mode_loop.py:120-122`. Verified empirically: **4 `asyncio.run()` calls per turn**. Each one allocates a new event loop, sets it as the current thread loop, runs the coroutine, then closes the loop. Costs are not the only issue:
- No way to stream (the protocol has `stream_generate`; nothing calls it).
- No way for an async subscriber to actually run; the bus just calls it and gets a coroutine object that never executes.
- `OpenAIModel.AsyncOpenAI` is never `aclose()`d.
- Cannot cancel an in-flight call cleanly.

**C3. `decision_maker.decide()` is `async` but contains no `await`.**
`aria_core/decision_maker.py:64`. The function is purely CPU-bound. The `async` keyword is a promise, not a fact. It exists to justify `asyncio.run()`. This is the root cause of C2.

**C4. `EpisodicItem.outcome` is write-once `None` — the entire feedback loop is missing.**
`decision_maker.py:120` writes `outcome=None, # filled later after execution`. Verified: every episode's outcome stays `None` forever. There is no executor, no `record_outcome()`, no signal from the world. The system cannot learn. The comment in `decision_maker.py:178` admits "we approximate success by high importance" — a placeholder for a feature that does not exist. The `EpisodicItem.outcome` field, the consolidation path, and the "memory of successes vs failures" idea are all dead code.

**C5. Singleton event bus with no isolation.**
`event_bus.py:48` `bus = _EventBus()`. Tests `tests/test_regression.py:122-200` mutate the singleton and never clean up. `test_text_mode_loop.py:33` calls `run_text_loop()` end-to-end inside a test. There is no `bus.clear()`. Test order affects results.

### 1.3 Architectural mistakes — MAJOR

**M1. `SimpleMemorySystem` has unbounded vocabulary growth.**
`simple_memory_system.py:130-141, 281-298`. Verified: every distinct token ever seen is added to `_vocab`; `_tfidf_vector` allocates `len(vocab)` floats per call. After 10k distinct tokens, every retrieval is 10k-element list allocation. IDF numerator uses `len(self._term_freq)` (total tokens ever seen) instead of document count, so the metric becomes uninformative as the corpus grows.

**M2. `outcome` field write-once `None` is a memory model defect.**
Already covered as C4. Listed separately because it is the single highest-value missing feature.

**M3. `_ACTION_TYPES` is a stringly-typed hidden catalog.**
`decision_maker.py:46, 89, 173, 229, 233, 236, 319, 323`. Adding an action requires grepping the codebase. The same string `("inform", "warn", "execute", "query")` is also duplicated in `output_planner/implementations/rule_based.py:8-11` and `main.py:176`. A typo fails silently.

**M4. Tone/priority/urgency literals duplicated in three places.**
`aria_core/interfaces.py:30-32` declares the `Literal`. `output_planner/implementations/rule_based.py:41` repeats the tone list. `output_planner/implementations/llm_based.py:24` repeats it again in a prompt string. The LLM-based planner can return any string — no validation against the `Literal`.

**M5. Output planner returns plain `dict`, not a typed `Plan` dataclass.**
`output_planner/interfaces.py:8` says `-> dict`. Every consumer does `plan.get("speak", True)`. The LLM planner's JSON is not validated. A `plan["speek"]` typo crashes at runtime.

**M6. `main.py` hard-imports `speech_recognition` and `customtkinter` at top level.**
`main.py:21-22`. The README's "`python -m text_mode_loop`" advertised path is fine because `text_mode_loop.py` doesn't import `main.py`. The moment a test imports `main.py` — and there is no test for `_aria_worker` — PyAudio and Tk must be installed. The "guard optional UI and speech dependencies" guideline in the roadmap is violated by the entry point that writes the guideline.

**M7. `LanguageCortex.chat()` is a 1:1 alias for `generate()` plus aliases duplicated across modules.**
`language_cortex/manager.py:50-52`. Three call sites call `.chat()` on different objects: `LanguageCortex` (alias), `LLMBasedInputInterpreter` (which constructed its own `LanguageCortex` *and* would receive one if it took an injected one), `LLMBasedOutputPlanner` (same). The naming is overloaded.

**M8. Factory pattern via `importlib` is unjustified.**
`input_interpreter/factory.py`, `output_planner/factory.py`, plus inline `getattr(__import__(...))` in `main.py:88-92` and `text_mode_loop.py:105-109`. There is no plugin system, no extension point, no third-party implementation. Three different instantiation patterns across the codebase.

**M9. The "1-week ARIA Remembers" milestone is not in the roadmap.**
The previous roadmap (P0–P4) does not include persistence, multi-turn context, outcome feedback, or any user-value milestone beyond "keep it runnable" and "stabilize async boundaries." See §5 for the new roadmap.

### 1.4 Architectural mistakes — MINOR

- **m1.** `GoalManager.relevant_goals()` uses naive token-set intersection with no ranking. The roadmap promises "embedding-based search in a production swap" but no plumbing exists for the swap.
- **m2.** `GoalManager` has no completion tracking. Completion is implemented as a substring match in `main.py:176-180` (cognitive policy running in the entry point). `Goal` is `frozen=True`, so it cannot change status.
- **m3.** No persistence anywhere. All state is RAM. Restart kills everything.
- **m4.** `decision_maker.py` uses `getattr(si, "attr", default)` defensively against a typed dataclass. 28+ occurrences. Hides bugs and defeats static analysis.
- **m5.** `_ACTION_TYPES` checked in three places, not derived from one source.
- **m6.** `_aria_worker` is 110+ lines doing six things. Pipeline orchestration is duplicated in `text_mode_loop.py:139-184`.
- **m7.** `MockModel.generate` truncates at 100 chars, but `stream_generate` doesn't — inconsistent.
- **m8.** Memory model fields use `Any` (`structured_input: Any`, `decision: Any`, `fact: Any`). Defeats dataclass typing.
- **m9.** `goals.py:20` uses `__import__('uuid')` inside a `default_factory` instead of `import uuid` at module level.
- **m10.** No `Session`/`ConversationContext` flows through the pipeline.
- **m11.** `LLMBasedInputInterpreter` and `LLMBasedOutputPlanner` are wired nowhere — dead code paths.
- **m12.** `LlamaCPPModel` raises `NotImplementedError` from `__init__` — footgun.

### 1.5 Missing architectural pieces

1. **Feedback loop from outcome → memory.** (C4.) The single most important missing piece.
2. **Session / conversation manager.** No turn IDs, no resumption.
3. **Action executor.** `decision.action_type == "execute"` produces no side effect. The system only plans to act.
4. **Plan validator.** LLM planner returns whatever JSON it emits.
5. **Configuration validation.** `_load_config()` returns a `dict` with no schema.
6. **Persistence layer.** (See P1 below.)
7. **Cancellation / timeout policy.** `cortex.chat()` can block forever; `recognize_google` can hang.
8. **Streaming path.** `LanguageCortex.stream_generate()` is declared but never called.
9. **Multi-modal input pipeline.** Microphone + Google STT only.
10. **Tool registry / function-calling.** The "execute" action is a non-extensible string.
11. **Telemetry / observability.** No metrics, no traces, no structured logs.

---

## 2. Engineering Quality Report

### 2.1 Confirmed bugs

| ID | Location | Bug | Verified |
|----|----------|-----|----------|
| **B1** | `output_planner/implementations/rule_based.py:17-19` | `decision.priority or base["priority"]` — empty string silently becomes the base. Setting `priority=""` on a `warn` decision yields `"high"`. | ✅ Reproduced. |
| **B2** | `event_bus.py:41-44` | Silently swallows **every** exception in subscribers. `logger.warning` without traceback; the traceback-logging claim in the prior session report only applies to `main.py`. | ✅ Confirmed. |
| **B3** | `event_bus.py:38-40` | Lock released before invoking callbacks. A subscriber that unsubscribes another during dispatch sees stale state. | ✅ Confirmed by reading. |
| **B4** | `main.py:113-115, 187-189` | Microphone held open across `RequestError` recovery. On persistent STT failure the loop spins in tight listen/timeout cycles forever. | ✅ Confirmed. |
| **B5** | `main.py:111, 195` | Generic `except Exception: break` in the worker loop terminates the daemon on any error. The `break` at line 195 is a kill switch, not recovery. | ✅ Confirmed. |
| **B6** | `text_mode_loop.py:131, 186-188` | `KeyboardInterrupt` is caught but `stop_event` (only in `main.py`) is not set. EOFError not handled explicitly. | ✅ Confirmed. |
| **B7** | `aria_core/decision_maker.py:125-127`, `main.py:171-173`, `text_mode_loop.py:175-177` | The "every 7 calls" housekeeping trigger is duplicated three times. On the first call, `len == 0`, so it always fires immediately. | ✅ Confirmed. |
| **B8** | `aria_core/memory/simple_memory_system.py:262` | Salience uses `in` (substring match) over a word list. `"unhappy"` contains `"happy"`; `"saddlery"` contains `"sad"`. False positives. | ✅ Reproduced. |
| **B9** | `aria_core/memory/simple_memory_system.py:317-365` | `consolidate()` recomputes nothing; low-importance items are kept with their original `importance` value. "Consolidation" is mostly a copy. | ✅ Confirmed. |
| **B10** | `aria_core/decision_maker.py:301-310` | Local `priority` is a string but annotated `float` in the return tuple. Static type checkers flag every call site. | ✅ Confirmed. |
| **B11** | `aria_logging.py:56` | `setup_logging()` runs at module import. Calling `setup_logging(level="DEBUG")` later doesn't reach this global; the import-time configuration wins. | ✅ Confirmed. |
| **B12** | `ui/aria_ui.py:264` | `_on_thought_generated(self, payload: Any)` references `Any` but it is not imported. Latent `NameError` on type introspection. The auditor reproduced it via `typing.get_type_hints`. | ✅ Reproduced. |
| **B13** | `main.py:163` | `time.sleep(min(2.0, len(response) * 0.05))` — fake speech duration, only in the audio path. Asymmetric. | ✅ Confirmed. |
| **B14** | `main.py:40`, `text_mode_loop.py:37` | `os.getenv("OPENAI_API_KEY").startswith("sk-fake")` — sentinel string as config. Also conflates the **OpenAI** API key with the **Google** STT path. | ✅ Confirmed. |
| **B15** | `tests/test_regression.py:122-200` | Singleton bus accumulates subscribers across tests. No `tearDown` clearing them. | ✅ Confirmed. |
| **B16** | `tests/test_text_mode_loop.py:30-62` | `run_text_loop()` invoked end-to-end with mocked `input`/`print`. Asserts are `assertTrue(True)` and `mock_input.assert_called()`. They confirm the loop ran; they don't confirm correct behavior. | ✅ Confirmed. |
| **B17** | `output_planner/llm_based.py:31-32`, `input_interpreter/llm_based.py:23-25` | `json.loads` on LLM output with no try/except. Malformed JSON crashes the worker. | ✅ Confirmed. |
| **B18** | `main.py:166-167` | Dead `else` branch in speech loop — emits start/stop with no work between. | ✅ Confirmed. |
| **B19** | `aria_core/memory/simple_memory_system.py:271` | IDF numerator is `len(self._term_freq)`, the total distinct tokens ever seen — not the number of documents. The metric becomes uninformative as the corpus grows. | ✅ Confirmed. |

### 2.2 Dead code (verified)

| ID | File | Reason dead |
|----|------|-------------|
| **D1** | `language_cortex/models/llama_cpp.py` | `__init__` raises `NotImplementedError`. Cannot be instantiated. |
| **D2** | `input_interpreter/implementations/llm_based.py`, `output_planner/implementations/llm_based.py` | Neither is wired in any `_load_config()`. Factory branches exist; no caller reaches them. |
| **D3** | `ui/aria_ui.py:200-205, 217-219, 264-267` | `_on_interpretation_ready`, `_on_action_planned`, `_on_thought_generated` — handlers do `pass` or compute values that are discarded. |
| **D4** | `ui/aria_ui.py:142-147` | Subscribes to `GoalCreated`, `InternalState`, `CurrentTask` — none are ever published. |
| **D5** | `aria_logging.py:59-63` | `get_logger()` defined but no module imports it. |
| **D6** | `__pycache__/test_decision.cpython-311.pyc` | Source `test_decision.py` was deleted in commit `bab762c`; the `.pyc` was not cleaned. Not in repo, but local clutter. |

### 2.3 Hidden duplication (verified)

| ID | Files | Duplication |
|----|-------|-------------|
| **H1** | `main.py:38-77`, `text_mode_loop.py:34-69` | `_load_config()` is copy-pasted. Already drifted: `main.py` has `llm_based` interpreter + `confidence_threshold`; `text_mode_loop.py` does not. |
| **H2** | `main.py:136-140`, `text_mode_loop.py:151-155` | ALang term construction duplicated. |
| **H3** | `main.py:97-99`, `text_mode_loop.py:115-117` | Goal seeding duplicated. |
| **H4** | `main.py:115-184`, `text_mode_loop.py:139-184` | Full pipeline orchestration duplicated. |
| **H5** | `event_bus.publish` vs `text_mode_loop.pub` | Identical wrappers; only naming differs. |
| **H6** | `main.py:88-92`, `text_mode_loop.py:105-109` | Model-class `getattr(__import__(...))` pattern duplicated. |
| **H7** | `aria_core/decision_maker.py:155-200` | `getattr(si, "entities", None)` repeated 5 times instead of being factored. |

### 2.4 Test coverage gaps (verified)

| ID | Module | Gap |
|----|--------|-----|
| **G1** | `aria_core/decision_maker.py` | Zero tests. Scoring, payload building, emotional cues, deadline escalation — all untested. |
| **G2** | `output_planner/implementations/rule_based.py` | Zero tests. Tone mapping, temperature, max_tokens heuristic, the empty-string-priority bug (B1) — all untested. |
| **G3** | `output_planner/factory.py`, `input_interpreter/factory.py` | Zero tests for the **only** public API for switching backends. |
| **G4** | `language_cortex/manager.py` | Zero tests for `generate`, `stream_generate`, `chat`, `chat_stream`. |
| **G5** | `language_cortex/models/mock.py`, `openai.py` | Zero tests. |
| **G6** | `output_planner/llm_based.py`, `input_interpreter/llm_based.py` | Dead paths also untested. Removing them is safe. |
| **G7** | `aria_core/memory/simple_memory_system.py` | `consolidate()`, `forget_low_importance()`, `_compute_base_importance`, vocab drift, importance clamping on >1.0 delta — all untested. |
| **G8** | `aria_core/goals.py` | `relevant_goals()` empty cue, multi-word matching, priority ordering — untested. |
| **G9** | `main.py`, `text_mode_loop.py` | No tests for pipeline internals. |
| **G10** | `event_bus.py` | No test for exception-swallowing. |
| **G11** | `ui/aria_ui.py` | Zero tests. |
| **G12** | `tests/test_regression.py` | `test_decision_maker_uses_memory_protocol` only checks `is not None`, not that the protocol is actually used. |

**Coverage estimate**: 56 tests over ~2,500 lines of code, with many tests being trivial (`test_empty_list`, `test_empty_dict`, `test_config_loading`). Real behavioral coverage is well under 30%.

### 2.5 Concrete quality improvements (top 12, ordered by value)

1. **Extract `_load_config()` into a single `config.py`.** Resolves H1, prevents drift.
2. **Extract a `Pipeline` class / `run_pipeline(text: str) -> PipelineResult`.** Resolves H2–H6, deduplicates 70+ lines.
3. **Make `decision_maker.decide()` actually async or sync.** If memory backend becomes I/O-bound, this becomes naturally async. Otherwise, drop the `async` keyword and call directly. Resolves C3.
4. **Replace `asyncio.run()` per call with a long-lived event loop in the worker.** One `asyncio.new_event_loop()` + `loop.run_until_complete(_aria_loop(...))`. Resolves C2.
5. **Add `bus.clear()` and use it in `setUp`/`tearDown`.** Resolves C5, B15, T1.
6. **Lazy-import `speech_recognition` and `customtkinter` inside the worker / UI.** Resolves M6.
7. **Introduce `ActionType` and `Tone` enums.** Replace string literals across `decision_maker.py`, `output_planner/rule_based.py`, `main.py`. Resolves M3, M4, m5.
8. **Introduce `Plan` dataclass with typed fields.** Resolves M5. `Plan.from_dict(d, decision)` for backward compat.
9. **Fix `output_planner/rule_based.py:17-19` falsy bug.** Use `if decision.priority in {"low","normal","high"} else base["priority"]`. Resolves B1.
10. **Cap `_vocab` size and use document count for IDF.** Add `max_vocab_size=50000` knob, frequency-based eviction. Resolves M1, B19.
11. **Add `EpisodicItem.outcome` writeback + `ActionExecutor` Protocol + `record_outcome()`.** Resolves C4. The single most valuable feature missing.
12. **Fix the `Any` import in `ui/aria_ui.py:264`.** Add `from typing import Any`. Resolves B12.

---

## 3. Technical Debt Report

### 3.1 Debt score by category (1 = clean, 10 = dire)

| Category | Score | Reasoning |
|----------|-------|-----------|
| Code debt | 6/10 | Real duplication, one latent `NameError`, some dead code, but tidy overall. |
| Architecture debt | 8/10 | Persistence is the killer. The `asyncio.run`-from-thread pattern is a tax. |
| Test debt | 7/10 | 56 tests pass, but several are smoke tests with `assertTrue(True)`; bus singleton bleeds. |
| Documentation debt | 8/10 | `SESSION_REPORT` actively misleads with "production-ready" and inflated coverage numbers. |
| Dependency debt | 10/10 | No `requirements.txt`, no `pyproject.toml`, no lockfile. Cannot reproduce. |
| Operational debt | 10/10 | No CI, no linter, no type-checker, no pre-commit, no coverage. Plain-text logs. |
| Configuration debt | 7/10 | Duplicated `_load_config`, `sys.path` surgery, hardcoded thresholds. |
| Concurrency debt | 8/10 | Singleton bus + `asyncio.run`-from-thread + cross-thread UI access. |
| Persistence debt | 10/10 | Zero on-disk state. |
| Observability debt | 9/10 | Plain-text stderr, no JSON, no metrics, no tracing. |

**Overall: 8.3/10 — significant technical debt.** This is a well-organized prototype, not a product.

### 3.2 Top 10 debt items to fix first (ordered by engineering value)

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Add `requirements.txt` + `requirements-dev.txt` with pinned versions | 1 hour | Blocks every other "ops" item. |
| 2 | Extract `config.py`, remove duplication (H1) | 3 hours | Prevents drift between entry points. |
| 3 | Extract `pipeline.py` with `Pipeline` + `run_pipeline()` (H2–H6) | 4 hours | Removes 70+ duplicated lines. |
| 4 | Replace `asyncio.run()` with long-lived loop (C2, C3) | 4 hours | Unblocks streaming, async subscribers, clean shutdown. |
| 5 | Add SQLite-backed memory + goal persistence (C4, A6, P1) | 1–2 days | The single biggest gap. Restart kills everything today. |
| 6 | Add `EpisodicItem.outcome` writeback + `ActionExecutor` Protocol (C4) | 1 day | The "cognitive" feature that does not exist. |
| 7 | Add GitHub Actions CI: ruff + mypy + unittest on Python 3.10/3.11 | 2 hours | The 56 tests don't run on PR. |
| 8 | Add `ActionType` / `Tone` enums + `Plan` dataclass (M3, M4, M5) | 4 hours | Pays off across 5+ files. |
| 9 | Add `bus.clear()` + structured (JSON) logging (C5, OP6) | 3 hours | Removes test bleed; unblocks log aggregation. |
| 10 | Fix the truthfulness of `SESSION_REPORT.md` (D1, D3, D6) | 30 min | Stop misleading future contributors. |

**Total effort for top 10**: ~3 working days.

### 3.3 What's acceptable (do not fix yet)

- Empty `__init__.py` files. Python best practice; no public API to re-export.
- `MockModel` echoing prompts. It is a fixture.
- `SimpleMemorySystem`'s O(N) `pop(0)`. Capacity is 20. Premature optimization.
- `SimpleDecisionMaker`'s hardcoded `_ACTION_TYPES`. Adding types is a deliberate design decision; the current four are fine.
- `sys.path.append` in `main.py:19`. Bounded; goes away when `pyproject.toml` lands (#1).
- `text_mode_loop.py`'s `print()` calls. It is a CLI; that is literally the job. The SESSION_REPORT's "all prints replaced" claim is wrong, but the *intention* — that the CLI prints chat output — is correct.
- `__pycache__` artifacts. Already in `.gitignore`.

### 3.4 Quick wins (≤30 min, high value)

- Delete `language_cortex/models/llama_cpp.py` (or move to `examples/`).
- Add `from typing import Any` to `ui/aria_ui.py`.
- Add `.env.example` documenting `OPENAI_API_KEY`.
- Add a `tests/test_smoke.py` that imports every module (catches import-time regressions).
- Strip the "Operational Readiness" / "Production Ready" green-checks from `SESSION_REPORT.md`.
- Fix the `test_event_bus` `setUp`/`tearDown` to call `bus.clear()`.

---

## 4. Project Health Score

| Dimension | Score (1–10) | Reasoning |
|-----------|---------------|-----------|
| **Code health** | 5 | Tidy in places, but C1–C5 + 19 confirmed bugs + 12 untested modules. |
| **Architecture health** | 5 | Layered with good Protocols. But: `asyncio.run`-per-call, no persistence, no outcome feedback, no executor, no session manager. |
| **Test health** | 5 | 56 tests pass. Several are trivial or have `assertTrue(True)`. Bus singleton bleeds. No decision-maker tests. No UI tests. No factory tests. No integration tests. |
| **Documentation health** | 4 | README is reasonable. SESSION_REPORT is marketing copy with verifiable false claims. ROADMAP is process-shaped, not value-shaped. No architecture diagram. |
| **Operational health** | 1 | No CI, no linter, no type-checker, no coverage, no `requirements.txt`, plain-text logs, no metrics, no tracing. |
| **Persistence health** | 0 | No on-disk state. |
| **Concurrency health** | 3 | Singleton bus + `asyncio.run`-per-call + cross-thread Tk access. |
| **Maintainability** | 5 | Good module boundaries; clear Protocols. Hindered by duplication, dead code, no tooling. |
| **Production-readiness** | 0 | Refuted. See §1.1, §2, §3. |

**Composite: 3.0 / 10 — Runnable prototype, not a product.** The previous CTO's "professional-grade foundation" framing applies to the *architecture* and the *tests* (relative to other prototypes), not to the *system*. The architecture is professional; the operational scaffolding is missing.

---

## 5. Revised Roadmap

Restructured around **what blocks user value**, not what is comfortable to ship. Priorities renumbered.

### Priority 0 — Foundation: Configuration and Pipeline Consolidation

**Owner: Project Manager (CTO)**
- Extract `config.py` with a typed `ARIAConfig` dataclass. Single source of truth.
- Extract `pipeline.py` with `Pipeline` and `run_pipeline(text: str) -> PipelineResult`. Both entry points become thin I/O adapters.
- Add `requirements.txt` + `requirements-dev.txt` with pinned versions. `pyproject.toml` with `[tool.ruff]`, `[tool.mypy]`, `[project]`.
- Add `.env.example`.
- **Exit criteria**: `python -m aria` and `python -m text_mode_loop` produce identical pipeline behavior from a single config. `pip install -r requirements.txt && ruff check . && mypy aria_core` clean.

### Priority 1 — Async Loop and Failure Recovery

**Owner: Nemotron (with Project Manager review)**
- Replace per-call `asyncio.run()` with a single long-lived loop in the worker.
- Move `import speech_recognition` and `import customtkinter` inside their respective workers (lazy import).
- Add `--mode headless` / `--mode ui` flag; same binary, different entry.
- Replace `except Exception: break` with a per-turn recovery that logs, publishes `SystemStatus`, and continues.
- Add a single `event_bus.clear()` and use it in test `setUp`/`tearDown`.
- **Exit criteria**: `python -m aria --mode headless` starts without PyAudio. Killing the speech recognizer mid-session does not kill the worker. Tests are order-independent.

### Priority 2 — Persistence and Outcome Feedback (the "ARIA Remembers" milestone)

**Owner: Mimo**
- Define `PersistenceProtocol` in `aria_core/persistence/interfaces.py`.
- Ship a SQLite-backed implementation. `SQLiteMemorySystem` implementing `MemorySystemProtocol`. `SQLiteGoalStore` for `GoalManager`.
- Add `ActionExecutor` Protocol and a `ToolRegistry` with: `launch_application`, `set_reminder`, `cancel_reminder`, `current_time`.
- Add `record_outcome(episode_id, outcome: Outcome)` on the memory layer.
- The worker loop dispatches tool execution and records outcome from the tool's return value or the user's next utterance (explicit `Outcome` heuristic: "yes"→success, "no"→failed, "thanks"→success).
- `consolidate()` prefers high-outcome episodes.
- **Exit criteria**: Kill the process mid-conversation, restart, ask "what were we talking about?" → ARIA answers from memory. `launch_application("notepad")` opens Notepad on Windows.

### Priority 3 — Multi-Turn Context

**Owner: Mimo (context), Nemotron (cortex signature)**
- Define `ConversationTurn` dataclass: `role, content, structured_input, decision, response, outcome, timestamp`.
- Pass a `Session` object through the pipeline.
- `LanguageCortex.chat(turns: list[ConversationTurn], retrieved: list[MemoryItem], **kwargs)` — prompt is constructed from recent turns + retrieved memories, token-budgeted.
- The decision maker consumes the last N turns as context.
- **Exit criteria**: A 3-turn conversation about "open notepad → type hello → what did I just say?" works.

### Priority 4 — Tool-Use and Extensibility

**Owner: Nemotron**
- `ARIDecision` carries `tool_name: str` and `tool_args: dict` (structured, not string-based).
- Wire `LLMBasedInputInterpreter` and `LLMBasedOutputPlanner` through their factories with a `LanguageCortex` constructor argument. Currently dead code; either wire or remove.
- Remove `LlamaCPPModel` stub until a binding target exists.
- **Exit criteria**: ARIA can call `launch_application("notepad")`, `set_reminder(30, "stretch")`, `current_time()`. The LLM-based interpreter and planner are reachable through config.

### Priority 5 — Type Safety, Observability, and CI

**Owner: Project Manager**
- Add `ActionType`, `Tone`, `Priority`, `Urgency` enums. Replace string literals everywhere.
- `Plan` dataclass replaces dict return.
- `ruff` + `mypy --strict aria_core` clean. `pre-commit` enforced.
- Structured JSON logs with `correlation_id` per turn.
- GitHub Actions: ruff, mypy, unittest, coverage badge.
- **Exit criteria**: CI is green on a clean clone. `pre-commit run --all-files` passes. Every log line is JSON-parseable.

### Priority 6 — Quality, Benchmarking, and Decision Regression

**Owner: Mimo**
- Build a 30-utterance eval set with expected `intent` and `action_type`.
- A regression test runs the eval against `RuleBasedInputInterpreter + SimpleDecisionMaker` and asserts action accuracy ≥ baseline.
- Same eval runs against `LLMBasedInputInterpreter + SimpleDecisionMaker` for comparison.
- **Exit criteria**: A change to the decision maker that drops accuracy fails CI.

### Priority 7 — Privacy and User Identity

**Owner: Project Manager**
- Add `UserProfile`: id, display name, optional voice fingerprint, retention policy.
- Audio and transcripts scoped to a profile. `--no-audio-retention` and `--transcript-retention-days` flags.
- `docs/privacy.md` documents the data flow.
- **Exit criteria**: An external reviewer can answer "what data does ARIA store, where, for how long?" from `docs/privacy.md` alone.

### Owner reassignments

| Concern | Current | Proposed |
|---------|---------|----------|
| `event_bus.py` | (none) | **Project Manager** — interface contract. |
| `aria_logging.py` | PM (implicit) | **Project Manager** — explicit. |
| `aria_core/persistence/*` (new) | (none) | **Mimo**. |
| `language_cortex/factory.py` (new) | (none) | **Nemotron**. |
| `config.py` (consolidate `_load_config`) | (none) | **Project Manager**. |
| `pipeline.py` (consolidate entry-point logic) | (none) | **Project Manager** with Nemotron review. |
| `tools/` (new, with `ToolRegistry`) | (none) | **Nemotron**. |
| `evals/` (new) | (none) | **Mimo**. |
| `ci/` (new) | (none) | **Project Manager**. |

The three-owner split (Mimo / Nemotron / Project Manager) is sound but under-specified. Add **interface contract owner = Project Manager**: freeze `aria_core/interfaces.py` and `output_planner/interfaces.py` for the duration of a milestone; any change requires PM review. This resolves the Mimo+Nemotron collision rule.

### Risk register (top 5)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite schema drift breaks long-running memory | Medium | High | Versioned schema, `schema_version` field on items, migration script in repo. |
| Async migration breaks existing tests | High | Low | Run old and new entry points side-by-side until parity suite passes. |
| Tool execution is OS-specific (Windows in this codebase) | Medium | Low | Detect OS, fall back to error event, document limitation. |
| mypy --strict surfaces a large backlog | High | Low | Per-module overrides, enable strict incrementally. |
| Dependency pinning breaks reproducibility | Medium | Medium | Pin to known-good versions; weekly dependabot; document upgrade. |

---

## 6. Immediate Next Milestones (ordered by engineering value)

### Milestone 1 — "Configuration and Pipeline Consolidation" (3–5 days, Project Manager)

- `aria_project/config.py` with `ARIAConfig` dataclass.
- `aria_project/pipeline.py` with `Pipeline` and `run_pipeline(text) -> PipelineResult`.
- `requirements.txt` + `requirements-dev.txt` + `pyproject.toml` (ruff, mypy, project metadata).
- `main.py` and `text_mode_loop.py` become thin wrappers around `Pipeline`.
- Tests: full pipeline parity (text-mode vs headless audio mode).
- Fix `output_planner/rule_based.py:17-19` (B1).
- Fix `ui/aria_ui.py:264` `Any` import (B12).
- Add `event_bus.clear()` (C5, B15).
- Replace per-call `asyncio.run()` with a long-lived loop (C2).
- Delete `language_cortex/models/llama_cpp.py` (D1).
- **Demo**: `pip install -e .`, `python -m aria --mode headless`, `python -m aria --mode ui`. Both work from one config.

### Milestone 2 — "ARIA Remembers" (1 week, Mimo)

- `aria_core/persistence/interfaces.py` with `PersistenceProtocol`.
- `aria_core/memory/sqlite_memory_system.py` implementing `MemorySystemProtocol` on top of SQLite.
- `aria_core/goals.py` extended with `SQLiteGoalStore`.
- `ActionExecutor` Protocol + `ToolRegistry` with `launch_application`, `set_reminder`, `cancel_reminder`, `current_time`.
- `record_outcome()` on memory.
- Worker loop dispatches tools and records outcomes.
- Tests: round-trip 50 episodes, restore goals after restart, retrieve semantic facts after restart.
- **Demo**: Kill mid-conversation, restart, "what were we talking about?" → answer from memory. `launch_application("notepad")` → Notepad opens.

### Milestone 3 — "ARIA Listens" (3–4 days, Nemotron)

- `language_cortex/factory.py` so entry points don't `__import__` inline.
- `ConversationTurn` + `Session` flow through pipeline.
- `LanguageCortex.chat(turns, retrieved, **kwargs)`.
- `LLMBasedInputInterpreter` / `LLMBasedOutputPlanner` wired through factory.
- Decision maker consumes last N turns.
- Token-budgeted context window for cortex.
- Tests: 3-turn "open notepad → type hello → what did I just say?" works.
- **Demo**: Multi-turn conversation, ARIA references earlier turns.

### Milestone 4 — "ARIA Ships" (3–5 days, Project Manager)

- `ActionType` / `Tone` / `Priority` / `Urgency` enums.
- `Plan` dataclass.
- GitHub Actions: ruff, mypy --strict, unittest, coverage.
- Pre-commit hooks.
- Structured JSON logging with correlation IDs.
- `docs/architecture.md`, `docs/privacy.md`, `docs/development.md`.
- Rewrite `docs/SESSION_REPORT.md` truthfully (drop the "production-ready" claim).
- **Demo**: A new contributor can `git clone && pip install -e . && pre-commit install && pytest` and have a clean baseline.

### Milestone 5 — "ARIA Reasons" (1 week, Mimo)

- 30-utterance eval set.
- Regression test gates decision accuracy.
- Decision maker scoring uses `EpisodicItem.outcome` as the primary reinforcement signal.
- Embedding-based goal relevance (replace naive token intersection).
- **Demo**: A change to the decision maker that drops eval accuracy fails CI.

---

## 7. CTO Directives (operational, effective immediately)

1. **No new features until Priority 0 is merged.** The duplication and the `asyncio.run`-per-call pattern must be resolved before any new layer is added. Adding to a duplicated entry point compounds the cost of fixing it.
2. **Mimo owns `aria_core/` exclusively.** Nemotron owns `input_interpreter/`, `language_cortex/`, `output_planner/`, `ui/`. Project Manager (CTO) owns `config.py`, `pipeline.py`, `event_bus.py`, `aria_logging.py`, `tests/`, `docs/`, `tools/`, `evals/`, CI.
3. **Interfaces freeze for the milestone.** `aria_core/interfaces.py` and `output_planner/interfaces.py` are frozen during Milestone 1. Any change requires PM review.
4. **Every PR must run `ruff check`, `mypy aria_core`, `python -m unittest discover -s tests`.** This will be enforced in CI once Milestone 4 lands; until then, the PM runs them locally before merge.
5. **Every change must update the test suite.** If you change a public function, add a test. If you can't, justify it in the PR description.
6. **`SESSION_REPORT.md` will be rewritten to be truthful** as part of Milestone 4. The "production-ready" claim is retracted.
7. **No new dependencies without discussion.** Add to `requirements.txt` only after PM approval and a note in `docs/CURRENT_TASKS.md`.
8. **Use `AskUserQuestion` or interrupt only for**:
   - Major architectural decisions not covered in this audit.
   - Credentials or secrets.
   - Destructive operations (deletes, force-pushes, schema migrations on real data).

---

## 8. Conclusion

The previous CTO's autonomous session delivered real, valuable work: the memory layer is genuinely good, the event bus is correct in its core mechanism, the protocols are well-defined, and 56 tests pass. The session report overstates this. The project is a runnable prototype with disciplined hygiene and a clean architecture in places, but with no persistence, no feedback loop from outcomes, no CI, no dependency manifest, and a duplicated configuration that has already drifted.

The path forward is not to preserve this work — it is to build on it. Priorities 0–1 fix the foundation. Priority 2 builds the missing feature (memory + tools + outcomes) that makes ARIA actually cognitive. Priorities 3–5 add the operational scaffolding and the multi-turn context that turn a prototype into a product. The roadmap is a sequence of 5 milestones over ~5 working weeks.

I am assuming the role of CTO and Engineering Manager. Mimo and Nemotron have new work queued (see §6). The prior roadmap is retired; the revised one is in §5. Tests must remain green; the architecture must evolve; the documentation must be truthful.

**The goal is not to preserve the previous CTO's work. The goal is the best possible version of ARIA.**
