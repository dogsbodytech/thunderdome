from __future__ import annotations

import json
import math
import socket
import sys
import threading
import time
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome import cli
from thunderdome.config import GEOMETRY_PATH, LED_POSITIONS_PATH, PROJECT_ROOT, REFERENCE_ROUTE_PATH
from thunderdome.simulator import (
    SimulatorDataError,
    build_simulator_payload,
    create_http_server,
    resolve_user_path,
    simulator_static_dir,
    validate_simulator_data,
)


class SimulatorDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_simulator_payload(GEOMETRY_PATH, REFERENCE_ROUTE_PATH, LED_POSITIONS_PATH)

    def test_metadata_reports_authoritative_counts_and_paths_without_ips(self):
        metadata = self.payload["metadata"]
        self.assertEqual(metadata["schema_version"], 1)
        self.assertEqual(metadata["simulator_mode"], "static viewer")
        self.assertEqual(metadata["total_led_count"], 5000)
        self.assertEqual(metadata["controller_count"], 5)
        self.assertEqual(metadata["string_count"], 5)
        self.assertEqual(metadata["route_count"], 5)
        self.assertEqual(metadata["routes_source"], str(REFERENCE_ROUTE_PATH))
        self.assertEqual(metadata["routes_source_filename"], REFERENCE_ROUTE_PATH.name)
        self.assertEqual(metadata["hub_count"], 61)
        self.assertEqual(metadata["spar_count"], 165)
        self.assertGreater(metadata["tail_count"], 0)
        self.assertEqual(metadata["apex"]["id"], "H061")
        self.assertTrue(all(math.isfinite(metadata["bounds"][axis][0]) for axis in "xyz"))
        blob = json.dumps(self.payload)
        self.assertNotIn("host", blob.lower())
        self.assertNotIn("ip", blob.lower())

    def test_geometry_normalization_has_hubs_spars_apex_and_bounds(self):
        geometry = self.payload["geometry"]
        self.assertEqual(len(geometry["hubs"]), 61)
        self.assertEqual(len(geometry["spars"]), 165)
        hub_ids = {hub["id"] for hub in geometry["hubs"]}
        self.assertIn("H061", hub_ids)
        for spar in geometry["spars"]:
            self.assertIn(spar["start_hub"], hub_ids)
            self.assertIn(spar["end_hub"], hub_ids)
            self.assertEqual(len(spar["start_xyz"]), 3)
            self.assertEqual(len(spar["end_xyz"]), 3)
        self.assertEqual(geometry["apex_id"], "H061")

    def test_led_records_are_ordered_and_preserve_string_mapping_and_tails(self):
        leds = self.payload["leds"]
        self.assertEqual(len(leds), 5000)
        self.assertEqual([led["global_index"] for led in leds], list(range(5000)))
        self.assertEqual({led["controller_number"] for led in leds}, {1, 2, 3, 4, 5})
        self.assertEqual({led["string_id"] for led in leds}, {0, 1, 2, 3, 4})
        for controller in range(1, 6):
            group = [led for led in leds if led["controller_number"] == controller]
            self.assertEqual(len(group), 1000)
            self.assertEqual(group[0]["global_index"], (controller - 1) * 1000)
            self.assertEqual(group[-1]["global_index"], controller * 1000 - 1)
            self.assertEqual([led["local_index"] for led in group], list(range(1000)))
        tails = [led for led in leds if led["is_tail"]]
        self.assertEqual(len(tails), self.payload["metadata"]["tail_count"])
        self.assertTrue(all("tail_index" in led for led in tails))
        self.assertTrue(all(math.isfinite(coord) for led in leds for coord in led["xyz"]))

    def test_validate_rejects_bad_led_indexing(self):
        payload = json.loads(json.dumps(self.payload))
        payload["leds"][42]["global_index"] = 99
        with self.assertRaises(SimulatorDataError):
            validate_simulator_data(payload, GEOMETRY_PATH, REFERENCE_ROUTE_PATH, LED_POSITIONS_PATH)

    def test_path_resolution_defaults_are_project_root_and_explicit_relatives_are_cwd_relative(self):
        self.assertEqual(resolve_user_path(None, GEOMETRY_PATH), GEOMETRY_PATH)
        self.assertEqual(resolve_user_path(None, REFERENCE_ROUTE_PATH), REFERENCE_ROUTE_PATH)
        relative = resolve_user_path("somewhere/file.json", GEOMETRY_PATH)
        self.assertEqual(relative, Path("somewhere/file.json"))

    def test_explicit_json_routes_are_loaded_with_geometry_and_positions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            geometry_path = Path(temp_dir) / "custom_geometry.json"
            route_path = Path(temp_dir) / "custom_routes.json"
            positions_path = Path(temp_dir) / "custom_positions.json"
            geometry_path.write_text(GEOMETRY_PATH.read_text(), encoding="utf-8")
            route_path.write_text((PROJECT_ROOT / "geometry" / "routes" / "string_routes.json").read_text(), encoding="utf-8")
            positions_path.write_text(LED_POSITIONS_PATH.read_text(), encoding="utf-8")
            payload = build_simulator_payload(geometry_path, route_path, positions_path)
        self.assertEqual(payload["metadata"]["routes_source"], str(route_path))
        self.assertEqual(payload["metadata"]["route_count"], 5)

    def test_bad_route_hub_and_spar_references_are_rejected_with_route_path(self):
        route_doc = json.loads((PROJECT_ROOT / "geometry" / "routes" / "string_routes.json").read_text())
        with tempfile.TemporaryDirectory() as temp_dir:
            route_path = Path(temp_dir) / "custom_routes.json"
            route_doc["routes"][0]["segments"][0]["from_hub"] = "H999"
            route_path.write_text(json.dumps(route_doc), encoding="utf-8")
            with self.assertRaisesRegex(SimulatorDataError, rf"{route_path}.*unknown hub.*H999"):
                build_simulator_payload(GEOMETRY_PATH, route_path, LED_POSITIONS_PATH)
            route_doc["routes"][0]["segments"][0]["from_hub"] = "H032"
            route_doc["routes"][0]["segments"][0]["spar_id"] = "S999"
            route_path.write_text(json.dumps(route_doc), encoding="utf-8")
            with self.assertRaisesRegex(SimulatorDataError, rf"{route_path}.*unknown spar.*S999"):
                build_simulator_payload(GEOMETRY_PATH, route_path, LED_POSITIONS_PATH)

    def test_malformed_routes_and_positions_route_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            route_path = Path(temp_dir) / "custom_routes.json"
            route_path.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(SimulatorDataError, rf"{route_path}.*malformed routes JSON"):
                build_simulator_payload(GEOMETRY_PATH, route_path, LED_POSITIONS_PATH)

            route_path.write_text((PROJECT_ROOT / "geometry" / "routes" / "string_routes.json").read_text(), encoding="utf-8")
            positions_path = Path(temp_dir) / "custom_positions.json"
            positions = json.loads(LED_POSITIONS_PATH.read_text())
            positions["leds"][0]["from_hub"] = "H033"
            positions_path.write_text(json.dumps(positions), encoding="utf-8")
            with self.assertRaisesRegex(SimulatorDataError, rf"{positions_path}.*conflicts with {route_path}"):
                build_simulator_payload(GEOMETRY_PATH, route_path, positions_path)


