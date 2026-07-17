import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import main


class CLILoopTests(unittest.TestCase):
    def test_multi_dry_run_rejects_loop_controls(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(
                [
                    "ddp-all",
                    "clear",
                    "--controllers",
                    "config/controllers.example.json",
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
                        "config/controllers.example.json",
                        "on",
                    ]
                )

        self.assertEqual(result, 1)
        self.assertEqual(client_class.call_count, 5)
        for client in clients:
            client.set_live.assert_called_once_with(True)
        self.assertIn("controller 3", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
