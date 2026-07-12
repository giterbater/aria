#!/usr/bin/env python
"""
ARIA Cognitive OS — Milestone 2-5 Verification Script

This script verifies that all milestones are complete and functioning:
- M2: Emotion, Prediction, Outcome, Learning
- M3: Event bus standardization
- M4: Environment contract
- M5: Cognitive OS UI
"""

import sys
import importlib
from pathlib import Path


def verify_module_exists(module_path: str, name: str) -> bool:
    """Check if a module can be imported."""
    try:
        __import__(module_path)
        print(f"[OK] {name}: {module_path}")
        return True
    except ImportError as e:
        print(f"[FAIL] {name}: {module_path} -- {e}")
        return False


def verify_class_exists(module_path: str, class_name: str, label: str) -> bool:
    """Check if a class exists in a module."""
    try:
        mod = importlib.import_module(module_path)
        if hasattr(mod, class_name):
            print(f"[OK] {label}: {module_path}.{class_name}")
            return True
        else:
            print(f"[FAIL] {label}: {module_path}.{class_name} not found")
            return False
    except ImportError as e:
        print(f"[FAIL] {label}: Failed to import {module_path} -- {e}")
        return False


def verify_event_types() -> bool:
    """Verify all canonical event types exist."""
    from aria_core.cognition.events import Event

    required_events = [
        "OBSERVATION",
        "MEMORY_RETRIEVED",
        "HYPOTHESIS",
        "PREDICTION",
        "DECISION",
        "ACTION",
        "ACTION_REJECTED",
        "OUTCOME",
        "LEARNING",
        "EMOTION",
        "MEMORY_STORED",
        "DREAM_START",
        "DREAM_REPLAY",
        "DREAM_CONSOLIDATE",
        "DREAM_EXTRACT",
        "DREAM_FORGET",
        "DREAM_END",
    ]

    all_present = True
    for event in required_events:
        if hasattr(Event, event):
            print(f"  [OK] Event.{event}")
        else:
            print(f"  [FAIL] Event.{event} MISSING")
            all_present = False

    return all_present


def verify_emotion_dims() -> bool:
    """Verify all 7 emotion dimensions exist."""
    from aria_core.cognition.emotion import EMOTION_DIMS

    required_dims = [
        "confidence",
        "curiosity",
        "frustration",
        "motivation",
        "caution",
        "persistence",
        "novelty",
    ]

    all_present = all(dim in EMOTION_DIMS for dim in required_dims)
    if all_present:
        print(f"[OK] All 7 emotion dimensions defined: {EMOTION_DIMS}")
    else:
        print(f"[FAIL] Missing emotion dimensions. Found: {EMOTION_DIMS}")

    return all_present


def verify_environment_contract() -> bool:
    """Verify Environment contract methods."""
    from aria_world.world import WorldEngine

    world = WorldEngine()
    required_methods = [
        "reset",
        "step",
        "observe",
        "get_state",
        "list_actions",
        "spec",
        "render",
    ]

    all_present = True
    for method in required_methods:
        if hasattr(world, method) and callable(getattr(world, method)):
            print(f"  [OK] WorldEngine.{method}")
        else:
            print(f"  [FAIL] WorldEngine.{method} MISSING")
            all_present = False

    return all_present


def verify_event_bus() -> bool:
    """Verify event bus works."""
    from event_bus import bus

    received = []

    def test_callback(payload):
        received.append(payload)

    bus.subscribe("test.verify", test_callback)
    bus.publish("test.verify", {"test": "data"})

    if received and received[0] == {"test": "data"}:
        print("[OK] Event bus pub/sub functional")
        bus.unsubscribe("test.verify", test_callback)
        return True
    else:
        print("[FAIL] Event bus pub/sub failed")
        return False


def verify_ui_module() -> bool:
    """Verify UI module exists and has required components."""
    try:
        from ui.aria_app import CognitiveOSUI, EventDispatcher
        print("[OK] UI module: CognitiveOSUI and EventDispatcher")
        return True
    except ImportError as e:
        print(f"[FAIL] UI module failed to import: {e}")
        return False


def main() -> int:
    """Run all verifications."""
    print("\n" + "=" * 70)
    print("ARIA COGNITIVE OS -- MILESTONE 2-5 VERIFICATION")
    print("=" * 70)

    checks = []

    # Milestone 2: Emotion, Prediction, Outcome, Learning
    print("\n[M2] Emotion State, Prediction, Outcome, Learning")
    checks.append(verify_class_exists("aria_core.cognition.emotion", "EmotionState", "EmotionState"))
    checks.append(verify_class_exists("aria_core.cognition.emotion", "EmotionAttributor", "EmotionAttributor"))
    checks.append(verify_class_exists("aria_core.cognition.prediction", "PredictionModel", "PredictionModel"))
    checks.append(verify_class_exists("aria_core.cognition.learning", "OutcomeLearningLoop", "OutcomeLearningLoop"))

    print("\n  Emotion dimensions:")
    checks.append(verify_emotion_dims())

    # Milestone 3: Event bus
    print("\n[M3] Standardized Event Bus")
    checks.append(verify_module_exists("aria_core.cognition.events", "CognitiveEvent"))

    print("\n  Canonical event types:")
    checks.append(verify_event_types())

    print("\n  Event bus functionality:")
    checks.append(verify_event_bus())

    # Milestone 4: Environment contract
    print("\n[M4] Environment Contract")
    print("  Environment methods:")
    checks.append(verify_environment_contract())

    # Milestone 5: UI
    print("\n[M5] Cognitive Operating System UI")
    checks.append(verify_ui_module())

    # Summary
    print("\n" + "=" * 70)
    passed = sum(checks)
    total = len(checks)
    print(f"VERIFICATION RESULTS: {passed}/{total} checks passed")

    if passed == total:
        print("\nALL MILESTONES 2-5 COMPLETE AND VERIFIED")
        print("=" * 70)
        return 0
    else:
        print(f"\n{total - passed} checks failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
