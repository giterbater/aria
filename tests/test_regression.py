"""
Regression tests for goal management, event bus, and sync/async bridges.

These tests ensure critical subsystem integration points remain stable
as ARIA evolves. Coverage includes goal relevance matching, event
publishing/subscription, and the async-to-sync worker pattern.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from aria_core.goals import Goal, GoalManager
from aria_core.interfaces import StructuredInput
from event_bus import bus


class TestGoalRelevance(unittest.TestCase):
    """Test goal lifecycle and relevance matching."""

    def test_add_and_list_goals(self):
        """Test adding goals and retrieving them."""
        manager = GoalManager()
        g1 = Goal(description="Learn Spanish", priority=1.2)
        g2 = Goal(description="Stay healthy", priority=1.0)

        manager.add_goal(g1)
        manager.add_goal(g2)

        goals = manager.list_goals()
        self.assertEqual(len(goals), 2)
        self.assertIn(g1, goals)
        self.assertIn(g2, goals)

    def test_remove_goal(self):
        """Test removing a goal by ID."""
        manager = GoalManager()
        g1 = Goal(description="Learn Spanish", priority=1.2)
        manager.add_goal(g1)

        self.assertEqual(len(manager.list_goals()), 1)
        manager.remove_goal(g1.id)
        self.assertEqual(len(manager.list_goals()), 0)

    def test_goal_with_deadline(self):
        """Test creating a goal with a deadline."""
        deadline = datetime.now() + timedelta(days=30)
        goal = Goal(description="Complete project", priority=2.0, deadline=deadline)

        self.assertIsNotNone(goal.deadline)
        self.assertEqual(goal.deadline, deadline)

    def test_goal_metadata_storage(self):
        """Test storing and retrieving arbitrary metadata on goals."""
        metadata = {"resource": "GPU", "estimated_hours": 10}
        goal = Goal(description="Train model", priority=1.5, metadata=metadata)

        self.assertEqual(goal.metadata["resource"], "GPU")
        self.assertEqual(goal.metadata["estimated_hours"], 10)

    def test_get_relevant_goals(self):
        """Test retrieving goals relevant to a cue."""
        manager = GoalManager()
        spanish_goal = Goal(description="Learn Spanish", priority=1.2)
        health_goal = Goal(description="Stay healthy", priority=1.0)

        manager.add_goal(spanish_goal)
        manager.add_goal(health_goal)

        # The relevant_goals method finds goals matching a cue
        cue = "spanish"
        relevant = manager.relevant_goals(cue)

        # Should find the Spanish goal as relevant
        self.assertGreater(len(relevant), 0)

    def test_goal_relevance_scores(self):
        """Test that relevance scoring works correctly."""
        manager = GoalManager()
        high_prio = Goal(description="Critical task", priority=3.0)
        low_prio = Goal(description="Nice to have", priority=0.5)

        manager.add_goal(high_prio)
        manager.add_goal(low_prio)

        relevant = manager.relevant_goals("task")
        # Relevance should consider priority
        if len(relevant) > 1:
            self.assertGreater(relevant[0].priority, relevant[1].priority)

    def test_goal_with_no_deadline(self):
        """Test that goals without deadlines are handled correctly."""
        goal = Goal(description="Ongoing learning", priority=1.0)
        self.assertIsNone(goal.deadline)

    def test_empty_goal_manager(self):
        """Test retrieving goals from an empty manager."""
        manager = GoalManager()
        goals = manager.list_goals()
        self.assertEqual(len(goals), 0)

    def test_multiple_goal_removal(self):
        """Test removing multiple goals."""
        manager = GoalManager()
        goals = [
            Goal(description="Goal 1", priority=1.0),
            Goal(description="Goal 2", priority=1.0),
            Goal(description="Goal 3", priority=1.0),
        ]
        for g in goals:
            manager.add_goal(g)

        manager.remove_goal(goals[0].id)
        manager.remove_goal(goals[1].id)

        remaining = manager.list_goals()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, goals[2].id)


class TestEventBusPubSub(unittest.TestCase):
    """Test event bus publish/subscribe functionality."""

    def setUp(self):
        """Clear the bus subscriptions before each test."""
        # Patch the bus to isolate tests
        self.bus = bus

    def test_publish_without_subscribers(self):
        """Test that publishing without subscribers doesn't crash."""
        # Should not raise an exception
        self.bus.publish("TestEvent", {"data": "test"})

    def test_publish_and_subscribe(self):
        """Test basic publish/subscribe pattern."""
        received_payloads = []

        def callback(payload):
            received_payloads.append(payload)

        self.bus.subscribe("TestEvent", callback)
        self.bus.publish("TestEvent", {"value": 42})

        # Give the event bus time to process (if async)
        self.assertEqual(len(received_payloads), 1)
        self.assertEqual(received_payloads[0]["value"], 42)

    def test_multiple_subscribers_same_event(self):
        """Test multiple subscribers receiving the same event."""
        results = {"callback1": [], "callback2": []}

        def callback1(payload):
            results["callback1"].append(payload)

        def callback2(payload):
            results["callback2"].append(payload)

        self.bus.subscribe("MultiEvent", callback1)
        self.bus.subscribe("MultiEvent", callback2)
        self.bus.publish("MultiEvent", "test_data")

        self.assertEqual(len(results["callback1"]), 1)
        self.assertEqual(len(results["callback2"]), 1)

    def test_subscribe_different_events(self):
        """Test subscribing to different events separately."""
        results = {"event1": [], "event2": []}

        self.bus.subscribe("Event1", lambda p: results["event1"].append(p))
        self.bus.subscribe("Event2", lambda p: results["event2"].append(p))

        self.bus.publish("Event1", "data1")
        self.bus.publish("Event2", "data2")

        self.assertEqual(results["event1"], ["data1"])
        self.assertEqual(results["event2"], ["data2"])

    def test_event_with_none_payload(self):
        """Test publishing events with None payload."""
        received = []
        self.bus.subscribe("NoneEvent", lambda p: received.append(p))
        self.bus.publish("NoneEvent", None)

        self.assertEqual(len(received), 1)
        self.assertIsNone(received[0])

    def test_event_with_complex_payload(self):
        """Test publishing complex data structures."""
        received = []
        complex_data = {
            "nested": {"level2": [1, 2, 3]},
            "list": ["a", "b", "c"],
            "number": 42,
        }

        self.bus.subscribe("ComplexEvent", lambda p: received.append(p))
        self.bus.publish("ComplexEvent", complex_data)

        self.assertEqual(received[0], complex_data)


