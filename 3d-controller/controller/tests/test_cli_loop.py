import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import main, parse_args
from thunderdome.animation.loop import FrameLoopStats
from thunderdome.frame import RGBFrame
from thunderdome.transport.ddp import packets_for_frame
from thunderdome.transport.multi_ddp import SendResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS_EXAMPLE = PROJECT_ROOT / "config" / "controllers.example.json"


def controller_results(*, failed_controller: int | None = None):
    return [
        SendResult(
            controller_number=number,
            host=f"controller-{number}",
            packets=0 if number == failed_controller else 3,
            duration_seconds=0.0,
            error="simulated failure" if number == failed_controller else None,
        )
        for number in range(1, 6)
    ]


class FakeMultiSession:
    def __init__(self, result_sets):
        self.result_sets = iter(result_sets)
        self.frames = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def send_frame(self, frame, *, dry_run=False):
        self.frames.append((frame, dry_run))
        return next(self.result_sets)


class CLILoopTests(unittest.TestCase):
    def test_single_controller_dispatches_each_persistent_operation(self):
        cases = [
            (["power", "on"], "set_power", (True,)),
            (["live", "off"], "set_live", (False,)),
            (["color", "#010203"], "set_color", ((1, 2, 3),)),
            (["effect", "2"], "set_effect", (2,)),
            (["palette", "3"], "set_palette", (3,)),
            (["preset", "4"], "set_preset", (4,)),
            (["prepare-ddp"], "prepare_ddp", ()),
        ]
        for arguments, method, expected in cases:
            with self.subTest(method=method):
                client = Mock()
                with patch("thunderdome.cli.WLEDClient", return_value=client):
                    self.assertEqual(main(["controller", *arguments[:1], "--host", "example.test", *arguments[1:]]), 0)
                getattr(client, method).assert_called_once_with(*expected)
                if method == "set_power": client.set_live.assert_not_called()

    def test_clock_hand_parser_uses_exclude_tail_and_rejects_include_tail(self):
        args = parse_args(["effect", "clock-hand", "--exclude-tail"])
        self.assertTrue(args.exclude_tail)
        with self.assertRaises(SystemExit):
            parse_args(["effect", "clock-hand", "--include-tail"])

    def test_new_spatial_effect_parsers_expose_bounded_metric_controls(self):
        rings = parse_args(
            ["effect", "expanding-rings", "--ring-spacing-mm", "900", "--ring-width-mm", "120", "--speed-mm-per-second", "300"]
        )
        wave = parse_args(
            ["effect", "height-wave", "--wave-spacing-mm", "800", "--wave-width-mm", "100", "--speed-mm-per-second", "250"]
        )
        self.assertEqual((rings.ring_spacing_mm, rings.ring_width_mm, rings.speed_mm_per_second), (900, 120, 300))
        self.assertEqual((wave.wave_spacing_mm, wave.wave_width_mm, wave.speed_mm_per_second), (800, 100, 250))

    def test_expanding_rings_dry_run_renders_and_does_not_open_network_sockets(self):
        session = FakeMultiSession([controller_results()])
        rendered = RGBFrame.allocate(5_000, (1, 2, 3))
        stdout = io.StringIO()
        with patch("thunderdome.cli.SpatialContext.load", return_value=Mock()) as load_context, patch(
            "thunderdome.cli.render_expanding_rings", return_value=rendered
        ) as render, patch("thunderdome.cli.MultiControllerDDPSession", return_value=session):
            with contextlib.redirect_stdout(stdout):
                result = main(["effect", "expanding-rings", "--controllers", str(CONTROLLERS_EXAMPLE), "--dry-run"])

        self.assertEqual(result, 0)
        load_context.assert_called_once()
        render.assert_called_once()
        self.assertEqual(session.frames, [(rendered, True)])
        self.assertIn("controller 1", stdout.getvalue())
    def test_multi_dry_run_rejects_loop_controls(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(
                [
                    "ddp-all",
                    "clear",
                    "--controllers",
                    str(CONTROLLERS_EXAMPLE),
                    "--dry-run",
                    "--loops",
                    "2",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("dry-run cannot be combined", stderr.getvalue())

    def test_multi_live_continues_after_a_controller_failure(self):
        clients = [Mock() for _ in range(5)]
        clients[2].set_live.side_effect = OSError("offline")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("thunderdome.cli.WLEDClient", side_effect=clients) as client_class:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(
                    [
                        "controllers",
                        "live",
                        "--controllers",
                        str(CONTROLLERS_EXAMPLE),
                        "on",
                    ]
                )

        self.assertEqual(result, 1)
        self.assertEqual(client_class.call_count, 5)
        for client in clients:
            client.set_live.assert_called_once_with(True)
        self.assertIn("controller 3", stderr.getvalue())

    def test_single_ddp_default_builds_a_1000_led_three_packet_frame(self):
        captured_frames = []

        def fake_send(_host, frame, **_kwargs):
            captured_frames.append(frame)
            return len(packets_for_frame(frame))

        with patch("thunderdome.cli.send_frame", side_effect=fake_send):
            result = main(["ddp", "pixel", "--host", "example.test", "20", "--color", "FF0000", "--brightness", "255"])

        self.assertEqual(result, 0)
        self.assertEqual(len(captured_frames), 1)
        self.assertEqual(len(captured_frames[0]), 1_000 * 3)
        self.assertEqual(len(packets_for_frame(captured_frames[0])), 3)

    def test_single_ddp_led_count_override_is_preserved(self):
        captured_frames = []

        def fake_send(_host, frame, **_kwargs):
            captured_frames.append(frame)
            return len(packets_for_frame(frame))

        with patch("thunderdome.cli.send_frame", side_effect=fake_send):
            result = main(["ddp", "clear", "--host", "example.test", "--led-count", "12"])

        self.assertEqual(result, 0)
        self.assertEqual(len(captured_frames[0]), 12 * 3)

    def test_ddp_all_one_shot_returns_nonzero_for_any_controller_failure(self):
        session = FakeMultiSession([controller_results(failed_controller=2)])
        stdout = io.StringIO()
        with patch("thunderdome.cli.MultiControllerDDPSession", return_value=session):
            with contextlib.redirect_stdout(stdout):
                result = main(["ddp-all", "clear", "--controllers", str(CONTROLLERS_EXAMPLE)])

        self.assertEqual(result, 1)
        self.assertEqual(session.frames[0][0].led_count, 5_000)
        self.assertIn("controller 2 controller-2: 0 packets error=simulated failure", stdout.getvalue())

    def test_ddp_all_stream_preserves_an_early_controller_failure(self):
        session = FakeMultiSession([controller_results(failed_controller=1), controller_results()])

        def run_two_frames(_producer, sender, **_kwargs):
            sender(None)
            sender(None)
            return FrameLoopStats(frames_sent=2, elapsed_seconds=0.0)

        stdout = io.StringIO()
        with patch("thunderdome.cli.MultiControllerDDPSession", return_value=session), patch(
            "thunderdome.cli.run_frame_loop", side_effect=run_two_frames
        ):
            with contextlib.redirect_stdout(stdout):
                result = main(["ddp-all", "clear", "--controllers", str(CONTROLLERS_EXAMPLE), "--loops", "2"])

        self.assertEqual(result, 1)
        self.assertEqual(len(session.frames), 2)
        self.assertIn("controller 1 controller-1: 0 packets error=simulated failure", stdout.getvalue())

    def test_ddp_all_successful_stream_returns_zero(self):
        session = FakeMultiSession([controller_results()])

        def run_one_frame(_producer, sender, **_kwargs):
            sender(None)
            return FrameLoopStats(frames_sent=1, elapsed_seconds=0.0, interrupted=True)

        with patch("thunderdome.cli.MultiControllerDDPSession", return_value=session), patch(
            "thunderdome.cli.run_frame_loop", side_effect=run_one_frame
        ):
            result = main(["ddp-all", "clear", "--controllers", str(CONTROLLERS_EXAMPLE), "--hold"])

        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
