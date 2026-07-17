from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import parse_args
from thunderdome.config import CONTROLLERS_PATH, GEOMETRY_PATH, LED_POSITIONS_PATH


class DefaultPathRegressionTests(unittest.TestCase):
    def test_builtin_effect_defaults_are_project_anchored_from_any_cwd(self):
        original = Path.cwd()
        try:
            for directory in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[3]):
                os.chdir(directory)
                args = parse_args(["effect", "expanding-rings"])
                self.assertEqual(Path(args.geometry), GEOMETRY_PATH)
                self.assertEqual(Path(args.positions), LED_POSITIONS_PATH)
                self.assertEqual(Path(args.controllers), CONTROLLERS_PATH)
            with tempfile.TemporaryDirectory() as temporary:
                os.chdir(temporary)
                args = parse_args(["effect", "height-wave"])
                self.assertEqual(Path(args.geometry), GEOMETRY_PATH)
                self.assertEqual(Path(args.positions), LED_POSITIONS_PATH)
                self.assertEqual(Path(args.controllers), CONTROLLERS_PATH)
        finally:
            os.chdir(original)

    def test_explicit_relative_paths_remain_process_cwd_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = Path.cwd()
            try:
                os.chdir(temporary)
                args = parse_args([
                    "effect", "expanding-rings", "--geometry", "local/geometry.json",
                    "--positions", "local/positions.json", "--controllers", "local/controllers.json",
                ])
                self.assertEqual(Path(args.geometry), Path("local/geometry.json"))
                self.assertEqual(Path(args.positions), Path("local/positions.json"))
                self.assertEqual(Path(args.controllers), Path("local/controllers.json"))
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
