# ARIA Cognitive OS — Design Specification

**Status:** Architecture proposal, v0.1
**Date:** 2026-07-11
**Scope:** Pluggable environments + cognitive transparency UI for ARIA

---

## 0. What this document is

This is not a UI mockup. It is an architecture for a **cognitive operating system** — a runtime in which any ARIA core (the existing `aria_core/decision_maker.py` + memory + goals + influence + reflection stack) can be embedded inside any environment that speaks a small contract, and observed by any front-end that wants to understand *why it did what it did*.

The deliverable is structured in three layers:

1. **Environment Contract** — the minimal interface every world (maze, city, civ, internet, robot) must implement.
2. **Cognitive Event Schema** — the typed events emitted by ARIA that any UI renders. The brief's nine-step pipeline (Observation → Memory → Hypothesis → Prediction → Decision → Action → Outcome → Learning → Emotion) is a faithful 1:1 with events already partially emitted on `event_bus` — this spec formalizes them and fills the four missing ones.
3. **UI Shell** — a three-zone reactive shell (Map / Brain / Thought Stream) with Dream Mode as a state, not a screen.

The brief asked for "production-quality architecture, reusable components, clean abstractions, extensible systems." Each section ends with the file-level plan and the contract an implementer signs.

---

## 1. Architectural invariants

These hold across every environment, every UI, every agent. Violate one and the abstraction breaks.

**I-1. ARIA never knows what environment it is in.** ARIA receives an `Observation` and produces an `Action`. The two are typed dicts; their schemas are part of the env contract, not the core.

**I-2. Every cognitive step is an event on the bus.** The brain is a stream. The UI does not poll the core — it subscribes. This is the only way the same ARIA can drive a CLI, a Tkinter face, a 3D city, or a remote dashboard.

**I-3. The thought stream is append-only and reproducible.** Every step that contributed to a decision is recorded with the same `episode_id` and is queryable after the fact. The UI can replay.

**I-4. Emotion is a first-class state, not a label.** Confidence, curiosity, frustration, motivation, caution, persistence, novelty — each has a value, a *delta*, and a *cause* (which cognitive event changed it and why). The brief's "every emotion must explain why it changed" is enforced at the type level, not as a UI courtesy.

**I-5. The environment is replaceable without touching the core.** A maze that emits `Observation { position, walls_ahead }` and accepts `Action { move: str }` and a city that emits `Observation { npc_id, position, visible_agents, weather, time_of_day, market_state }` and accepts `Action { build_road, dispatch_police, observe_area, ... }` both run on the same `aria_core`.

**I-6. The UI is replaceable without touching the core.** Tkinter, web, terminal, headless benchmark — all bind to the bus. No widget imports `aria_core`.

**I-7. The dream loop is a first-class cognitive mode.** Sleep consolidation, semantic extraction, identity updates, and forgetting are not background tasks — they are observable processes that emit events like any other step.

---

## 2. Environment Contract

### 2.1 The interface

```python
# aria_core/environment/contract.py
from typing import Protocol, Any, runtime_checkable
from dataclasses import dataclass, field
from datetime import datetime

@runtime_checkable
class Environment(Protocol):
    """The smallest interface an environment must satisfy."""

    def reset(self, seed: int | None = None) -> Observation: ...
    def step(self, action: Action) -> tuple[Observation, float, bool, dict]: ...
    def observe(self, agent_id: str | None = None) -> Observation: ...
    def get_state(self) -> WorldSnapshot: ...
    def list_actions(self) -> list[ActionSchema]: ...
    def render(self, mode: str = "ui") -> Any: ...
    def spec(self) -> EnvironmentSpec: ...
```

Six methods, none of them optional. The signature follows Gymnasium's `step` convention so any RL practitioner can map it to their training loop in their head; the additions (`observe`, `get_state`, `list_actions`, `render`, `spec`) make it usable for transparency UI.

### 2.2 The schemas

