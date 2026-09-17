from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import parse_args
from thunderdome.config import CONTROLLERS_PATH, GEOMETRY_PATH, LED_POSITIONS_PATH, ROUTES_PATH
from thunderdome.simulator import resolve_user_path


class DefaultPathRegressionTests(unittest.TestCase):
    def test_immutable_resources_resolve_from_source_or_installed_data_root(self):
        from thunderdome.config import SIMULATOR_STATIC_PATH, installed_resource_root, resource_root
        root = resource_root()
        self.assertTrue((root / "geometry" / "thunderdome_geometry.json").is_file())
        self.assertEqual(GEOMETRY_PATH, root / "geometry" / "thunderdome_geometry.json")
        self.assertEqual(ROUTES_PATH, root / "geometry" / "routes" / "string_routes.json")
        self.assertEqual(SIMULATOR_STATIC_PATH, root / "simulator" / "static")
        for asset in ("index.html", "simulator.css", "simulator.js", "control-ui.js", "vendor/three.module.js", "vendor/OrbitControls.js", "vendor/LICENSE.threejs"):
            self.assertTrue((SIMULATOR_STATIC_PATH / asset).is_file())
        self.assertEqual(installed_resource_root(Path("/isolated/data")), Path("/isolated/data/share/thunderdome"))

    def test_mutable_runtime_paths_use_source_overrides_or_xdg(self):
        from thunderdome.config import EFFECT_DEFAULTS_PATH, mutable_runtime_paths
        source = Path("/source")
        self.assertEqual(mutable_runtime_paths(source_root=source, environ={}, home=Path("/home/user")), (source / "config/controllers.json", source / "config/effect-defaults.json", source / "geometry/generated/led_positions_3d.json"))
        self.assertEqual(mutable_runtime_paths(source_root=source, environ={"THUNDERDOME_CONFIG_DIR": "/override/config", "THUNDERDOME_DATA_DIR": "/override/data"}, home=Path("/home/user")), (Path("/override/config/controllers.json"), Path("/override/config/effect-defaults.json"), Path("/override/data/led_positions_3d.json")))
        self.assertEqual(mutable_runtime_paths(source_root=None, environ={"XDG_CONFIG_HOME": "/xdg/config", "XDG_DATA_HOME": "/xdg/data"}, home=Path("/home/user")), (Path("/xdg/config/thunderdome/controllers.json"), Path("/xdg/config/thunderdome/effect-defaults.json"), Path("/xdg/data/thunderdome/led_positions_3d.json")))
        self.assertEqual(EFFECT_DEFAULTS_PATH.name, "effect-defaults.json")
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

    def test_positions_generation_uses_the_canonical_default_and_keeps_overrides(self):
        self.assertEqual(Path(parse_args(["positions", "generate"]).path), LED_POSITIONS_PATH)
        self.assertEqual(Path(parse_args(["positions", "generate", "--path", "local/positions.json"]).path), Path("local/positions.json"))

    def test_route_consumers_default_to_structured_route_authority(self):
        self.assertEqual(Path(parse_args(["route", "validate"]).route_path), ROUTES_PATH)
        self.assertEqual(Path(parse_args(["positions", "generate"]).route_path), ROUTES_PATH)
        for command in (["simulator", "serve"], ["control", "serve"]):
            self.assertEqual(resolve_user_path(parse_args(command).routes, ROUTES_PATH), ROUTES_PATH)


if __name__ == "__main__":
    unittest.main()
