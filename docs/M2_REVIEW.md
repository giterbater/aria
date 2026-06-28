# M2 CTO Review — Sign-off and Integration Notes

**Reviewer**: CTO (Mimo's manager)
**Date**: 2026-06-28
**Subject**: Mimo's M2 deliverables (persistence + outcome feedback + tools)
**Verdict**: ✅ **APPROVED FOR INTEGRATION** (one contract-compliance fix applied)

---

## 1. Deliverables reviewed

Five commits on `main`, Co-authored-by Mimo <mimo@aria.local>:

| SHA       | Subject                                                      |
|-----------|--------------------------------------------------------------|
| 0c61434   | feat: add M2 interface contracts and Outcome enum            |
| 2f53988   | feat: add SQLiteMemorySystem with full MemorySystemProtocol conformance |
| 99d52d9   | feat: add SQLiteGoalStore and GoalManager(persistence=...) extension |
| 838a7b3   | feat: add tool registry with launch_application, set_reminder, cancel_reminder, current_time |
| b6ffdb3   | test: add M2 test coverage                                    |

## 2. Test results

`python -m unittest discover -s tests` → **134 passed** (56 pre-M2 + 78 new). Zero regressions.

## 3. Scope compliance

`git diff` against the pre-M2 HEAD confirmed zero changes to forbidden files:
`main.py`, `text_mode_loop.py`, `event_bus.py`, `aria_logging.py`, `input_interpreter/`,
`language_cortex/`, `output_planner/`, `ui/`.

All M2 work is confined to `aria_core/` (new + extended files) and `tests/`.

## 4. Deviations — disposition

### Accepted without revision

| # | Deviation                                                                                                          | Rationale                                                                                                                                              |
|---|--------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | `set_reminder` spawns a `threading.Timer` whose callback is literally `pass` (dead code). The actual delivery uses `PendingReminders.drain_fired()` polling from the worker. | Worker is the single firing path by design. Timer is vestigial. No correctness impact; acceptable to leave for a follow-up cleanup.                    |
| 2 | `SQLiteMemorySystem.get_semantic` / `retrieve_relevant` use substring + Jaccard instead of TF-IDF cosine that `SimpleMemorySystem` uses. | The `MemorySystemProtocol.retrieve_relevant` docstring says: "concrete implementation decides how to blend the three stores". Different algorithms per backend is permissible. Flagged here because Mimo didn't list it in the original deviations note. |
| 3 | `ToolRegistry.with_defaults()` convenience classmethod (not in the original contract). | Pure addition; positive deviation. Speeds up wiring in `text_mode_loop.py` (PM-owned) when M3 integrates. |

### Fixed in this review (CTO commit)

| # | Deviation                                                                                                          | Resolution                                                                                                                                              |
|---|--------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4 | `SimpleMemorySystem.record_outcome` raised `AttributeError` (did not exist as a method). Mimo's deviation note asked whether to implement it or raise `NotImplementedError`. | Per the M2 contract §4: "implementations that don't support writeback must raise NotImplementedError until M2 lands." I added the explicit `NotImplementedError` with a clear message. The 134-test suite still passes. |

### Other findings (informational, no action required)

- `SQLiteMemorySystem.consolidate` deletes the working/episodic row inside one `with self._conn:` block and inserts the semantic replacement inside a separate one. Tiny window where the item is absent. Not a correctness bug for single-threaded use; documented for future hardening.
- `Outcome` enum string-valued (inherits `str`) — round-trips through SQLite `TEXT` cleanly. Good choice.

## 5. Independent verification (CTO)

Beyond trusting Mimo's tests, I ran direct checks:

1. Subtype preservation across load — confirmed `WorkingMemoryItem`, `EpisodicItem`, `SemanticItem` round-trip with `isinstance` checks intact.
2. Outcome deltas — `record_outcome(SUCCESS)` on importance=0.6 → 0.7 ✅; `FAILED` on 0.7 → 0.65 ✅; many SUCCESS → clamps to 1.0 ✅; unknown id → no-op ✅.
3. `launch_application('notepad')` mocked → exact argv `['cmd', '/c', 'start', '', 'notepad']` ✅.
4. `current_time()` returns ISO-8601 with both `iso` and `epoch` keys ✅.
5. `SimpleMemorySystem.record_outcome(...)` → raises `NotImplementedError` with the contract-correct message ✅.

## 6. Mimo's open questions — disposition

| # | Question                                                                                  | Answer                                                                                       |
|---|-------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| 1 | Should `SimpleMemorySystem.record_outcome` raise `NotImplementedError` or be implemented? | **Raise** `NotImplementedError`. Resolved in commit `pending-this-commit`.                   |
| 2 | `update_importance` delta-based vs `PersistenceProtocol.update_memory_importance` new-importance-based mismatch. | Accept the asymmetry for M2. `MemorySystemProtocol.update_importance(id, delta)` is the existing API; `PersistenceProtocol.update_memory_importance(id, new_importance)` is the new one. `SQLiteGoalStore` already bridges them (it computes the delta and forwards). Document the asymmetry; revisit in M3 if it bites. |
| 3 | Single DB file for goals + memory vs separate files.                                      | Single file via `SQLiteGoalStore` lazily instantiating `SQLiteMemorySystem(db_path)`. Simpler. Document; revisit if multi-tenant needs emerge.       |
| 4 | ARIDecision reconstruction on load for M3.                                                | Out of M2 scope. Currently `EpisodicItem.decision` is `Any` and round-trips as a dict through JSON. M3 will define a `from_dict` / `to_dict` on the dataclass and the load-side reconstruction logic will switch on `decision` shape. |

## 7. Sign-off

M2 is **complete**. Marking `M2: ARIA Remembers (persistence + outcome feedback + tools)` complete. Moving to **M1 (Configuration and Pipeline Consolidation)** as the prerequisite for M3 (multi-turn context).

Co-Authored-By: Claude <noreply@anthropic.com>