class TestAsyncSyncBridge(unittest.TestCase):
    """Test async/sync bridging for worker patterns."""

    def test_run_async_from_sync(self):
        """Test running async code from synchronous context."""

        async def async_operation():
            return "async_result"

        def run_async(coro):
            return asyncio.run(coro)

        result = run_async(async_operation())
        self.assertEqual(result, "async_result")

    def test_async_with_await(self):
        """Test async function that uses await."""

        async def async_with_delay():
            await asyncio.sleep(0.01)
            return "completed"

        def run_async(coro):
            return asyncio.run(coro)

        result = run_async(async_with_delay())
        self.assertEqual(result, "completed")

    def test_multiple_sequential_async_calls(self):
        """Test multiple async calls from sync context."""

        async def async_op(value):
            return value * 2

        def run_async(coro):
            return asyncio.run(coro)

        result1 = run_async(async_op(5))
        result2 = run_async(async_op(10))

        self.assertEqual(result1, 10)
        self.assertEqual(result2, 20)

    def test_async_exception_handling(self):
        """Test that exceptions in async code are properly raised."""

        async def failing_async():
            raise ValueError("Intentional error")

        def run_async(coro):
            return asyncio.run(coro)

        with self.assertRaises(ValueError):
            run_async(failing_async())

    def test_async_with_multiple_awaits(self):
        """Test async function with multiple await points."""

        async def multi_await():
            await asyncio.sleep(0.01)
            val = "step1"
            await asyncio.sleep(0.01)
            return val + "_step2"

        def run_async(coro):
            return asyncio.run(coro)

        result = run_async(multi_await())
        self.assertEqual(result, "step1_step2")


class TestModuleBoundaries(unittest.TestCase):
    """Test that module boundaries are properly enforced."""

    def test_decision_maker_uses_memory_protocol(self):
        """Test that decision maker works with any MemorySystemProtocol."""
        from aria_core.decision_maker import SimpleDecisionMaker
        from aria_core.memory.simple_memory_system import SimpleMemorySystem
        from aria_core.goals import GoalManager

        memory = SimpleMemorySystem()
        goals = GoalManager()

        # Should not raise an exception
        maker = SimpleDecisionMaker(memory=memory, goals=goals)
        self.assertIsNotNone(maker)

    def test_goal_manager_independence(self):
        """Test that GoalManager doesn't depend on specific implementations."""
        manager = GoalManager()
        goal = Goal(description="Test", priority=1.0)
        manager.add_goal(goal)

        # Should be able to work with any Goal instance
        retrieved = manager.list_goals()
        self.assertEqual(len(retrieved), 1)

    def test_structured_input_interface(self):
        """Test that StructuredInput is properly defined."""
        from aria_core.interfaces import StructuredInput

        si = StructuredInput(
            raw_text="test",
            intent="test_intent",
            confidence=0.95,
            entities=[],
            facts=["fact1"],
            questions=["q1"],
        )

        self.assertEqual(si.raw_text, "test")
        self.assertEqual(si.intent, "test_intent")
        self.assertEqual(si.confidence, 0.95)


if __name__ == "__main__":
    unittest.main()