```python
@dataclass
class Observation:
    """What ARIA sees at this tick."""
    agent_id: str
    tick: int
    timestamp: datetime
    # The environment defines what is inside `data`. ARIA never inspects
    # the shape — it goes to the perception layer (aria_core/perception/).
    data: dict[str, Any]
    # What the agent's body can perceive (line-of-sight, range, etc.).
    # Optional; not every env has it.
    modality: str = "symbolic"
    # Free-form attention cues ("a loud noise came from sector 3").
    salience: dict[str, float] = field(default_factory=dict)

@dataclass
class Action:
    """What ARIA wants to do."""
    agent_id: str
    action_type: str          # validated against env.spec().action_space
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str | None = None   # ARIA's reason, for the thought stream
    confidence: float = 1.0

@dataclass
class WorldSnapshot:
    """Everything the UI needs to render the world, every tick."""
    tick: int
    time_of_day: float          # 0..24
    day: int
    season: str
    weather: str
    agents: list[AgentSnapshot]
    resources: dict[str, float]
    buildings: list[BuildingSnapshot]
    roads: list[RoadSegment]
    events: list[WorldEvent]
    metrics: dict[str, float]

@dataclass
class AgentSnapshot:
    id: str
    name: str
    occupation: str
    position: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    mood: dict[str, float] = field(default_factory=dict)
    current_task: str = ""
    inventory: dict[str, float] = field(default_factory=dict)
    alive: bool = True
    is_aria: bool = False       # the ARIA-controlled agent, if any
    thought: str = ""           # last thought-stream entry for this agent

@dataclass
class EnvironmentSpec:
    name: str                          # "SmallCity-v0", "Maze-v0", ...
    version: str
    observation_space: dict[str, Any]  # JSON schema
    action_space: list[ActionSchema]
    max_ticks: int
    population_range: tuple[int, int]
    description: str
```

`ActionSchema` is a typed catalog — this kills the bug `aria-known-bugs.md B1` flagged in a different form: actions are no longer stringly typed at the env boundary.

### 2.3 The contract is bilateral

ARIA does not own the env's vocabulary. The env publishes its `ActionSchema`, and ARIA's output planner *must* validate before emission. This is the same discipline the audit asked for in `_ACTION_TYPES` — promoted from a constant to a contract.

### 2.4 What changes in the existing code

`aria_world/world.py:122` (`WorldEngine.tick`) becomes a `step` method. `aria_world/visualization.py` already does ASCII — it gets promoted to a `render(mode="ui")` returning a structured dict (not a string). The `WorldEngine` becomes a candidate `Environment` implementation called `SmallCityEnvironment`. Same for any future `MazeEnvironment`, `InternetEnvironment`, `RobotEnvironment`.

**Files to add:**

- `aria_core/environment/__init__.py`
- `aria_core/environment/contract.py` — the Protocol + dataclasses above.
- `aria_core/environment/registry.py` — `register(name, factory)`, `make(name, **kwargs)`, used by the UI to launch any env by name without an import.
- `aria_core/environment/validation.py` — validates an `Action` against the env's `ActionSchema` *before* `env.step` is called. Emits `ActionRejected` on failure with a reason.

**Files to modify:**

- `aria_world/world.py` — split `tick()` into `observe()` + `step(action)` so ARIA can drive a single NPC (the `ARIA-controlled agent`).
- `aria_world/agent.py` — `live_one_day` becomes the default policy for non-ARIA NPCs; ARIA-controlled NPCs use the core.

### 2.5 Non-goals (explicit)

- We are **not** building a Gymnasium-compatible training API. The `step` signature *looks* like one, but the return is `(obs, reward, done, info)` only because that's the cheapest way to type it. No vectorized envs, no parallel samplers.
- We are **not** building a "scene graph." `WorldSnapshot` is a flat list of typed records. The renderer composes them. If a future env needs octrees, it adds a field to `WorldSnapshot` — the contract grows.
- The maze environment is **not** being deleted. It becomes the simplest possible `Environment` and stays as the smoke test in CI.

---

## 3. Cognitive Event Schema

### 3.1 The full pipeline

The brief gives nine steps. Existing code covers six of them. Three are missing. Here is the canonical stream, with what already emits, what is missing, and the typed payload.

