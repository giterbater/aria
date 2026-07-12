# Reasoning Architecture

`ReasoningEngine` turns objectives and context into executable plans.

The current flow is:

1. Build a `ReasoningContext`.
2. Generate a `ReasonedPlan` using an LLM if available.
3. Fall back to deterministic keyword planning when no LLM is available.
4. Verify skill availability, dependencies, cycles, low-confidence steps, and empty plans.
5. Replan after failure when possible.

## Key Models

- `ReasoningContext`: available skills, learned patterns, failure modes, recent actions, active goals, constraints.
- `ConfidenceScore`: goal, plan, skill-selection, and memory-match confidence.
- `ReasonedPlan`: reasoning output with risks, alternatives, verification notes, and raw step dictionaries.

## Typed Migration Layer

`ReasonedPlan.to_plan()` adapts raw reasoning steps into existing `Plan` / `PlanStep` objects. This is a compatibility bridge, not the desired long-term endpoint.

## Target v1 Direction

Move from:

```text
Understand -> Plan -> Execute
```

Toward:

```text
Understand -> Generate hypotheses -> Evaluate options -> Choose -> Execute -> Verify
```

## Measurement Targets

- Plan validity before execution.
- Step success rate.
- Number of replans per task.
- Confidence calibration.
- Time to plan.
- Improvement from learned failure modes.
