# Milestone 1 — Configuration and Pipeline Consolidation (frozen for this milestone)

This contract is **frozen for Milestone 1**. Any change requires PM (CTO) review.

This milestone is split into two ownership slices:

* **M1.Nemotron** — Nemotron-owned deliverables (CTO is the integration point).
* **M1.PM** — PM-owned deliverables (CTO is the executor of record).

---

## 1. M1.Nemotron — code in Nemotron's directories

### 1.1 Fix B1 — falsy-value silent override in `output_planner/rule_based.py`

**File**: `output_planner/implementations/rule_based.py`

The current code (lines 17-19):
```python
urgency = decision.urgency or base["urgency"]
tone = decision.tone or base["tone"]
priority = decision.priority or base["priority"]
```

**Problem**: `or` falls through on *any* falsy value (`""`, `0`, `False`), not just `None`. If the caller deliberately sets `priority=""` to mean "no priority", they silently get `"high"`.

**Fix**: explicit `is None` check. Only fall through when the field is genuinely unset.

```python
urgency = base["urgency"] if decision.urgency is None else decision.urgency
tone = base["tone"] if decision.tone is None else decision.tone
priority = base["priority"] if decision.priority is None else decision.priority
```

**Acceptance**:
* New test `test_rule_based_preserves_explicit_falsy.py` in `tests/` (or appended to an existing rule-based test file).
* Test cases: explicit empty-string urgency/tone/priority round-trips through unchanged.
* Existing 134 tests still pass.

### 1.2 Fix B12 — `Any` import missing in `ui/aria_ui.py`

**File**: `ui/aria_ui.py`

Line 11: `from typing import Dict` — missing `Any`.

Line 264: `def _on_thought_generated(self, payload: Any)` references `Any`.

**Fix**: change line 11 to `from typing import Dict, Any`.

**Acceptance**:
* `typing.get_type_hints(ARIAUI._on_thought_generated)` no longer raises `NameError`.
* `mypy ui/aria_ui.py` no longer reports `[name-defined]` for `Any`.

### 1.3 Fix C2 — `asyncio.run` per call → long-lived loop

**Files**: `main.py`, `text_mode_loop.py` (PM-owned, but the worker logic lives here; Nemotron owns the pattern; PM coordinates).

Current: `main.py:109-111` and `text_mode_loop.py:120-122` define `def run_async(coro): return asyncio.run(coro)` and call it four times per turn.

**Pattern (Nemotron designs, PM integrates)**:

Add `aria_core/async_runtime.py` with:

```python
class AsyncRuntime:
    """Owns a single asyncio loop running in its own daemon thread."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def run(self, coro: Coroutine) -> Any:
        """Submit coro to the loop and block until it returns. Thread-safe."""
        ...
```

`run()` uses `asyncio.run_coroutine_threadsafe(coro, self._loop).result()`.

In `main.py` / `text_mode_loop.py`:
* Replace `def run_async(coro): return asyncio.run(coro)` with `runtime.run(coro)`.
* Start one `AsyncRuntime` at worker boot; stop it on shutdown.

