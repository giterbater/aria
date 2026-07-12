# ARIA Roadmap

ARIA v0.x assembled the major pieces. ARIA v1 focuses on measurable improvement.

## Phase A: Benchmarking And Visualization

Every build should answer:

- Is reasoning better?
- Is planning faster?
- Is memory retrieval improving?
- Is language understanding improving?
- Is execution more reliable?
- Is the simulated world healthier?

Current work:

- ARIA World dashboard.
- Simulation benchmark scores.
- Public docs and quick-start workflow.

## Phase B: Internal Cognitive State

Add functional internal variables that affect planning and decision-making:

- confidence
- uncertainty
- curiosity
- persistence
- caution
- workload
- novelty

These are control signals, not fake personality.

## Phase C: Better Reasoning

Move from:

```text
Understand -> Plan -> Execute
```

Toward:

```text
Understand -> Generate hypotheses -> Evaluate options -> Choose -> Execute -> Verify
```

## Phase D: Multi-Agent Testing

Run several ARIA instances against shared problems to measure coordination, critique, and diversity of approach.

## Phase E: Civilization

Only expand civilization-level behavior after benchmarks show reliable improvements in individual subsystems and ARIA World outcomes.

## Rule

No major feature should land without a measurable success criterion.
