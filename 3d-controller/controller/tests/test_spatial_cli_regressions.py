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
    def test_spatial_commands_use_loops_not_rotations_and_parse_new_options(self):
        for command in ("expanding-rings", "height-wave"):
            args = parse_args(["effect", command, "--loops", "2", "--prepare-ddp"])
            self.assertEqual(args.loops, 2)
            self.assertTrue(args.prepare_ddp)
            with self.assertRaises(SystemExit):
                parse_args(["effect", command, "--rotations", "2"])
        self.assertEqual(parse_args(["effect", "clock-hand", "--rotations", "2"]).rotations, 2)
        with self.assertRaises(SystemExit):
            parse_args(["effect", "height-wave", "--loops", "0"])

    def test_spatial_loop_modes_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            parse_args(["effect", "expanding-rings", "--hold", "--duration", "1"])

    def test_prepare_runs_once_before_streaming_and_failures_abort(self):
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
            "thunderdome.cli.run_wled_operation", return_value=[]
        ) as prepare, patch("thunderdome.cli.render_height_wave", return_value=RGBFrame.allocate(5_000)), patch("thunderdome.cli.MultiControllerDDPSession", return_value=session), patch(
            "thunderdome.cli.run_frame_loop", side_effect=loop
        ):
            self.assertEqual(main(["effect", "height-wave", "--controllers", str(CONTROLLERS), "--prepare-ddp", "--loops", "1"]), 0)
        prepare.assert_called_once()
        self.assertEqual(calls, ["stream"])

        with patch("thunderdome.cli.SpatialContext.load", return_value=context), patch(
            "thunderdome.cli.selected_xyz", return_value=((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        ), patch(
            "thunderdome.cli.run_wled_operation", return_value=[Mock(error="offline", controller_number=1, host="bad")]
        ) as prepare, patch("thunderdome.cli.MultiControllerDDPSession") as ddp:
            self.assertEqual(main(["effect", "height-wave", "--controllers", str(CONTROLLERS), "--prepare-ddp", "--loops", "1"]), 1)
        prepare.assert_called_once()
        ddp.assert_not_called()

    def test_prepare_is_omitted_normally_and_dry_run_never_uses_http(self):
        context = Mock(spec=SpatialContext)
        session = Session()
        with patch("thunderdome.cli.SpatialContext.load", return_value=context), patch(
            "thunderdome.cli.selected_xyz", return_value=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        ), patch("thunderdome.cli.parse_spatial_origin", return_value=(0.0, 0.0, 0.0)), patch(
            "thunderdome.cli.render_expanding_rings", return_value=RGBFrame.allocate(5_000)
        ), patch(
            "thunderdome.cli.run_wled_operation"
        ) as prepare, patch("thunderdome.cli.MultiControllerDDPSession", return_value=session):
            self.assertEqual(main(["effect", "expanding-rings", "--controllers", str(CONTROLLERS), "--dry-run", "--prepare-ddp", "--loops", "1"]), 0)
        prepare.assert_not_called()
        self.assertEqual(session.frames[0][1], True)


if __name__ == "__main__":
    unittest.main()
