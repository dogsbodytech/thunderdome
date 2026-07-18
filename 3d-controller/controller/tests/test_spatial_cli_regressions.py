from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import main, parse_args
from thunderdome.effects.common import SpatialContext
from thunderdome.frame import RGBFrame
from thunderdome.transport.multi_ddp import SendResult


ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS = ROOT / "config" / "controllers.example.json"


def result(error: str | None = None) -> list[SendResult]:
    return [SendResult(1, "controller-1", 3, 0.0, error)]


class Session:
    def __init__(self):
        self.frames = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def send_frame(self, frame, *, dry_run=False):
        self.frames.append((frame, dry_run))
        return result()


class SpatialCLIRegressionTests(unittest.TestCase):
    def test_spatial_commands_use_loops_not_rotations_and_prepare_removed(self):
        for command in ("expanding-rings", "height-wave"):
            args = parse_args(["effect", command, "--loops", "2"])
            self.assertEqual(args.loops, 2)
            self.assertFalse(hasattr(args, "prepare_ddp"))
            with self.assertRaises(SystemExit):
                parse_args(["effect", command, "--prepare" "-ddp"])
            with self.assertRaises(SystemExit):
                parse_args(["effect", command, "--rotations", "2"])
        self.assertEqual(parse_args(["effect", "clock-hand", "--rotations", "2"]).rotations, 2)
        with self.assertRaises(SystemExit):
            parse_args(["effect", "height-wave", "--loops", "0"])

    def test_spatial_loop_modes_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            parse_args(["effect", "expanding-rings", "--hold", "--duration", "1"])

    def test_effect_runners_do_not_call_prepare_operation(self):
        context = Mock(spec=SpatialContext)
        session = Session()
        calls = []

        def loop(producer, sender, **_kwargs):
            calls.append("stream")
            sender(producer(0, 0.0))
            return Mock(frames_sent=1, elapsed_seconds=0.0, interrupted=False)

        with patch("thunderdome.cli.SpatialContext.load", return_value=context), patch(
            "thunderdome.cli.selected_xyz", return_value=((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        ), patch(
            "thunderdome.cli.run_wled_operation"
        ) as prepare, patch("thunderdome.cli.render_height_wave", return_value=RGBFrame.allocate(5_000)), patch("thunderdome.cli.MultiControllerDDPSession", return_value=session), patch(
            "thunderdome.cli.run_frame_loop", side_effect=loop
        ):
            self.assertEqual(main(["effect", "height-wave", "--output", "null", "--controllers", str(CONTROLLERS), "--loops", "1"]), 0)
        prepare.assert_not_called()
        self.assertEqual(calls, ["stream"])

    def test_dry_run_uses_ddp_dry_run_without_http(self):
        context = Mock(spec=SpatialContext)
        session = Session()
        with patch("thunderdome.cli.SpatialContext.load", return_value=context), patch(
            "thunderdome.cli.selected_xyz", return_value=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        ), patch("thunderdome.cli.parse_spatial_origin", return_value=(0.0, 0.0, 0.0)), patch(
            "thunderdome.cli.render_expanding_rings", return_value=RGBFrame.allocate(5_000)
        ), patch(
            "thunderdome.cli.run_wled_operation"
        ) as prepare, patch("thunderdome.cli.MultiControllerDDPSession", return_value=session), patch(
            "thunderdome.cli.run_frame_loop", side_effect=lambda producer, sender, **_: (sender(producer(0, 0.0)) or Mock(frames_sent=1, elapsed_seconds=0.0, interrupted=False))
        ):
            self.assertEqual(main(["effect", "expanding-rings", "--controllers", str(CONTROLLERS), "--dry-run", "--loops", "1"]), 0)
        prepare.assert_not_called()
        self.assertEqual(session.frames, [])


if __name__ == "__main__":
    unittest.main()
