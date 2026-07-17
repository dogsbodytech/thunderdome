import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.animation.loop import run_frame_loop


class FrameLoopTests(unittest.TestCase):
    def test_loop_sends_a_new_generated_frame_each_iteration(self):
        sent = []
        sleeps = []

        stats = run_frame_loop(
            lambda frame_number, elapsed_seconds: frame_number,
            sent.append,
            fps=20,
            loops=4,
            clock=lambda: 100.0,
            sleep=sleeps.append,
        )

        self.assertEqual(sent, [0, 1, 2, 3])
        self.assertEqual(stats.frames_sent, 4)
        self.assertFalse(stats.interrupted)
        self.assertEqual(len(sleeps), 3)
        for actual, expected in zip(sleeps, [0.05, 0.1, 0.15]):
            self.assertAlmostEqual(actual, expected)

    def test_loop_converts_normal_keyboard_interrupt_to_statistics(self):
        calls = 0

        def interrupting_sender(_frame):
            nonlocal calls
            calls += 1
            raise KeyboardInterrupt

        stats = run_frame_loop(
            lambda frame_number, elapsed_seconds: frame_number,
            interrupting_sender,
            fps=20,
            loops=10,
            clock=lambda: 100.0,
            sleep=lambda _seconds: None,
        )

        self.assertEqual(calls, 1)
        self.assertEqual(stats.frames_sent, 0)
        self.assertTrue(stats.interrupted)


if __name__ == "__main__":
    unittest.main()
