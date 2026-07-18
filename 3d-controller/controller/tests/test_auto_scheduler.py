import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.auto_scheduler import AutoScheduler
from thunderdome.frame import RGBFrame


class AutoSchedulerTests(unittest.TestCase):
    def test_transition_and_deterministic_shuffle_are_shared_decisions(self):
        scheduler = AutoScheduler(["fire", "aurora", "radar"], interval=10, transition=2, shuffle=True, seed=7)
        same = AutoScheduler(["fire", "aurora", "radar"], interval=10, transition=2, shuffle=True, seed=7)
        self.assertEqual(scheduler.names, same.names)
        decision = scheduler.decision(9)
        self.assertTrue(decision.transitioning)
        self.assertEqual(decision.blend, .5)

    def test_frame_applies_brightness_after_transition(self):
        scheduler = AutoScheduler(["fire", "aurora"], interval=10, transition=2)
        frame = scheduler.frame(9, lambda name, elapsed: RGBFrame.allocate(2, (255 if name == "fire" else 0, 0, 0)), brightness=255)
        self.assertEqual(frame.data[:3], bytes((127, 0, 0)))


if __name__ == "__main__":
    unittest.main()
