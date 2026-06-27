# Current Tasks

## Completed This Session (by Project Manager)

1. ✅ **Extract ALang rendering to reusable utility** - Moved `_alang_to_str()` from `ui/aria_ui.py` to `output_planner/alang_serialization.py` with comprehensive tests (9 tests added)

2. ✅ **Add text-mode conversation loop** - Created `text_mode_loop.py` for stdin/stdout ARIA interaction without microphone or UI dependencies (7 tests added)

3. ✅ **Add comprehensive regression tests** - Created test suite covering goal management (8 tests), event bus pub/sub (7 tests), async/sync bridging (5 tests), and module boundaries (2 tests) = 23 new tests

4. ✅ **Remove temporary test artifacts** - Deleted `test_decision.py` and `out*.txt` files to clean repository

5. ✅ **Improve exception handling** - Added traceback logging to exception handlers for better debuggability

6. ✅ **Establish unified logging infrastructure** - Created `aria_logging.py` with centralized configuration; replaced all `print()` statements with proper `logger.*()` calls

## Test Summary

- **Total Tests**: 56 (17 original + 39 new)
- **Status**: ✅ ALL PASSING
- **Coverage Improved**: Goal management, event bus, async/sync bridges, communication systems, memory systems

## Next Up (for Mimo or Nemotron)

None currently queued. All identified Priority 1-2 items have been addressed by Project Manager.

## Done

- Mimo: improved memory relevance by extracting structured text from StructuredInput, ARIDecision, and dicts instead of relying on dataclass repr.
- Mimo: preserved memory item subclasses (WorkingMemoryItem, EpisodicItem, SemanticItem) with type-safe `with_importance` overrides.
- Project Manager: documented subsystem ownership and roadmap priorities.
- Project Manager: added a standard-library rule-based pipeline smoke test.
- Project Manager: fixed the worker path so async interpreter, decision, planner, and language calls execute correctly from the synchronous speech loop.
- Project Manager (current session): 6 high-value improvements with comprehensive testing and documentation.