| # | Step | Existing event | Missing? | Payload (canonical) |
|---|------|----------------|----------|---------------------|
| 1 | Observation | (implicit) | yes — env fires on `step` | `{"episode_id", "agent_id", "obs": Observation, "tick"}` |
| 2 | Memory Retrieved | (none) | **missing** | `{"episode_id", "agent_id", "cues", "matches": [(item_id, kind, relevance, snippet)], "total"}` |
| 3 | Hypothesis Generated | (none) | **missing** — `aria_core/reasoning/multi_hypothesis.py` exists, not yet wired to bus | `{"episode_id", "agent_id", "hypotheses": [(id, text, prior, support)]}` |
| 4 | Prediction | (none) | **missing** | `{"episode_id", "agent_id", "predicted_outcome", "predicted_reward", "model_id"}` |
| 5 | Decision | `DecisionMade` | exists, payload is `ARIDecision` | `{"episode_id", "agent_id", "decision": ARIDecision, "scores": {action: score}, "chosen_reason"}` |
| 6 | Action | `ActionPlanned` | exists | `{"episode_id", "agent_id", "action": Action, "validated": bool}` |
| 7 | Outcome | (none) | **missing — bug C4 in [[aria-known-bugs]]** is that `EpisodicItem.outcome` is write-once `None` | `{"episode_id", "agent_id", "result", "reward", "surprise", "delta_prediction"}` |
| 8 | Learning | (none) | **missing — outcome→memory loop absent** | `{"episode_id", "agent_id", "memory_updates": [(item_id, delta, reason)], "influence_shift", "skill_delta"}` |
| 9 | Emotion | `InternalState` | exists, but no `delta` or `cause` fields — brief requires them | `{"episode_id", "agent_id", "state": {dim: val}, "delta": {dim: Δ}, "cause": {dim: "reason"}}` |

### 3.2 The event bus contract

```python
# aria_core/cognition/events.py
from dataclasses import dataclass, field
from typing import Any
import uuid, time

# Canonical event names. Importers use these, not raw strings.
class Event:
    OBSERVATION    = "cognition.observation"
    MEMORY_RETRIEVED = "cognition.memory_retrieved"
    HYPOTHESIS     = "cognition.hypothesis"
    PREDICTION     = "cognition.prediction"
    DECISION       = "cognition.decision"          # supersedes DecisionMade
    ACTION         = "cognition.action"            # supersedes ActionPlanned
    OUTCOME        = "cognition.outcome"
    LEARNING       = "cognition.learning"
    EMOTION        = "cognition.emotion"           # supersedes InternalState
    DREAM_START    = "cognition.dream.start"
    DREAM_REPLAY   = "cognition.dream.replay"
    DREAM_CONSOLIDATE = "cognition.dream.consolidate"
    DREAM_EXTRACT  = "cognition.dream.extract"
    DREAM_FORGET   = "cognition.dream.forget"
    DREAM_END      = "cognition.dream.end"

@dataclass
class CognitiveEvent:
    episode_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    event: str = ""            # one of Event.*
    tick: int = 0
    t: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
```

Every cognitive emitter wraps its payload in this envelope. The UI never has to guess the shape. `episode_id` joins the nine steps for the same decision into a single replayable unit.

### 3.3 The Emotion type (this is the hard one)

The brief demands `Confidence ↓ / Reason: Prediction failed.` That is not a label — it is a *cause attribution*. The existing `Personality.to_cognitive_modifiers()` (`aria_world/models.py:118`) returns a static modifier map. It does not track state.

```python
# aria_core/cognition/emotion.py
from dataclasses import dataclass, field
from collections import deque

EMOTION_DIMS = ("confidence", "curiosity", "frustration", "motivation",
                "caution", "persistence", "novelty")

@dataclass
class EmotionDelta:
    dim: str
    delta: float
    cause_episode_id: str
    cause_event: str
    cause_text: str

@dataclass
class EmotionState:
    values: dict[str, float] = field(default_factory=lambda: {d: 0.5 for d in EMOTION_DIMS})
    recent: deque[EmotionDelta] = field(default_factory=lambda: deque(maxlen=32))
    # The last N explanations per dimension, so the UI can show "why this number".

    def apply(self, delta: EmotionDelta) -> None:
        if delta.dim not in self.values:
            return
        old = self.values[delta.dim]
        # Bounded random-walk with momentum toward the cause's value.
        new = max(0.0, min(1.0, old + delta.delta))
        self.values[delta.dim] = new
        self.recent.appendleft(delta)

    def explain(self, dim: str) -> list[EmotionDelta]:
        return [d for d in self.recent if d.dim == dim]
```