class SimulatorStaticAssetTests(unittest.TestCase):
    def test_static_assets_are_local_and_include_vendor_license(self):
        static = simulator_static_dir()
        required = [
            static / "index.html",
            static / "simulator.css",
            static / "simulator.js",
            static / "vendor" / "three.module.js",
            static / "vendor" / "OrbitControls.js",
            static / "vendor" / "LICENSE.threejs",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)
        for path in required[:3]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"https?://|src=\"//|href=\"//")
            self.assertNotIn("fonts.googleapis", text)
            self.assertNotIn("sourceMappingURL=http", text)
        controls = (static / "vendor" / "OrbitControls.js").read_text(encoding="utf-8")
        self.assertIn("from './three.module.js';", controls)

    def test_vendor_is_official_webgl_three_r160_and_controls_import_local_module(self):
        static = simulator_static_dir()
        three = (static / "vendor" / "three.module.js").read_text(encoding="utf-8")
        controls = (static / "vendor" / "OrbitControls.js").read_text(encoding="utf-8")
        self.assertIn("const REVISION = '160'", three)
        self.assertIn("class WebGLRenderer", three)
        self.assertIn("WebGLRenderingContext", three)
        self.assertIn("from './three.module.js';", controls)
        self.assertNotIn("Stage A vendor subset", three)

    def test_frontend_sets_z_up_camera_and_reports_missing_module_in_page(self):
        static = simulator_static_dir()
        html = (static / "index.html").read_text(encoding="utf-8")
        js = (static / "simulator.js").read_text(encoding="utf-8")
        self.assertIn("window.addEventListener('error'", html)
        self.assertIn("set(0, 0, 1)", js)
        self.assertIn("raycaster.params.Points.threshold", js)

    def test_frontend_builds_cached_canvas_hub_id_labels_and_toggles_them(self):
        js = (simulator_static_dir() / "simulator.js").read_text(encoding="utf-8")
        self.assertIn("function createTextSprite", js)
        self.assertIn("new THREE.CanvasTexture", js)
        self.assertIn("createHubLabel(hub)", js)
        self.assertIn("hub.id === 'H061'", js)
        self.assertIn("labels.visible = false", js)
        self.assertIn("setHubLabelsVisible", js)
        self.assertIn("setHubLabelsVisible(document.getElementById('show-labels').checked)", js)
        self.assertNotRegex(js, r"https?://|fonts\.googleapis")

    def test_frontend_exports_testable_helpers(self):
        js = (simulator_static_dir() / "simulator.js").read_text(encoding="utf-8")
        self.assertIn("export function stringColor", js)
        self.assertIn("export function validateLedIndex", js)
        self.assertIn("export function formatLedMetadata", js)

    def test_frontend_escapes_inspection_values_from_explicit_user_data(self):
        js = (simulator_static_dir() / "simulator.js").read_text(encoding="utf-8")
        self.assertIn("export function escapeHtml", js)
        self.assertIn("escapeHtml(led.spar_id", js)
        self.assertIn("escapeHtml(led.from_hub", js)
        self.assertIn("escapeHtml(led.to_hub", js)


