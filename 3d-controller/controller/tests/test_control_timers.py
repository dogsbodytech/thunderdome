"""Deterministic timer ownership tests: no sleeps, sockets or worker threads."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.control import ControlAPI, ControlSettings
from thunderdome.runtime import OutputMode


class ManualTimer:
    instances = []

    def __init__(self, interval, function, args=(), kwargs=None):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs or {}
        self.cancelled = False
        self.started = False
        self.daemon = False
        self.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        # Cancellation cannot stop a callback that has already been dispatched.
        self.function(*self.args, **self.kwargs)


class QuietRuntime:
    def __init__(self):
        self.shutdown_calls = 0
        self.shutdown_error = None

    def shutdown(self):
        self.shutdown_calls += 1
        if self.shutdown_error:
            raise self.shutdown_error


class TimerCoordinator:
    def __init__(self):
        self.current = {"override": None, "remaining_override_seconds": None}
        self.status_calls = 0
        self.expiry_calls = 0

    def execute(self, command):
        from thunderdome.runtime import CommandResult
        return CommandResult(True, None, self.current)

    def status(self):
        self.status_calls += 1
        return self.current

    def expire_overrides(self, generation=None):
        override = self.current.get("override")
        if override is not None and override.get("generation") == generation:
            self.expiry_calls += 1


def timed_status(generation, request_id="reused", remaining=60):
    return {"override": {"generation": generation, "request_id": request_id},
            "remaining_override_seconds": remaining}


class ControlTimerTests(unittest.TestCase):
    def setUp(self):
        ManualTimer.instances = []
        self.timer_patch = patch("thunderdome.control.threading.Timer", ManualTimer)
        self.timer_patch.start()
        self.addCleanup(self.timer_patch.stop)
        self.runtime = QuietRuntime()
        self.api = ControlAPI(ControlSettings("http://127.0.0.1:1", default_output=OutputMode.NULL), self.runtime)
        self.api.coordinator = TimerCoordinator()

    def sync(self, status):
        self.api.coordinator.current = status
        self.api._sync_override_timer(status)
        return self.api._override_timer

    def test_reused_id_replacement_duration_uses_real_coordinator_generation(self):
        from thunderdome.runtime import (RuntimeCoordinator, RuntimeCommand,
                                        CommandAction, CommandSource)
        class Runtime:
            def start(self, display):
                pass
            def stop(self):
                pass
        clock = [0.0]
        self.api.coordinator = RuntimeCoordinator(Runtime(), monotonic=lambda: clock[0])
        def apply(duration):
            return self.api.coordinator.execute(RuntimeCommand(
                CommandSource.BROWSER, CommandAction.APPLY_OVERRIDE, "same", "Fire", {},
                OutputMode.NULL, duration_seconds=duration))
        first = apply(60)
        self.api._sync_override_timer(first.status)
        old = self.api._override_timer
        clock[0] = 1.0
        second = apply(5)
        self.api._sync_override_timer(second.status)
        current = self.api._override_timer
        self.assertIsNot(old, current)
        self.assertEqual(old.interval, 60)
        self.assertEqual(current.interval, 5)
        self.assertTrue(old.cancelled)
        old.fire()
        self.assertIs(self.api._override_timer, current)
        self.assertEqual(sum(not timer.cancelled for timer in ManualTimer.instances), 1)

    def test_old_callback_cannot_expire_new_generation_before_timer_sync(self):
        from thunderdome.runtime import (RuntimeCoordinator, RuntimeCommand,
                                        CommandAction, CommandSource)
        class Runtime:
            def start(self, display):
                pass
            def stop(self):
                pass
        clock = [0.0]
        coordinator = RuntimeCoordinator(Runtime(), monotonic=lambda: clock[0])
        self.api.coordinator = coordinator
        def apply(duration):
            return coordinator.execute(RuntimeCommand(
                CommandSource.BROWSER, CommandAction.APPLY_OVERRIDE, "same", "Fire", {},
                OutputMode.NULL, duration_seconds=duration))
        self.api._sync_override_timer(apply(60).status)
        old = self.api._override_timer
        clock[0] = 1.0
        apply(5)  # Accepted, but the HTTP caller has not synchronized its timer yet.
        newer = coordinator._override
        clock[0] = 7.0
        old.fire()
        self.assertIs(coordinator._override, newer)
        self.assertEqual(coordinator._active.generation, newer.generation)

    def test_reused_request_id_replaces_timer_for_new_generation(self):
        old = self.sync(timed_status("generation-one"))
        new = self.sync(timed_status("generation-two"))
        self.assertIsNot(old, new)
        self.assertTrue(old.cancelled)
        self.assertTrue(new.started)
        self.assertTrue(new.daemon)
        self.assertEqual(new.interval, 60)

    def test_dispatched_cancelled_callback_cannot_touch_rearmed_same_generation(self):
        old = self.sync(timed_status("generation-one"))
        self.sync({"override": None, "remaining_override_seconds": None})
        new = self.sync(timed_status("generation-one"))
        old.fire()
        self.assertEqual(self.api.coordinator.status_calls, 0)
        self.assertEqual(self.api.coordinator.expiry_calls, 0)
        self.assertIs(self.api._override_timer, new)
        self.assertFalse(new.cancelled)

    def test_shutdown_invalidates_pending_natural_override_completion(self):
        from thunderdome.runtime import (RuntimeCoordinator, RuntimeCommand,
                                        CommandAction, CommandSource)
        class Runtime(QuietRuntime):
            def __init__(self):
                super().__init__()
                self.started = []
            def start(self, display):
                self.started.append(display)
            def stop(self):
                pass
        runtime = Runtime()
        api = ControlAPI(ControlSettings("http://unused.invalid"), runtime)
        for action, effect in ((CommandAction.SET_BASELINE, "Fire"),
                               (CommandAction.APPLY_OVERRIDE, "Aurora")):
            self.assertTrue(api.coordinator.execute(RuntimeCommand(
                CommandSource.BROWSER, action, "same", effect, {}, OutputMode.NULL)).accepted)
        finishing = runtime.started[-1]
        api.shutdown()
        runtime.on_terminated(finishing, None, False)
        self.assertEqual(len(runtime.started), 2)
        status = api.coordinator.status()
        self.assertEqual(status["service_state"], "idle")
        self.assertIsNone(status["effective"])
        self.assertIsNone(status["baseline"])

    def test_shutdown_cannot_rearm_timer(self):
        timer = self.sync(timed_status("generation-one"))
        self.api.shutdown()
        self.assertTrue(timer.cancelled)
        self.assertIsNone(self.sync(timed_status("generation-two")))
        timer.fire()
        self.assertEqual(self.api.coordinator.status_calls, 0)
        self.api.shutdown()
        self.assertEqual(self.runtime.shutdown_calls, 1)

    def test_failed_shutdown_remains_retryable_without_rearming_timer(self):
        timer = self.sync(timed_status("generation-one"))
        self.runtime.shutdown_error = OSError("worker still stopping")
        with self.assertRaisesRegex(OSError, "still stopping"):
            self.api.shutdown()
        self.assertFalse(self.api._shutdown)
        self.assertTrue(timer.cancelled)
        self.assertIsNone(self.sync(timed_status("generation-two")))
        self.runtime.shutdown_error = None
        self.api.shutdown()
        self.api.shutdown()
        self.assertEqual(self.runtime.shutdown_calls, 2)
        self.assertTrue(self.api._shutdown)

    def test_repeated_sync_keeps_one_timer_for_current_generation(self):
        timer = self.sync(timed_status("generation-one"))
        for remaining in range(59, 0, -1):
            self.assertIs(self.sync(timed_status("generation-one", remaining=remaining)), timer)
        self.assertEqual(len(ManualTimer.instances), 1)
        self.assertFalse(timer.cancelled)

    def test_stale_callback_with_reused_request_id_cannot_touch_new_timer(self):
        old = self.sync(timed_status("generation-one"))
        new = self.sync(timed_status("generation-two"))
        old.fire()
        self.assertIs(self.api._override_timer, new)
        self.assertEqual(self.api.coordinator.status_calls, 0)
        self.assertEqual(self.api.coordinator.expiry_calls, 0)

    def test_cancelled_callback_does_not_query_coordinator(self):
        timer = self.sync(timed_status("generation-one"))
        self.sync({"override": None, "remaining_override_seconds": None})
        timer.fire()
        self.assertTrue(timer.cancelled)
        self.assertIsNone(self.api._override_timer)
        self.assertEqual(self.api.coordinator.status_calls, 0)

    def test_untimed_replacement_cancels_timer(self):
        timer = self.sync(timed_status("generation-one"))
        self.assertIsNone(self.sync(timed_status("generation-two", remaining=None)))
        self.assertTrue(timer.cancelled)
        self.assertEqual(len(ManualTimer.instances), 1)

    def test_current_callback_expires_matching_generation_only_once(self):
        timer = self.sync(timed_status("generation-one"))
        timer.fire()
        timer.fire()
        self.assertEqual(self.api.coordinator.expiry_calls, 1)
        self.assertIsNone(self.api._override_timer)

    def test_generation_mismatch_does_not_explicitly_expire_reused_request_id(self):
        timer = self.sync(timed_status("generation-one"))
        self.api.coordinator.current = timed_status("generation-two")
        timer.fire()
        self.assertEqual(self.api.coordinator.expiry_calls, 0)
        self.assertIsNone(self.api._override_timer)

    def test_callback_cleanup_preserves_reentrant_replacement(self):
        timer = self.sync(timed_status("generation-one"))
        replacements = []

        def expire(generation):
            self.sync({"override": None, "remaining_override_seconds": None})
            replacements.append(self.sync(timed_status("generation-one")))

        self.api.coordinator.expire_overrides = expire
        timer.fire()
        self.assertIs(self.api._override_timer, replacements[0])
        self.assertFalse(replacements[0].cancelled)


if __name__ == "__main__":
    unittest.main()