Cause attribution rules — encoded once, reused everywhere:

| Event | Dim | Δ | Cause template |
|-------|-----|---|----------------|
| Outcome.surprise > 0.5 | confidence | −0.1 · surprise | "Prediction failed: predicted {pred}, got {actual}." |
| Observation.novelty > 0.7 | curiosity | +0.1 | "Unknown object discovered: {entity}." |
| Outcome.reward < threshold, repeated 3+ times | frustration | +0.15 | "Repeated failure at {task}." |
| Goal progress > 0 | motivation | +0.05 | "Goal '{goal}' advanced." |
| Outcome.danger == true | caution | +0.1 | "Threat detected: {source}." |
| Outcome.success | persistence | +0.05 | "Approach worked for {task}." |
| Memory.semantic.new | novelty | +0.05 | "New concept learned: {concept}." |

This is a lookup table, not a learned model. Every entry is auditable. The UI shows the most-recent cause per dim — one line, human-readable.

### 3.4 What changes in existing code

- `aria_core/decision_maker.py:88` `decide()` becomes a context manager that owns an `episode_id` and emits `Observation → MemoryRetrieved → Hypothesis → Prediction → Decision → Action` in order, before returning. Each step is a `bus.publish` call.
- `aria_core/memory/models.py` `EpisodicItem.outcome` becomes a real `Outcome` field settable after execution — this **fixes bug C4** at the same time.
- A new `aria_core/cognition/learning.py` wires the `Outcome` event back to memory (importance update, episodic link, semantic extraction) and emits `Learning`. This is the missing feedback loop.
- The `cognition/emotion.py` module above subscribes to `Outcome`, `Observation`, `Learning` and emits `Emotion`.

### 3.5 Files to add (cognition layer)

- `aria_core/cognition/__init__.py`
- `aria_core/cognition/events.py`
- `aria_core/cognition/emotion.py`
- `aria_core/cognition/learning.py`
- `aria_core/cognition/prediction.py` — a simple learned-world-model stub: predict next state from (current_state, action), return surprise as `||pred − actual||`. Real model later; the *shape* of the event is fixed now.

---

## 4. UI Shell — the three zones

The shell is a layout, not a screen. The whole system lives in one window with three regions, and one global state (`mode: awake | dream | frozen`). Every region subscribes to the bus and re-renders from `CognitiveEvent`s.

