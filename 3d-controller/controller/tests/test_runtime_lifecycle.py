"""Deterministic lifecycle regressions; no hardware or network sinks."""
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunderdome.runtime import (CommandAction as Action, CommandSource, DisplayDefinition, OutputMode,
                                RuntimeCommand, RuntimeCoordinator)


def command(action, effect="Fire", request_id="same", duration=None):
    return RuntimeCommand(CommandSource.BROWSER, action, request_id, effect, {},
                          OutputMode.NULL, duration_seconds=duration)


class FakeRuntime:
    def __init__(self):
        self.started = []
        self.fail_stop = False
        self.fail_start = False

    def start(self, display):
        if self.fail_start:
            raise OSError("start failed")
        self.started.append(display)

    def stop(self):
        if self.fail_stop:
            raise OSError("worker stuck")


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.coordinator = RuntimeCoordinator(self.runtime)
        self.coordinator.execute(command(Action.SET_BASELINE))

    def assert_rejected_preserves(self, action, effect="Radar"):
        before = self.coordinator.status()
        self.runtime.fail_stop = True
        result = self.coordinator.execute(command(action, effect))
        self.assertFalse(result.accepted)
        self.assertIn("worker stuck", result.reason)
        for key in ("baseline", "override", "effective", "service_state"):
            self.assertEqual(result.status[key], before[key], key)
        self.assertEqual(len(self.runtime.started), 2 if before["override"] else 1)

    def test_failed_baseline_replacement(self):
        self.assert_rejected_preserves(Action.SET_BASELINE)

    def test_failed_override_replacement(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.assert_rejected_preserves(Action.APPLY_OVERRIDE)

    def test_failed_override_cancellation(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.assert_rejected_preserves(Action.CANCEL_OVERRIDE)

    def test_failed_override_restoration(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.assert_rejected_preserves(Action.RESTART_BASELINE)

    def test_failed_stop_all(self):
        self.assert_rejected_preserves(Action.STOP_ALL)

    def test_failed_expiry_keeps_override_and_reports_stop_failure(self):
        clock = [0.0]
        self.coordinator._monotonic = lambda: clock[0]
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora", duration=5))
        before = self.coordinator.status()
        clock[0] = 6.0
        self.runtime.fail_stop = True
        with self.assertRaisesRegex(OSError, "worker stuck"):
            self.coordinator.expire_overrides()
        status = self.coordinator.status()
        self.assertEqual(status["override"], before["override"])
        self.assertEqual(status["effective"], before["effective"])
        self.assertEqual(status["latest_error"], "worker stuck")


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.coordinator = RuntimeCoordinator(self.runtime)
        self.coordinator.execute(command(Action.SET_BASELINE))

    def finish(self, display, error=None, cancelled=False):
        self.coordinator.runtime_terminated(display, error, cancelled)

    def test_natural_baseline_completion(self):
        self.finish(self.runtime.started[-1])
        status = self.coordinator.status()
        self.assertEqual(status["service_state"], "idle")
        self.assertIsNone(status["baseline"])
        self.assertIsNone(status["effective"])

    def test_natural_override_completion_restores_baseline(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora", duration=60))
        self.finish(self.runtime.started[-1])
        status = self.coordinator.status()
        self.assertIsNone(status["override"])
        self.assertEqual(status["effective"]["effect"], "Fire")
        self.assertEqual(len(self.runtime.started), 3)

    def test_baseline_failure_keeps_restart_definition_but_not_effective(self):
        self.finish(self.runtime.started[-1], "renderer failed")
        status = self.coordinator.status()
        self.assertEqual(status["service_state"], "error")
        self.assertIsNone(status["effective"])
        self.assertEqual(status["baseline"]["effect"], "Fire")
        self.assertEqual(status["latest_error"], "renderer failed")
        self.assertTrue(self.coordinator.execute(command(Action.RESTART_BASELINE)).accepted)
        self.assertEqual(self.coordinator.status()["service_state"], "running")

    def test_override_failure_restores_baseline_and_retains_error(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.finish(self.runtime.started[-1], "sink failed")
        status = self.coordinator.status()
        self.assertIsNone(status["override"])
        self.assertEqual(status["effective"]["effect"], "Fire")
        self.assertEqual(status["latest_error"], "sink failed")

    def test_override_without_baseline_finishes_idle_or_error(self):
        for error in (None, "failure"):
            with self.subTest(error=error):
                self.coordinator.execute(command(Action.STOP_ALL))
                self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
                self.finish(self.runtime.started[-1], error)
                status = self.coordinator.status()
                self.assertEqual(status["service_state"], "error" if error else "idle")
                self.assertIsNone(status["effective"])
                self.assertIsNone(status["override"])

    def test_old_callbacks_with_reused_request_id_cannot_clear_replacement(self):
        old = self.runtime.started[-1]
        self.coordinator.execute(command(Action.SET_BASELINE, "Aurora"))
        for error, cancelled in ((None, False), ("stale failure", False), (None, True)):
            self.finish(old, error, cancelled)
            status = self.coordinator.status()
            self.assertEqual(status["service_state"], "running")
            self.assertEqual(status["effective"]["effect"], "Aurora")
            self.assertIsNone(status["latest_error"])

    def test_restored_baseline_has_fresh_run_identity(self):
        old = self.runtime.started[-1]
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.coordinator.execute(command(Action.CANCEL_OVERRIDE))
        self.finish(old)
        self.assertEqual(self.coordinator.status()["effective"]["effect"], "Fire")

    def test_start_failure_does_not_claim_old_or_candidate_is_running(self):
        self.runtime.fail_start = True
        result = self.coordinator.execute(command(Action.SET_BASELINE, "Aurora"))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status["service_state"], "error")
        self.assertIsNone(result.status["effective"])
        self.assertEqual(result.status["baseline"]["effect"], "Fire")

    def test_failed_restore_after_override_completion_is_not_running(self):
        self.coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora"))
        self.runtime.fail_start = True
        self.finish(self.runtime.started[-1])
        status = self.coordinator.status()
        self.assertEqual(status["service_state"], "error")
        self.assertIsNone(status["override"])
        self.assertIsNone(status["effective"])
        self.assertEqual(status["latest_error"], "start failed")


class WorkerTests(unittest.TestCase):
    def make_runtime(self, producer, *, timeout=0.05):
        from thunderdome.control import ControlSettings, FrameRuntime
        runtime = FrameRuntime(ControlSettings("http://unused.invalid"), producer,
                               stop_timeout=timeout)
        self.addCleanup(runtime.stop)
        return runtime

    def test_thread_start_failure_releases_unstarted_worker(self):
        runtime = self.make_runtime(lambda d: (lambda n, t: None, 30))
        coordinator = RuntimeCoordinator(runtime)
        with patch("thunderdome.control.threading.Thread.start", side_effect=RuntimeError("thread unavailable")):
            result = coordinator.execute(command(Action.SET_BASELINE))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status["service_state"], "error")
        self.assertIsNone(result.status["effective"])
        self.assertIsNone(runtime._thread)
        self.assertIsNone(runtime._cancel)
        self.assertIsNone(runtime.active_since)
        runtime.stop()

    def test_expiring_runtime_uses_lifetime_remaining_at_activation(self):
        from thunderdome.control import ControlSettings, FrameRuntime
        from thunderdome.sinks import NullFrameSink

        def activation_duration(now):
            runtime = FrameRuntime(ControlSettings("http://unused.invalid"), lambda d: (lambda n, t: None, 30), monotonic=lambda: now)
            runtime._sink = lambda mode: NullFrameSink()
            display = DisplayDefinition("Fire", {}, OutputMode.NULL, CommandSource.BROWSER, "timed", 100.0, expires_at=110.0)
            seen = []

            def loop(*args, **kwargs):
                seen.append(kwargs["duration"])
                return SimpleNamespace(interrupted=False)

            with patch("thunderdome.control.time.monotonic", return_value=now), patch(
                "thunderdome.control.run_frame_loop", side_effect=loop
            ):
                runtime._run(display, threading.Event())
            return seen, runtime.error

        self.assertEqual(activation_duration(100.0), ([10.0], None))
        self.assertEqual(activation_duration(105.0), ([5.0], None))
        almost_expired, error = activation_duration(109.9)
        self.assertAlmostEqual(almost_expired[0], 0.1)
        self.assertIsNone(error)
        self.assertEqual(activation_duration(111.0), ([], None))

    def test_stuck_worker_remains_owned_and_blocks_second_start(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def factory(display):
            calls.append(display)
            entered.set()
            release.wait()
            return lambda n, t: None, 30
        runtime = self.make_runtime(factory, timeout=0)
        self.addCleanup(release.set)
        display = DisplayDefinition(
            "Fire", {}, OutputMode.NULL, CommandSource.BROWSER, "same", 0)
        runtime.start(display)
        self.assertTrue(entered.wait(1))
        worker, cancel = runtime._thread, runtime._cancel
        try:
            with self.assertRaisesRegex(OSError, "did not stop"):
                runtime.stop()
            self.assertIs(runtime._thread, worker)
            self.assertIs(runtime._cancel, cancel)
            self.assertTrue(worker.is_alive())
            with self.assertRaisesRegex(OSError, "did not stop"):
                runtime.start(display)
            self.assertEqual(len(calls), 1)
            self.assertIs(runtime._thread, worker)
        finally:
            release.set()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        runtime.stop()
        self.assertIsNone(runtime._thread)
        self.assertIsNone(runtime._cancel)

    def test_worker_failure_updates_coordinator_after_sink_cleanup(self):
        from thunderdome.sinks import NullFrameSink
        for failure in (ValueError("renderer failed"), OSError("sink failed"),
                        OverflowError("overflow")):
            with self.subTest(failure=failure):
                entered, release, closed = threading.Event(), threading.Event(), threading.Event()
                def render(n, t):
                    entered.set()
                    release.wait()
                    raise failure
                runtime = self.make_runtime(lambda d: (render, 30))
                self.addCleanup(release.set)
                class Sink(NullFrameSink):
                    def close(self):
                        closed.set()
                runtime._sink = lambda mode: Sink()
                coordinator = RuntimeCoordinator(runtime)
                coordinator.execute(command(Action.SET_BASELINE))
                self.assertTrue(entered.wait(1))
                worker = runtime._thread
                release.set()
                worker.join(1)
                self.assertFalse(worker.is_alive())
                self.assertTrue(closed.is_set())
                self.assertIsNone(runtime._thread)
                status = coordinator.status()
                self.assertEqual(status["service_state"], "error")
                self.assertIsNone(status["effective"])
                self.assertEqual(status["latest_error"], str(failure))

    def test_factory_and_sink_failures_never_leave_dead_worker_running(self):
        from thunderdome.frame import RGBFrame
        from thunderdome.sinks import NullFrameSink, SinkResult
        for stage in ("factory", "open", "send", "result", "close"):
            with self.subTest(stage=stage):
                entered, release = threading.Event(), threading.Event()
                error = OSError(f"{stage} failed")
                def factory(display):
                    entered.set()
                    release.wait()
                    if stage == "factory":
                        raise error
                    return lambda n, t: RGBFrame.allocate(5000), 30
                class Sink(NullFrameSink):
                    def open(self):
                        if stage == "open":
                            raise error
                    def send_frame(self, frame):
                        if stage == "send":
                            raise error
                        if stage == "result":
                            return SinkResult("fake", False, str(error))
                        return super().send_frame(frame)
                    def close(self):
                        if stage == "close":
                            raise error
                def loop(producer, send, **kwargs):
                    send(producer(0, 0))
                    return SimpleNamespace(interrupted=False)
                runtime = self.make_runtime(factory)
                self.addCleanup(release.set)
                runtime._sink = lambda mode: Sink()
                coordinator = RuntimeCoordinator(runtime)
                with patch("thunderdome.control.run_frame_loop", side_effect=loop):
                    coordinator.execute(command(Action.SET_BASELINE))
                    self.assertTrue(entered.wait(1))
                    worker = runtime._thread
                    release.set()
                    worker.join(1)
                    self.assertFalse(worker.is_alive())
                    self.assertIsNone(runtime._thread)
                    status = coordinator.status()
                    self.assertEqual(status["service_state"], "error")
                    self.assertIsNone(status["effective"])
                    self.assertIn(str(error), status["latest_error"])

    def test_worker_finite_baseline_completes_after_sink_cleanup(self):
        from thunderdome.sinks import NullFrameSink
        entered, release, closed = (threading.Event() for _ in range(3))
        runtime = self.make_runtime(lambda d: (lambda n, t: None, 30, 1))
        self.addCleanup(release.set)
        class Sink(NullFrameSink):
            def close(self):
                closed.set()
        runtime._sink = lambda mode: Sink()
        def loop(*args, **kwargs):
            entered.set()
            release.wait()
            return SimpleNamespace(interrupted=False)
        with patch("thunderdome.control.run_frame_loop", side_effect=loop):
            coordinator = RuntimeCoordinator(runtime)
            coordinator.execute(command(Action.SET_BASELINE))
            self.assertTrue(entered.wait(1))
            worker = runtime._thread
            release.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertTrue(closed.is_set())
            self.assertIsNone(runtime._thread)
            status = coordinator.status()
            self.assertEqual(status["service_state"], "idle")
            self.assertIsNone(status["baseline"])
            self.assertIsNone(status["effective"])

    def test_callback_does_not_deadlock_with_command_joining_worker(self):
        entered = threading.Event()
        runtime = self.make_runtime(lambda d: (lambda n, t: None, 30))
        def loop(*args, cancel_event, **kwargs):
            entered.set()
            cancel_event.wait()
            return SimpleNamespace(interrupted=True)
        with patch("thunderdome.control.run_frame_loop", side_effect=loop):
            coordinator = RuntimeCoordinator(runtime)
            coordinator.execute(command(Action.SET_BASELINE))
            self.assertTrue(entered.wait(1))
            worker = runtime._thread
            result = coordinator.execute(command(Action.STOP_ALL))
            self.assertTrue(result.accepted, result.reason)
            self.assertFalse(worker.is_alive())
            self.assertIsNone(result.status["effective"])
            self.assertEqual(result.status["service_state"], "idle")

    def test_termination_queued_during_transition_is_drained_before_unlock(self):
        coordinator = RuntimeCoordinator(FakeRuntime())
        coordinator.execute(command(Action.SET_BASELINE))
        active = coordinator._active
        with coordinator._guard():
            worker = threading.Thread(target=coordinator.runtime_terminated,
                                      args=(active, "failure", False))
            worker.start()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertTrue(coordinator._notifications)
        self.assertFalse(coordinator._notifications)
        self.assertEqual(coordinator._state, "error")
        self.assertIsNone(coordinator._active)

    def test_stuck_worker_late_exit_does_not_leave_coordinator_running(self):
        entered, release = threading.Event(), threading.Event()
        def factory(display):
            entered.set()
            release.wait()
            return lambda n, t: None, 30
        runtime = self.make_runtime(factory, timeout=0)
        self.addCleanup(release.set)
        coordinator = RuntimeCoordinator(runtime)
        coordinator.execute(command(Action.SET_BASELINE))
        self.assertTrue(entered.wait(1))
        worker = runtime._thread
        result = coordinator.execute(command(Action.SET_BASELINE, "Aurora"))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status["effective"]["effect"], "Fire")
        release.set()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        status = coordinator.status()
        self.assertEqual(status["service_state"], "idle")
        self.assertIsNone(status["effective"])
        self.assertEqual(status["baseline"]["effect"], "Fire")

    def test_finite_override_restores_only_after_old_sink_closes(self):
        self.check_override_finish()

    def test_failed_override_restores_only_after_old_sink_closes(self):
        self.check_override_finish(OSError("override failed"))

    def check_override_finish(self, failure=None):
        from thunderdome.sinks import NullFrameSink
        entered, release, closed, restored, baseline_ready = (threading.Event() for _ in range(5))
        opens = []
        def factory(display):
            if display.effect == "Fire" and opens:
                self.assertTrue(closed.is_set())
                restored.set()
            return lambda n, t: None, 30
        runtime = self.make_runtime(factory)
        self.addCleanup(release.set)
        class Sink(NullFrameSink):
            def __enter__(self):
                opens.append(self)
                return self
            def close(self):
                if len(opens) == 2:
                    closed.set()
        runtime._sink = lambda mode: Sink()
        def loop(producer, send, *, cancel_event, **kwargs):
            if len(opens) == 2:
                entered.set()
                release.wait()
                if failure:
                    raise failure
                return SimpleNamespace(interrupted=False)
            baseline_ready.set()
            cancel_event.wait()
            return SimpleNamespace(interrupted=True)
        with patch("thunderdome.control.run_frame_loop", side_effect=loop):
            coordinator = RuntimeCoordinator(runtime)
            coordinator.execute(command(Action.SET_BASELINE))
            self.assertTrue(baseline_ready.wait(1))
            coordinator.execute(command(Action.APPLY_OVERRIDE, "Aurora", duration=60))
            self.assertTrue(entered.wait(1))
            worker = runtime._thread
            release.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertTrue(restored.wait(1))
            status = coordinator.status()
            self.assertIsNone(status["override"])
            self.assertEqual(status["effective"]["effect"], "Fire")
            self.assertEqual(status["latest_error"], str(failure) if failure else None)
            coordinator.execute(command(Action.STOP_ALL))


if __name__ == "__main__":
    unittest.main()