class SimulatorCliTests(unittest.TestCase):
    def test_cli_help_and_argument_parsing(self):
        with self.assertRaises(SystemExit) as top:
            cli.parse_args(["simulator", "--help"])
        self.assertEqual(top.exception.code, 0)
        with self.assertRaises(SystemExit) as serve:
            cli.parse_args(["simulator", "serve", "--help"])
        self.assertEqual(serve.exception.code, 0)
        args = cli.parse_args(["simulator", "serve"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8080)
        self.assertFalse(args.open_browser)
        self.assertIsNone(args.routes)
        args = cli.parse_args(["simulator", "serve", "--host", "0.0.0.0", "--port", "18080", "--open-browser"])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 18080)
        self.assertTrue(args.open_browser)
        args = cli.parse_args(["simulator", "serve", "--routes", "custom_routes.json"])
        self.assertEqual(args.routes, "custom_routes.json")

    def test_invalid_paths_do_not_start_server(self):
        with patch("thunderdome.cli.serve_simulator") as serve:
            result = cli.main(["simulator", "serve", "--geometry", "missing.json", "--no-open-browser"])
        self.assertEqual(result, 1)
        serve.assert_not_called()

    def test_missing_routes_path_does_not_start_server(self):
        with patch("thunderdome.cli.serve_simulator") as serve:
            result = cli.main(["simulator", "serve", "--routes", "missing-routes.json", "--no-open-browser"])
        self.assertEqual(result, 1)
        serve.assert_not_called()


class SimulatorHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_http_server("127.0.0.1", 0, GEOMETRY_PATH, REFERENCE_ROUTE_PATH, LED_POSITIONS_PATH)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def fetch(self, path: str):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return response.headers["Content-Type"], response.read()

    def test_static_and_api_endpoints(self):
        content_type, body = self.fetch("/")
        self.assertIn("text/html", content_type)
        self.assertIn(b"Thunderdome Simulator", body)
        for path in ["/simulator.css", "/simulator.js", "/vendor/three.module.js", "/vendor/OrbitControls.js"]:
            content_type, body = self.fetch(path)
            self.assertGreater(len(body), 100)
            self.assertNotIn("text/plain", content_type)

        content_type, body = self.fetch("/api/simulator/metadata")
        self.assertIn("application/json", content_type)
        metadata = json.loads(body)
        self.assertEqual(metadata["total_led_count"], 5000)
        self.assertEqual(metadata["route_count"], 5)
        self.assertEqual(metadata["routes_source_filename"], REFERENCE_ROUTE_PATH.name)
        content_type, body = self.fetch("/api/simulator/geometry")
        self.assertIn("application/json", content_type)
        self.assertEqual(len(json.loads(body)["hubs"]), 61)
        content_type, body = self.fetch("/api/simulator/leds")
        self.assertIn("application/json", content_type)
        leds = json.loads(body)["leds"]
        self.assertEqual(len(leds), 5000)
        self.assertEqual([led["global_index"] for led in leds], list(range(5000)))

    def test_rejects_directory_traversal_and_unknown_api(self):
        for path in ["/../pyproject.toml", "/api/simulator/nope"]:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError):
                self.fetch(path)


if __name__ == "__main__":
    unittest.main()