```
┌─────────────────────────────────────────────────────────────────┐
│  Top bar:   Day 14 · Spring · Rain · Population 42 · FPS 60     │
├──────────────────────────────────────────┬──────────────────────┤
│                                          │  Brain Sidebar       │
│                                          │  ──────────────────  │
│                                          │  Emotion (with cause)│
│            MAP ZONE                      │  Goals (active)      │
│     (city, maze, civ, planet)            │  Memory (typed)      │
│     zoom + pan + select                  │  Action Panel        │
│                                          │  World Inspector     │
│                                          │                      │
├──────────────────────────────────────────┴──────────────────────┤
│  THOUGHT STREAM — Observation → Memory → Hypothesis → ...        │
│  append-only, color-coded by step, click to expand episode       │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 Map Zone

- Renders `WorldSnapshot` every render tick (60 Hz target, decoupled from sim tick).
- Layers, in z-order: roads → buildings → districts → parks → traffic → pedestrians → ARIA agents → events.
- Camera: pan with drag, zoom with wheel, `+`/`-` keys, `F` to focus the ARIA agent, `1..9` to focus a specific NPC.
- Selection: click an NPC opens the **NPC Inspector** floating panel; click a building opens a building inspector; click empty space deselects.
- Performance budget: 100 NPCs × 60 FPS = 6 000 sprite updates per second. Use Canvas2D with a single dirty-rect redraw, or WebGL if the UI host is web.

### 4.2 Brain Sidebar (the "right side" of the brief)

Stacked, always visible, never empty. Each section is a self-contained component bound to one or more bus events.

| Section | Subscribes to | Renders |
|---------|---------------|---------|
| **Emotion Panel** | `cognition.emotion` | One row per `EMOTION_DIMS`. Each row: dim name, current value as a horizontal bar, arrow (↑/↓/→), and the most-recent `cause_text`. Hover shows the last five causes. |
| **Active Goals** | `cognition.decision` (filtered to action_type=execute or relevant) | List of `Goal` with priority chip, progress bar, deadline countdown, and a "linked memories" count. |
| **Memory (typed)** | `cognition.memory_retrieved` (transient) + `memory_stored` (persistent) | Tabs: Episodic / Semantic / Procedural / Identity / Value / Perception. The currently-retrieved memories are highlighted for 2 s. Clicking a memory card opens a detail panel with timestamp, importance, emotion, retrieval count, reinforcement count, origin. |
| **Action Panel** | `cognition.action` (display only) + user input | A grid of action buttons sourced from the env's `list_actions()`. Disabled if env rejects. On click, the user becomes the ARIA agent for one tick. |
| **World Inspector** | `WorldSnapshot` | Day, season, weather, economy, population, traffic, food, energy, water, crime, education, health, major events. |

Every component subscribes to exactly the events it needs. No polling. This is enforced by a single rule in code review: a panel that calls `bus.publish` does not exist; a panel that calls into `aria_core` directly is a bug.

### 4.3 Thought Stream (the most important panel)

This is the brief's "users should literally watch cognition unfold." It is a vertical, auto-scrolling, append-only log. Each entry is one row of the nine-step pipeline.

```
[14:32:07.041]  ▸ Observation     position=(0.34, 0.66); weather=rain; npc_42 nearby
[14:32:07.042]  ▸ Memory          3 matches (top: "rain → seek shelter", rel=0.81)
[14:32:07.043]  ▸ Hypothesis      H1: stay inside (prior 0.6)  H2: go to market (prior 0.3)
[14:32:07.044]  ▸ Prediction      H1 → safety↑, hunger↑; H2 → hunger↓, safety↓
[14:32:07.045]  ▸ Decision        action=execute(stay_inside)  score=1.42
[14:32:07.046]  ▸ Action          dispatched
[14:32:07.512]  ▸ Outcome         safety +0.3, hunger +0.1, surprise=0.12
[14:32:07.513]  ▸ Learning        reinforced 2 memories; updated 1 semantic fact
[14:32:07.514]  ▸ Emotion         confidence↑ (cause: prediction matched)
```

All nine rows share an `episode_id` badge on the left edge. Clicking the badge opens a side panel showing the full structured payload (debug view). The stream is filterable by step, agent, or time range.

Color is information, not decoration. Each step has a fixed hue and the line carries a left-border accent in that hue. The active row pulses softly during emission, then settles. **No particles. No glitch effects. No decorative motion.**

### 4.4 NPC Inspector (click an NPC)

Modal-ish: opens as a left-docked drawer that does not cover the map. Contents:

- Identity: name, age, occupation, portrait (or colored ring fallback).
- Current state: goal, current task, mood, location, velocity, alive.
- Inventory: read-only resource list.
- Relationships: top-5 trust edges (uses `RelationshipGraph` from `aria_world/relationships.py`).
- Thought: a small embedded thought stream filtered to this NPC's `agent_id`.
- Predicted next action: read from the last `cognition.prediction` for this agent.

The ARIA agent's own row in the NPC list has a thin ARIA-colored ring to distinguish it from NPCs running their default policy.

### 4.5 World Inspector

A scrollable card grid. Each metric is a tile: title, value, delta from last tick, 30-tick sparkline. Built directly from `WorldSnapshot.metrics` and the env's own stats. The tile *is* the data — no extra layout chrome.

### 4.6 Action Panel

A simple grid of buttons. Buttons come from `env.list_actions()`. Disabled state when the env rejects the action or the ARIA agent is not in a state where the action is legal. A small text field accepts free-form "directives" — these are packaged as `Action(action_type="directive", params={"text": ...})` and passed to the env for interpretation. The env decides what they mean.

### 4.7 Dream Mode (state, not screen)

`mode = dream` is a global flag emitted on the bus by the env (or by a scheduled trigger). When active:

- The whole window gains a dark overlay (single solid color, no blur or noise).
- The map's simulation tick slows to ¼ speed.
- The thought stream filters to `cognition.dream.*` events.
- The brain sidebar switches to a "Consolidation" view: replaying memories, patterns being extracted, identity updates, forgetting.
- The ARIA agent's avatar (if shown) dims to 50% alpha.

These are five things changing on one state. Not a separate screen, not a transition animation, not a re-mount. Switching `mode` back to `awake` reverses them. The brief's signature feature works because the rest of the system was already event-driven; dream mode is one new subscriber and one new overlay.

---

## 5. Visual system

- **Stack:** PyQt6 or PySide6. CustomTkinter is the existing choice and the existing UI is 460×620 — that size is incompatible with the brief ("Google Earth, not a game"). PySide6 gives a true retained-mode scene graph and a stylesheet system that produces a Linear/Apple aesthetic without CSS-in-QSS hacks.
- **Theme:** Single dark theme, defined in one stylesheet. Two surface tones (`#0E0F11`, `#16181C`), one elevated (`#1E2127`), one accent (`#7C5CFF`), one success (`#3FB950`), one warn (`#D29922`), one error (`#F85149`). Text uses one neutral scale (5 steps). No additional colors.
- **Typography:** One sans family (Inter, system fallback). Three sizes only (12, 14, 18). No italics, no underlines, no all-caps. Numerics in tabular figures.
- **Iconography:** 16/20 px line icons from a single set. No emoji in the chrome (emoji are fine *inside* thought-stream text).
- **Motion:** 120 ms eased transitions for state changes. Nothing slower, nothing bouncier. No idle animations. No gradients in the chrome.
- **Charts:** Sparklines and bar charts use the same five accent colors. Tooltip on hover. No 3D, no shadows beyond a single 1-px divider.
- **Density:** The brain sidebar is dense on purpose. Cognitive state has a lot of data; white space would hide it.

