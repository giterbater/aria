import asyncio
import unittest

from aria_core.decision_maker import SimpleDecisionMaker
from aria_core.goals import GoalManager
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from input_interpreter.implementations.rule_based import RuleBasedInputInterpreter
from language_cortex.manager import LanguageCortex
from language_cortex.models.mock import MockModel
from output_planner.implementations.rule_based import RuleBasedOutputPlanner


class RuleBasedPipelineTests(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def build_pipeline(self):
        interpreter = RuleBasedInputInterpreter()
        memory = SimpleMemorySystem()
        goals = GoalManager()
        decision_maker = SimpleDecisionMaker(memory=memory, goals=goals)
        planner = RuleBasedOutputPlanner()
        cortex = LanguageCortex(MockModel())
        return interpreter, decision_maker, planner, cortex

    def test_question_flows_to_language_response(self):
        interpreter, decision_maker, planner, cortex = self.build_pipeline()

        structured = self.run_async(interpreter.interpret("What is ARIA?"))
        decision = self.run_async(decision_maker.decide(structured))
        plan = self.run_async(planner.plan(decision))
        response = self.run_async(cortex.chat(plan["prompt"], max_tokens=60))

        self.assertEqual(structured.intent, "question")
        self.assertEqual(decision.action_type, "query")
        self.assertIn("question", plan["prompt"].lower())
        self.assertTrue(response.startswith("Echo:"))

    def test_open_application_selects_execute_action(self):
        interpreter, decision_maker, planner, _ = self.build_pipeline()

        structured = self.run_async(interpreter.interpret("open calculator"))
        decision = self.run_async(decision_maker.decide(structured))
        plan = self.run_async(planner.plan(decision))

        self.assertEqual(structured.intent, "open_application")
        self.assertEqual(decision.action_type, "execute")
        self.assertEqual(decision.payload["action"], "launch_calculator")
        self.assertIn("launch_calculator", plan["prompt"])


if __name__ == "__main__":
    unittest.main()
