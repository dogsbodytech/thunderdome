import unittest
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.runtime import CommandAction, CommandSource, OutputMode, RuntimeCommand, RuntimeCoordinator


class FakeRuntime:
    def __init__(self):
        self.started = []
        self.stopped = 0

    def start(self, display):
        self.started.append(display)

    def stop(self):
        self.stopped += 1


class RuntimeCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = [10.0]
        self.runtime = FakeRuntime()
        self.coordinator = RuntimeCoordinator(self.runtime, monotonic=lambda: self.clock[0])

    def command(self, action, *, effect="fire", priority=0, duration=None, output=OutputMode.SIMULATOR):
        return RuntimeCommand(CommandSource.BROWSER, action, "request", effect, {"brightness": 255}, output, priority, duration)

    def test_baseline_replacement_and_stop_all(self):
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE)).accepted)
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, effect="aurora")).accepted)
        self.assertEqual(self.runtime.stopped, 1)
        self.assertEqual(self.runtime.started[-1].effect, "aurora")
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.STOP_ALL, effect=None, output=None)).accepted)
        self.assertIsNone(self.coordinator.status()["baseline"])

    def test_override_priority_expiry_and_cancellation_restart_baseline(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="aurora", priority=1, duration=5)).accepted)
        rejected = self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="radar", priority=0, duration=5))
        self.assertFalse(rejected.accepted)
        self.assertIn("lower priority", rejected.reason)
        self.clock[0] = 16.0
        self.coordinator.expire_overrides()
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "fire")
        self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="aurora", priority=1, duration=5))
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.CANCEL_OVERRIDE, effect=None, output=None)).accepted)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "fire")

    def test_equal_priority_newer_override_replaces_and_output_inherits(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE, output=OutputMode.BOTH))
        first = self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="aurora", priority=1, duration=5, output=None))
        self.assertTrue(first.accepted)
        self.assertEqual(self.coordinator.status()["override"]["output"], "both")
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="radar", priority=1, duration=5, output=None)).accepted)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "radar")

    def test_baseline_uses_configured_default_without_restarting_on_invalid_replacement(self):
        self.coordinator.default_output = OutputMode.SIMULATOR
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, output=None)).accepted)
        starts = len(self.runtime.started)
        malformed = RuntimeCommand(CommandSource.BROWSER, CommandAction.SET_BASELINE, "bad", "fire", {"brightness": float("nan")}, None)
        self.assertFalse(self.coordinator.execute(malformed).accepted)
        self.assertEqual(len(self.runtime.started), starts)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "fire")

    def test_completed_baseline_clears_only_its_own_request(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        request_id = self.coordinator.status()["baseline"]["request_id"]
        self.assertTrue(self.coordinator.complete_baseline(request_id))
        self.assertEqual(self.coordinator.status()["service_state"], "idle")
        self.assertIsNone(self.coordinator.status()["baseline"])
        self.assertIsNone(self.coordinator.status()["effective"])

    def test_old_completed_baseline_cannot_clear_replacement(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        old_id = self.coordinator.status()["baseline"]["request_id"]
        self.coordinator.execute(RuntimeCommand(CommandSource.BROWSER, CommandAction.SET_BASELINE, "new", "aurora", {"brightness": 255}, OutputMode.SIMULATOR))
        self.assertFalse(self.coordinator.complete_baseline(old_id))
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "aurora")

    def test_continuous_baseline_remains_effective_without_completion(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        status = self.coordinator.status()
        self.assertEqual(status["service_state"], "running")
        self.assertEqual(status["baseline"]["effect"], "fire")
        self.assertEqual(status["effective"]["effect"], "fire")

    def test_override_expiry_restores_baseline_before_baseline_completion(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        baseline_id = self.coordinator.status()["baseline"]["request_id"]
        self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="aurora", priority=1, duration=1))
        self.clock[0] += 2
        self.coordinator.expire_overrides()
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "fire")
        self.assertTrue(self.coordinator.complete_baseline(baseline_id))
        self.assertEqual(self.coordinator.status()["service_state"], "idle")


if __name__ == "__main__":
    unittest.main()
