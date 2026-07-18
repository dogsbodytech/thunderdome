from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome import cli
from thunderdome.effects.registry import BY_NAME, DEFAULT_PLAYLIST, PRESETS
from thunderdome.frame import RGBFrame

ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS = ROOT / "config" / "controllers.example.json"


class FakeStats:
    def __init__(self, frames: int, elapsed: float):
        self.frames_sent = frames
        self.elapsed_seconds = elapsed
        self.interrupted = False


def fake_loop(times):
    calls = []

    def runner(producer, sender, *, fps, duration=None, loops=None, **_):
        selected = [t for t in times if duration is None or t < duration]
        if loops is not None:
            selected = selected[:loops]
        for number, elapsed in enumerate(selected):
            frame = producer(number, elapsed)
            assert isinstance(frame, RGBFrame)
            assert len(frame.data) == 15000
            sender(frame)
            calls.append((number, elapsed, bytes(frame.data)))
        return FakeStats(len(selected), selected[-1] if selected else 0.0)

    runner.calls = calls
    return runner


class PR9CorrectionTests(unittest.TestCase):
    def test_effect_help_does_not_expose_prepare_ddp_and_options_are_relevant(self):
        commands = ["clock-hand", "expanding-rings", "height-wave", "fire", "rotating-plane", "radar", "aurora", "fireflies", "auto"]
        for command in commands:
            with self.subTest(command=command):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit):
                    cli.parse_args(["effect", command, "--help"])
                help_text = stdout.getvalue()
                self.assertNotIn("--prepare" "-ddp", help_text)
        fire_help = self._help("fire")
        self.assertIn("--flame-height-m", fire_help)
        self.assertNotIn("--rotation-seconds", fire_help)
        self.assertNotIn("--count", fire_help)
        plane_help = self._help("rotating-plane")
        self.assertIn("--axis", plane_help)
        self.assertIn("--loops", plane_help)
        self.assertNotIn("--flame-height-m", plane_help)
        aurora_help = self._help("aurora")
        self.assertNotIn("--loops", aurora_help)
        self.assertIn("--band-width", aurora_help)
        fireflies_help = self._help("fireflies")
        self.assertIn("--color-variation", fireflies_help)
        self.assertNotIn("--loops", fireflies_help)
        auto_help = self._help("auto")
        self.assertNotIn("--hold", auto_help)

    def _help(self, command: str) -> str:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit):
            cli.parse_args(["effect", command, "--help"])
        return stdout.getvalue()

    def test_registry_contains_unique_default_playlist_and_valid_presets(self):
        self.assertEqual(set(DEFAULT_PLAYLIST), set(BY_NAME))
        self.assertEqual(len(DEFAULT_PLAYLIST), 9)
        self.assertEqual(len(DEFAULT_PLAYLIST), len(set(DEFAULT_PLAYLIST)))
        for preset in PRESETS.values():
            self.assertTrue(preset)
            self.assertTrue(set(preset) <= set(BY_NAME))
        with self.assertRaises(ValueError):
            cli._resolve_auto_playlist("missing", None, False, 1)

    def test_real_main_path_reaches_each_effect_handler_in_dry_run(self):
        commands = {
            "clock-hand": ["--rotations", "1"],
            "expanding-rings": ["--loops", "1"],
            "height-wave": ["--loops", "1"],
            "fire": ["--duration", "0.4"],
            "rotating-plane": ["--loops", "1"],
            "radar": ["--loops", "1"],
            "aurora": ["--duration", "0.4"],
            "fireflies": ["--duration", "0.4", "--count", "3"],
            "twinkle": ["--duration", "0.4"],
        }
        for command, extra in commands.items():
            with self.subTest(command=command):
                runner = fake_loop([0.0, 0.2, 0.4])
                with patch("thunderdome.cli.run_frame_loop", runner), patch("thunderdome.cli.run_wled_operation") as wled:
                    result = cli.main(["effect", command, "--controllers", str(CONTROLLERS), "--fps", "5", "--dry-run", *extra])
                self.assertEqual(result, 0)
                self.assertGreaterEqual(len(runner.calls), 2)
                wled.assert_not_called()

    def test_auto_defaults_continuous_and_finite_modes_validate(self):
        args = cli.parse_args(["effect", "auto"])
        self.assertIsNone(args.duration)
        self.assertIsNone(args.cycles)
        self.assertEqual(args.interval, 30)
        self.assertEqual(args.transition, 2)
        with self.assertRaises(SystemExit):
            cli.parse_args(["effect", "auto", "--cycles", "1", "--duration", "1"])
        self.assertEqual(cli._auto_duration(args, ["fire", "aurora"]), None)
        args = cli.parse_args(["effect", "auto", "--cycles", "2", "--interval", "3"])
        self.assertEqual(cli._auto_duration(args, ["fire", "aurora"]), 12)
        args = cli.parse_args(["effect", "auto", "--duration", "5"])
        self.assertEqual(cli._auto_duration(args, ["fire", "aurora"]), 5)

    def test_auto_scheduler_advances_playlist_transitions_and_brightness_once(self):
        names = ["fire", "aurora", "fireflies"]
        calls = []

        def renderer(name, elapsed):
            calls.append((name, round(elapsed, 2)))
            value = {"fire": 100, "aurora": 200, "fireflies": 50}[name]
            return RGBFrame.allocate(5000, (value, 0, 0))

        frame0 = cli._auto_frame_for_elapsed(names, renderer, elapsed=0.0, interval=0.4, transition=0.1, brightness=24)
        frame1 = cli._auto_frame_for_elapsed(names, renderer, elapsed=0.35, interval=0.4, transition=0.1, brightness=24)
        frame2 = cli._auto_frame_for_elapsed(names, renderer, elapsed=0.45, interval=0.4, transition=0.1, brightness=24)
        frame3 = cli._auto_frame_for_elapsed(names, renderer, elapsed=0.85, interval=0.4, transition=0.1, brightness=24)
        self.assertEqual(tuple(frame0.data[:3]), (100 * 24 // 255, 0, 0))
        self.assertNotEqual(tuple(frame1.data[:3]), (100 * 24 // 255, 0, 0))
        self.assertEqual(tuple(frame2.data[:3]), (200 * 24 // 255, 0, 0))
        self.assertEqual(tuple(frame3.data[:3]), (50 * 24 // 255, 0, 0))
        self.assertIn(("fire", 0.35), calls)
        self.assertIn(("aurora", 0.05), calls)

    def test_auto_dry_run_uses_scheduler_and_one_session(self):
        runner = fake_loop([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        with patch("thunderdome.cli.run_frame_loop", runner), patch("thunderdome.cli.run_wled_operation") as wled:
            result = cli.main([
                "effect", "auto", "--controllers", str(CONTROLLERS), "--effects", "fire,aurora,fireflies",
                "--cycles", "1", "--interval", "0.4", "--transition", "0.1", "--fps", "5", "--brightness", "24", "--dry-run",
            ])
        self.assertEqual(result, 0)
        self.assertGreaterEqual(len(runner.calls), 5)
        wled.assert_not_called()

    def test_auto_controller_failure_is_nonzero(self):
        runner = fake_loop([0.0])

        class FailingSession:
            instances = 0

            def __init__(self, *_args, **_kwargs):
                FailingSession.instances += 1

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def send_frame(self, _frame, *, dry_run=False):
                from thunderdome.transport.multi_ddp import SendResult
                return [SendResult(1, "controller-1", 0, 0.0, "simulated failure")]

        with patch("thunderdome.cli.run_frame_loop", runner), patch("thunderdome.cli.MultiControllerDDPSession", FailingSession):
            result = cli.main([
                "effect", "auto", "--controllers", str(CONTROLLERS), "--effects", "fire,aurora",
                "--duration", "0.2", "--interval", "0.4", "--transition", "0", "--fps", "5", "--dry-run",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(FailingSession.instances, 0)

    def test_playlist_validation_order_duplicates_and_shuffle(self):
        self.assertEqual(cli._resolve_auto_playlist("fire,aurora,fireflies", None, False, 1), ["fire", "aurora", "fireflies"])
        with self.assertRaises(ValueError):
            cli._resolve_auto_playlist("fire,fire", None, False, 1)
        with self.assertRaises(ValueError):
            cli._resolve_auto_playlist("", None, False, 1)
        a = cli._resolve_auto_playlist(None, None, True, 42)
        b = cli._resolve_auto_playlist(None, None, True, 42)
        self.assertEqual(a, b)
        self.assertNotEqual(a, list(DEFAULT_PLAYLIST))


if __name__ == "__main__":
    unittest.main()
