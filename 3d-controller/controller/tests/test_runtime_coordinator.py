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

    def command(self, action, *, effect="Fire", priority=0, duration=None, output=OutputMode.SIMULATOR):
        return RuntimeCommand(CommandSource.BROWSER, action, "request", effect, {"brightness": 255}, output, priority, duration)

    def mqtt_command(self, action, *, effect="Fire", priority=0, duration=None, output=None):
        return RuntimeCommand(CommandSource.MQTT, action, "mqtt-request", effect, {"brightness": 255}, output, priority, duration)

    def test_mqtt_cannot_set_baseline_or_stop_all(self):
        for action in (CommandAction.SET_BASELINE, CommandAction.STOP_ALL):
            with self.subTest(action=action):
                result = self.coordinator.execute(self.mqtt_command(action, effect=None if action == CommandAction.STOP_ALL else "Fire"))
                self.assertFalse(result.accepted)
                self.assertIn("MQTT", result.reason)

    def test_duration_must_be_finite_and_positive(self):
        for duration in (float("nan"), float("inf"), float("-inf"), 0.0):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                RuntimeCommand(CommandSource.BROWSER, CommandAction.APPLY_OVERRIDE, "request", "Fire", {}, OutputMode.NULL, duration_seconds=duration)

        command = RuntimeCommand(CommandSource.BROWSER, CommandAction.APPLY_OVERRIDE, "request", "Fire", {}, OutputMode.NULL, duration_seconds=2.5)
        self.assertEqual(command.duration_seconds, 2.5)

    def test_mqtt_override_requires_duration_and_omitted_output(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        missing_duration = self.coordinator.execute(self.mqtt_command(CommandAction.APPLY_OVERRIDE, duration=None))
        explicit_output = self.coordinator.execute(self.mqtt_command(CommandAction.APPLY_OVERRIDE, duration=5, output=OutputMode.DDP))
        self.assertFalse(missing_duration.accepted)
        self.assertIn("duration", missing_duration.reason)
        self.assertFalse(explicit_output.accepted)
        self.assertIn("output", explicit_output.reason)

    def test_mqtt_override_requires_baseline_and_inherits_its_output(self):
        self.coordinator.default_output = OutputMode.SIMULATOR
        no_baseline = self.coordinator.execute(self.mqtt_command(CommandAction.APPLY_OVERRIDE, duration=5))
        self.assertFalse(no_baseline.accepted)
        self.assertIn("baseline", no_baseline.reason)
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE, output=OutputMode.BOTH))
        accepted = self.coordinator.execute(self.mqtt_command(CommandAction.APPLY_OVERRIDE, duration=5))
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.status["override"]["output"], "both")

    def test_mqtt_cancellation_remains_supported(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        self.coordinator.execute(self.mqtt_command(CommandAction.APPLY_OVERRIDE, duration=5))
        result = self.coordinator.execute(self.mqtt_command(CommandAction.CANCEL_OVERRIDE, effect=None))
        self.assertTrue(result.accepted)
        self.assertEqual(result.status["effective"]["source"], "browser")

    def test_baseline_replacement_and_stop_all(self):
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE)).accepted)
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, effect="Aurora")).accepted)
        self.assertEqual(self.runtime.stopped, 1)
        self.assertEqual(self.runtime.started[-1].effect, "Aurora")
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.STOP_ALL, effect=None, output=None)).accepted)
        self.assertIsNone(self.coordinator.status()["baseline"])

    def test_baseline_update_under_override_does_not_restart_override_and_restores_new_baseline(self):
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, effect="Fire")).accepted)
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", duration=5)).accepted)
        starts, stops = len(self.runtime.started), self.runtime.stopped

        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, effect="Radar")).accepted)
        self.assertEqual((len(self.runtime.started), self.runtime.stopped), (starts, stops))
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Aurora")
        self.assertEqual(self.coordinator.status()["baseline"]["effect"], "Radar")

        self.clock[0] = 16.0
        self.assertTrue(self.coordinator.expire_overrides())
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Radar")

    def test_legacy_effect_command_is_canonicalized_before_starting_runtime(self):
        result = self.coordinator.execute(self.command(CommandAction.SET_BASELINE, effect="height-wave"))

        self.assertTrue(result.accepted)
        self.assertEqual(self.runtime.started[-1].effect, "HeightWave")

    def test_override_priority_expiry_and_cancellation_restart_baseline(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", priority=1, duration=5)).accepted)
        rejected = self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Radar", priority=0, duration=5))
        self.assertFalse(rejected.accepted)
        self.assertIn("lower priority", rejected.reason)
        self.clock[0] = 16.0
        self.coordinator.expire_overrides()
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Fire")
        self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", priority=1, duration=5))
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.CANCEL_OVERRIDE, effect=None, output=None)).accepted)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Fire")

    def test_equal_priority_newer_override_replaces_and_output_inherits(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE, output=OutputMode.BOTH))
        first = self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", priority=1, duration=5, output=None))
        self.assertTrue(first.accepted)
        self.assertEqual(self.coordinator.status()["override"]["output"], "both")
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Radar", priority=1, duration=5, output=None)).accepted)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Radar")

    def test_override_without_baseline_uses_configured_default_output(self):
        self.coordinator.default_output = OutputMode.SIMULATOR
        result = self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", duration=5, output=None))
        self.assertTrue(result.accepted)
        self.assertEqual(self.coordinator.status()["override"]["output"], "simulator")
        self.clock[0] += 6
        self.coordinator.expire_overrides()
        self.assertIsNone(self.coordinator.status()["effective"])

    def test_baseline_uses_configured_default_without_restarting_on_invalid_replacement(self):
        self.coordinator.default_output = OutputMode.SIMULATOR
        self.assertTrue(self.coordinator.execute(self.command(CommandAction.SET_BASELINE, output=None)).accepted)
        starts = len(self.runtime.started)
        malformed = RuntimeCommand(CommandSource.BROWSER, CommandAction.SET_BASELINE, "bad", "Fire", {"brightness": float("nan")}, None)
        self.assertFalse(self.coordinator.execute(malformed).accepted)
        self.assertEqual(len(self.runtime.started), starts)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Fire")

    def test_completed_baseline_clears_only_its_own_request(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        self.coordinator.runtime_terminated(self.runtime.started[-1], None, False)
        self.assertEqual(self.coordinator.status()["service_state"], "idle")
        self.assertIsNone(self.coordinator.status()["baseline"])
        self.assertIsNone(self.coordinator.status()["effective"])

    def test_old_completed_baseline_cannot_clear_replacement(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        old_run = self.runtime.started[-1]
        self.coordinator.execute(RuntimeCommand(CommandSource.BROWSER, CommandAction.SET_BASELINE, "new", "Aurora", {"brightness": 255}, OutputMode.SIMULATOR))
        self.coordinator.runtime_terminated(old_run, None, False)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Aurora")

    def test_continuous_baseline_remains_effective_without_completion(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        status = self.coordinator.status()
        self.assertEqual(status["service_state"], "running")
        self.assertEqual(status["baseline"]["effect"], "Fire")
        self.assertEqual(status["effective"]["effect"], "Fire")

    def test_override_expiry_restores_baseline_before_baseline_completion(self):
        self.coordinator.execute(self.command(CommandAction.SET_BASELINE))
        self.coordinator.execute(self.command(CommandAction.APPLY_OVERRIDE, effect="Aurora", priority=1, duration=1))
        self.clock[0] += 2
        self.coordinator.expire_overrides()
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Fire")
        self.coordinator.runtime_terminated(self.runtime.started[-1], None, False)
        self.assertEqual(self.coordinator.status()["service_state"], "idle")


if __name__ == "__main__":
    unittest.main()