These are rules, not aspirations. A PR that adds a gradient, a glow, or a bouncy animation gets rejected.

---

## 6. Concrete plan for the first demo (Small City)

The brief names Small City as the v1 target. The existing `aria_world` is already a 10–20 agent village with knowledge, culture, and conflict — it is functionally a small city. The work for v1 is therefore:

1. **Promote the world.** `aria_world/world.py` becomes a `SmallCityEnvironment` that implements the Section 2 contract. Configurable population 30–100 (the brief's number) — the existing cap is 20 and needs raising in `aria_world/config.py:11`. Add roads, districts, weather, time-of-day, traffic, and random events on top of what's there.
2. **Promote an NPC to ARIA.** The brief's "ARIA controlled agents" line means at least one city resident is driven by `aria_core/decision_maker.py`, not by `live_one_day`. The Map Zone highlights this agent with the accent color.
3. **Wire the cognition events.** Sections 3.1–3.4. The four missing events (`Hypothesis`, `Prediction`, `Outcome`, `Learning`) plus the `Emotion` rewrite. This is the highest-leverage work — it is what makes the rest of the UI possible.
4. **Build the three-zone shell.** PySide6 window, three regions, bus subscription wiring, one panel per brief section.
5. **Dream Mode.** One state flag, one overlay, one subscriber. Lower priority than the other panels because it depends on the cognitive events existing.

What the v1 demo shows to a first-time viewer, in order:

- A living city with NPCs moving, trading, fighting, dying.
- A specific ARIA-driven NPC thinking out loud in the thought stream.
- That NPC's emotion changing with reasons.
- The user being able to act *as* the ARIA agent via the Action Panel.
- One dream sequence showing memory consolidation.

If those five things work, the cognitive-OS thesis is proven.

---

## 7. File-level plan

A single ordered list, so the next session can pick it up. Items are scoped for ~one PR each. Items marked **[blocks]** must land before anything below them.

```
[blocks]
 1. aria_core/environment/contract.py            # Protocol + dataclasses (Section 2)
 2. aria_core/environment/registry.py            # register / make
 3. aria_core/environment/validation.py          # ActionSchema check
 4. aria_core/cognition/events.py                # CognitiveEvent + Event.* (Section 3.2)

[events first because every panel binds to them]
 5. aria_core/cognition/emotion.py               # Section 3.3 — fixes C4-adjacent gap
 6. aria_core/cognition/prediction.py            # stub predictor, emits Prediction
 7. aria_core/cognition/learning.py              # outcome → memory loop, fixes C4
 8. aria_core/decision_maker.py:88               # wraps decide() in episode_id + emits 6 events
 9. aria_core/memory/models.py                   # EpisodicItem.outcome becomes settable
10. aria_core/learning/engine.py                 # subscribe to Outcome, emit Learning

[environment adapter]
11. aria_world/world.py                          # split tick → observe/step, add small-city primitives
12. aria_world/config.py                         # raise population cap to 100, add road/weather fields
13. aria_world/dashboard.py                      # rewrite to emit WorldSnapshot, not strings

[ui]
14. ui/aria_ui.py → ui/aria_app.py               # replace; PySide6; one App class
15. ui/shell/                                   # main_window, top_bar, three regions
16. ui/panels/emotion.py                         # binds to cognition.emotion
17. ui/panels/goals.py
18. ui/panels/memory.py
19. ui/panels/action.py
20. ui/panels/world_inspector.py
21. ui/panels/npc_inspector.py
22. ui/panels/thought_stream.py                  # the most important one
23. ui/map/                                      # canvas / WebGL viewport, camera, layers
24. ui/dream/                                    # overlay + consolidation view
```

Total: 24 items, in dependency order. Items 1–4 are a single sitting; 5–10 are the cognitive-event work and are the highest-leverage batch; 11–13 are the world adapter; 14–24 are the UI.

---

## 8. What this design deliberately does *not* do

- **No 3D.** 2D is faster, more honest, and reads as a "system" rather than a "game." A future redesign can promote the Map Zone to 3D without touching the bus contract.
- **No procedural visuals for NPCs.** NPCs are glyphs + labels + emotion color, not animated characters. The brief is "watching a mind," not "watching a movie."
- **No ML in v1.** `prediction.py` is a stub. The event *shape* is what matters; the model can be replaced without changing the UI.
- **No mobile.** The cognitive density of the right sidebar is not legible on a phone. A future "ARIA watch" view could collapse the sidebar to a single card.
- **No procedural music / audio.** Sound is information-carrying in this design. We have no information to carry yet. A future revision adds sonification only where it adds comprehension.
- **No fan-out to multiple ARIAs in v1.** The contract supports it (every event has an `agent_id`). The UI does not. Multi-agent view is a deliberate v2.

---

## 9. Acceptance criteria for "this is the cognitive OS"

The brief ends with: *someone opening ARIA should immediately think, "I am watching an artificial mind operate inside a living world."* That is the test. Concretely, in the v1 build:

- A new viewer, with no explanation, can read the thought stream top-to-bottom and describe what the ARIA agent did, why, and what it learned.
- A new viewer can click any NPC and see its current thought.
- A new viewer can take an action as the ARIA agent and watch the next thought stream respond.
- A new viewer can trigger a dream and watch memory consolidation play out.
- The visual style is indistinguishable from a Linear / Anthropic / Apple product, not a game.

If all five hold, the cognitive OS exists.

---

## 10. Related documents

- `docs/CTO_AUDIT.md` — the bug list and prior P0–P4 roadmap. This spec respects the audit's sequencing rule: no new features before config + pipeline consolidation.
- `docs/PERCEPTION_ARCHITECTURE.md` — feeds into Section 2.2's `Observation.data`.
- `docs/REASONING_BOTTLENECK_ANALYSIS.md` — explains why `Hypothesis` and `Prediction` are not yet wired to the bus.
- [[aria-project-ownership]] — owner split; this spec respects the Mimo / Nemotron / PM boundaries.
- [[aria-known-bugs]] — bugs B1, B12, C2, C4 are addressed directly by items 9, 13, and 4–7 above.