**Acceptance**:
* One event loop, alive for the duration of the worker, instead of one per call.
* Existing 134 tests still pass (most don't touch async; the async-related tests stay green).
* New test `test_async_runtime.py` exercising start/submit/stop ordering and exception propagation.

### 1.4 Delete D1 — `language_cortex/models/llama_cpp.py` stub

**File**: `language_cortex/models/llama_cpp.py`

This module raises `NotImplementedError` from `__init__`. It is unreachable code — a footgun.

**Steps**:
1. `grep -r llama_cpp` to confirm nothing imports it. (Verified during this audit: zero importers.)
2. `git rm language_cortex/models/llama_cpp.py`.

**Acceptance**:
* File gone from the tree.
* No import errors anywhere.

### 1.5 Re-wire m11/m12 — remove dead `LLMBasedInputInterpreter` / `LLMBasedOutputPlanner` paths **OR** wire them via factory

This is a **design decision**, not a code change.

`LLMBasedInputInterpreter` and `LLMBasedOutputPlanner` exist but are not reached through `build_input_interpreter` / `build_output_planner` factories. Per the audit:

> Either wire or remove.

**Nemotron must decide and document**: keep them and wire, or remove them entirely. For M1, the minimum bar is **one of the two**, with the rationale written into `docs/M1_REVIEW.md` later. M3 may need them. Recommend: **keep and wire via factory**, because M3 multi-turn context will benefit from an LLM-interpreted `StructuredInput`.

---

## 2. M1.PM — code in PM directories

### 2.1 Add `event_bus.clear()`

**File**: `event_bus.py`

Add:

```python
def clear(self) -> None:
    """Drop every subscriber. Used by tests and by worker restarts."""
    with self._lock:
        self._subscribers.clear()
```

**Acceptance**:
* Test `test_event_bus.py` (new or extended) verifies `clear()` empties all subscribers, subsequent `publish()` is a no-op, and `subscribe()` after `clear()` works.
* Existing 134 tests still pass.

### 2.2 Add `aria_project/config.py`

**File**: `aria_project/config.py`

```python
@dataclass(frozen=True)
class ARIAConfig:
    mode: Literal["headless", "ui"] = "headless"
    input_interpreter: InterpreterConfig = ...
    output_planner: PlannerConfig = ...
    language_model: LanguageModelConfig = ...
    memory: MemoryConfig = ...
    tools: ToolsConfig = ...
    runtime: RuntimeConfig = ...
```

Plus `load_config(path: Path | None = None) -> ARIAConfig` that:
* Reads YAML if `path` is given.
* Reads environment variables (`OPENAI_API_KEY`, etc.).
* Validates against the dataclass schema (raises `ConfigError` on bad input).
* Falls back to mock model if no API key.

**Replaces** the two duplicate `_load_config()` functions in `main.py` and `text_mode_loop.py`. The PM owns this and integrates.

**Acceptance**:
* `python -m aria_project.config --print` outputs the resolved config.
* `main.py` and `text_mode_loop.py` both call `load_config()` from this module.
* Existing tests still pass.

### 2.3 Add `aria_project/pipeline.py`

**File**: `aria_project/pipeline.py`

A `Pipeline` class that orchestrates: `interpret → decide → plan → execute → respond`, plus:

```python
@dataclass(frozen=True)
class PipelineResult:
    structured_input: StructuredInput
    decision: ARIDecision
    plan: dict
    tool_result: ActionResult | None
    response: str

def run_pipeline(
    raw_input: str,
    *,
    cfg: ARIAConfig,
    runtime: AsyncRuntime,
    interpreter: InputInterpreterProtocol,
    planner: OutputPlannerProtocol,
    decision_maker: DecisionMakerProtocol,
    cortex: LanguageCortexProtocol,
    tool_registry: ToolRegistry,
) -> PipelineResult: ...
```

**Acceptance**:
* Existing 134 tests still pass.
* `text_mode_loop.py` and `main.py` both call `run_pipeline(...)` instead of inlining the loop.

### 2.4 Refactor `main.py` and `text_mode_loop.py` to thin wrappers

After `config.py` and `pipeline.py` exist, both entry points should be:

* `main.py`: parse argv → load config → build components → start UI + worker (worker calls `run_pipeline`).
* `text_mode_loop.py`: parse argv → load config → build components → loop: read line → run_pipeline → print.

Both should fit in **< 80 lines** after the refactor.

### 2.5 Add project tooling

**Files**: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`

```toml
# pyproject.toml
[project]
name = "aria"
version = "0.2.0"
requires-python = ">=3.10"
dependencies = [
    "customtkinter>=5.2.0",
    "speechrecognition>=3.10.0",
]

[project.optional-dependencies]
dev = ["ruff>=0.4.0", "mypy>=1.10.0", "pytest>=8.0.0"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict_optional = true
ignore_missing_imports = true
```

**Acceptance**:
* `pip install -e .[dev]` succeeds.
* `ruff check .` runs clean (or only flags third-party and legacy issues; record the latter in `docs/M1_REVIEW.md`).
* `mypy aria_core/` runs clean.

---

## 3. What M1 does NOT touch

* `aria_core/memory/sqlite_memory_system.py` — already landed in M2.
* `aria_core/execution/*` — M2.
* `aria_core/persistence/*` — M2.
* `tests/test_m2_*` — M2.
* `docs/M2_CONTRACT.md`, `docs/M2_REVIEW.md` — frozen.

---

## 4. Test requirements

* All existing 134 tests still pass.
* New tests (Nemotron): `test_rule_based_preserves_explicit_falsy.py`, `test_async_runtime.py`, `test_event_bus_clear.py`.
* New tests (PM): `test_config.py`, `test_pipeline.py`.
* Final test count target: **134 + ~15 = ~149 tests, all green**.

---

## 5. Two checkpoint runs

Per CTO directive, the **full regression suite** (`python -m unittest discover -s tests`) must run:

1. After the architectural refactor (`pipeline.py` integration, `main.py` / `text_mode_loop.py` thin-wrapper conversion).
2. After introducing the new tooling (`ruff`, `mypy`, `pyproject.toml`).

Both runs must report green. Failure on either checkpoint blocks M1 sign-off.

---

## 6. Acceptance criteria for M1

1. `python -m unittest discover -s tests` reports ≥ 134 tests, all green.
2. `ruff check .` and `mypy aria_core/` both clean (or legacy issues documented).
3. `pip install -e .` succeeds from a fresh venv.
4. `python -m aria_project.config --print` resolves the default config.
5. `python -m aria_project --mode headless` and `--mode ui` both work from one config.
6. `from aria_core.execution.registry import ToolRegistry` still works (M2 surface intact).
7. **No new dependencies without PM approval** (recorded in `docs/M1_REVIEW.md`).

---

## 7. Git hygiene

* One commit per logical change (B1, B12, C2, D1, m11/m12, event_bus.clear, config.py, pipeline.py, refactor main/text_mode_loop, pyproject+ruff+mypy).
* Co-authored-by line on every commit, attributing the work to the owning engineer.
* No modifications outside the milestone's owned directories except `tests/` and the contract doc itself.
