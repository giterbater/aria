import sys
sys.path.insert(0, r'C:\Users\nevaan kaul\aria_project')

from aria_core.decision_maker import SimpleDecisionMaker
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.goals import GoalManager
from aria_core.interfaces import StructuredInput

# Create a mock StructuredInput for testing
class MockStructuredInput:
    def __init__(self):
        self.intent = "statement"
        self.raw_text = "Hello, how are you?"
        self.entities = []
        self.timestamp = __import__('datetime').datetime.now()
        self.importance = 0.5

def test():
    memory = SimpleMemorySystem()
    goals = GoalManager()
    dm = SimpleDecisionMaker(memory=memory, goals=goals)
    si = MockStructuredInput()
    # This is an async method, so we need to run it in an event loop
    import asyncio
    result = asyncio.run(dm.decide(si))
    print("Decision:", result.action_type)
    print("Payload:", result.payload)
    print("Tone:", result.tone)
    print("Priority:", result.priority)
    print("Urgency:", result.urgency)
    print("Speak:", result.speak)

if __name__ == "__main__":
    test()