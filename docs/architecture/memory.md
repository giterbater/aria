# Memory Architecture

ARIA's memory layer is protocol-first.

`MemorySystemProtocol` defines the core contract for:

- working memory
- episodic memory
- semantic memory
- relevance retrieval
- consolidation
- forgetting
- outcome writeback

## Implementations

- `SimpleMemorySystem`: in-memory reference backend for tests and prototypes.
- `SQLiteMemorySystem`: persistent backend with outcome writeback support.

## Memory Types

- `WorkingMemoryItem`: recent perception or context.
- `EpisodicItem`: one interaction or action episode.
- `SemanticItem`: distilled knowledge.
- `Outcome`: closed-set feedback label used for reinforcement.

## Current Use

`ARIACore` records skill-step outcomes as episodic memory and calls `record_outcome()` when supported. This creates a feedback loop from execution into persistence.

## Architectural Debt

- Simple and SQLite backends use different relevance algorithms.
- Consolidation is still naive.
- Memory retrieval is not yet benchmarked against task outcomes.
- Language memory and cognitive memory are adjacent systems, not yet unified.

## Measurement Targets

- Retrieval relevance against labeled queries.
- Outcome writeback correctness.
- Consolidation usefulness.
- Memory latency by backend.
- Improvement on repeated tasks with memory enabled vs disabled.
