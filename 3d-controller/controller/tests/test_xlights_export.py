"""Tests for the xLights model export module."""
from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.geometry import load_geometry
from thunderdome.led_positions import generate_positions
from thunderdome.routes import load_routes
from thunderdome.xlights_export import (
    dome_to_xlights,
    generate_model_group,
    generate_polyline_model,
    segment_led_counts,
    update_xlights_rgbeffects,
)

ROOT = Path(__file__).resolve().parents[2]
GEOM = ROOT / "geometry" / "thunderdome_geometry.json"
ROUTE = ROOT / "geometry" / "reference_string_route.md"


class SegmentLedCountsTests(unittest.TestCase):
    def setUp(self):
        self.geometry = load_geometry(GEOM)
        self.routes = load_routes(ROUTE, self.geometry)

    def test_segment_led_counts_sum_to_n_spar(self):
        """Segment counts must sum to the same n_spar as generate_positions."""
        positions = generate_positions(self.routes, self.geometry)["leds"]
        for route in self.routes:
            counts = segment_led_counts(route.segments, route.total_length_m)
            n_spar_export = sum(counts)
            n_spar_positions = sum(
                1 for p in positions
                if p["string_id"] == route.string_id
                and p["location_type"] == "spar"
            )
            self.assertEqual(
                n_spar_export,
                n_spar_positions,
                msg=f"string {route.string_id}: n_spar mismatch",
            )
            self.assertLessEqual(n_spar_export, 1000)
            self.assertGreater(n_spar_export, 900, msg="expected most LEDs on spars")

    def test_segment_led_counts_matches_led_positions(self):
        """Per-segment counts must match actual LED positions from generate_positions."""
        positions = generate_positions(self.routes, self.geometry)["leds"]
        for route in self.routes:
            counts = segment_led_counts(route.segments, route.total_length_m)
            self.assertEqual(len(counts), len(route.segments))

            # Build expected per-segment counts from generate_positions
            spar_rows = [
                p for p in positions
                if p["string_id"] == route.string_id
                and p["location_type"] == "spar"
            ]
            expected: list[int] = [0] * len(route.segments)
            for row in spar_rows:
                spar_id = row["spar_id"]
                for idx, seg in enumerate(route.segments):
                    if seg.spar_id == spar_id:
                        expected[idx] += 1
                        break

            self.assertEqual(
                counts,
                expected,
                msg=f"string {route.string_id}: per-segment counts differ",
            )


class GeneratePolylineModelTests(unittest.TestCase):
    def setUp(self):
        self.geometry = load_geometry(GEOM)
        self.routes = load_routes(ROUTE, self.geometry)

    def test_generate_polyline_model_xml_is_valid(self):
        """generate_polyline_model returns a valid Element with correct attributes."""
        route = self.routes[0]
        elem = generate_polyline_model(route, self.geometry, start_channel=1)

        # Serialise and re-parse to confirm valid XML
        xml_str = ET.tostring(elem, encoding="unicode")
        reparsed = ET.fromstring(xml_str)

        self.assertEqual(reparsed.tag, "model")
        self.assertEqual(reparsed.get("DisplayAs"), "Poly Line")
        self.assertEqual(reparsed.get("NodesPerString"), "1000")
        self.assertEqual(reparsed.get("LightsPerNode"), "1")
        self.assertEqual(reparsed.get("PolyStrings"), "1")
        self.assertEqual(reparsed.get("NumPoints"), "26")  # 25 hubs + 1 tail
        self.assertEqual(reparsed.get("StartChannel"), "1")

        # Verify 25 segments are present
        seg_counts = [int(reparsed.get(f"Seg{i}", "0")) for i in range(1, 26)]
        self.assertEqual(sum(seg_counts), 1000)

        # Tail segment is the last one
        n_tail = seg_counts[-1]
        self.assertGreater(n_tail, 0)
        self.assertEqual(sum(seg_counts[:-1]) + n_tail, 1000)

        # All 25 corners should be "Neither"
        for i in range(1, 26):
            self.assertEqual(reparsed.get(f"Corner{i}"), "Neither")

        # PointData must have 26 × 3 = 78 comma-separated values
        point_data = reparsed.get("PointData", "")
        values = [v for v in point_data.split(",") if v]
        self.assertEqual(len(values), 78)

    def test_model_name_uses_controller_number(self):
        for route in self.routes:
            elem = generate_polyline_model(route, self.geometry, start_channel=1)
            self.assertEqual(
                elem.get("name"),
                f"Thunderdome String {route.controller_number}",
            )

    def test_start_channels_are_spaced_3000_apart(self):
        """Each string starts 3000 channels (1000 LEDs × 3 channels) after the previous."""
        expected_channels = {1: 1, 2: 3001, 3: 6001, 4: 9001, 5: 12001}
        for route in self.routes:
            elem = generate_polyline_model(
                route, self.geometry,
                start_channel=expected_channels[route.controller_number],
            )
            self.assertEqual(
                int(elem.get("StartChannel", "0")),
                expected_channels[route.controller_number],
            )


class UpdateXlightsRgbeffectsTests(unittest.TestCase):
    def setUp(self):
        self.geometry = load_geometry(GEOM)
        self.routes = load_routes(ROUTE, self.geometry)

    def test_creates_file_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "xlights_rgbeffects.xml"
            self.assertFalse(output.exists())
            update_xlights_rgbeffects(output, self.geometry, self.routes)
            self.assertTrue(output.exists())

    def test_output_is_valid_xml_with_five_models_and_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "xlights_rgbeffects.xml"
            update_xlights_rgbeffects(output, self.geometry, self.routes)
            tree = ET.parse(output)
            root = tree.getroot()
            models = root.find("models")
            self.assertIsNotNone(models)
            poly_models = [c for c in models if c.get("DisplayAs") == "Poly Line"]
            self.assertEqual(len(poly_models), 5)
            groups = root.find("modelGroups")
            self.assertIsNotNone(groups)
            td_group = groups.find("modelGroup[@name='Thunderdome']")
            self.assertIsNotNone(td_group)

    def test_idempotent_on_second_run(self):
        """Running twice should replace, not duplicate, the Thunderdome models."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "xlights_rgbeffects.xml"
            update_xlights_rgbeffects(output, self.geometry, self.routes)
            update_xlights_rgbeffects(output, self.geometry, self.routes)
            tree = ET.parse(output)
            root = tree.getroot()
            models = root.find("models")
            poly_models = [c for c in models if c.get("DisplayAs") == "Poly Line"]
            self.assertEqual(len(poly_models), 5)
            groups = root.find("modelGroups")
            td_groups = [c for c in groups if c.get("name") == "Thunderdome"]
            self.assertEqual(len(td_groups), 1)


class DomeToXlightsTests(unittest.TestCase):
    def test_z_up_maps_to_y_up(self):
        xl_x, xl_y, xl_z = dome_to_xlights(1.0, 0.0, 0.0)
        self.assertAlmostEqual(xl_x, 100.0)
        self.assertAlmostEqual(xl_y, 0.0)
        self.assertAlmostEqual(xl_z, 0.0)

        xl_x, xl_y, xl_z = dome_to_xlights(0.0, 0.0, 1.0)
        self.assertAlmostEqual(xl_x, 0.0)
        self.assertAlmostEqual(xl_y, 100.0)
        self.assertAlmostEqual(xl_z, 0.0)

        xl_x, xl_y, xl_z = dome_to_xlights(0.0, 1.0, 0.0)
        self.assertAlmostEqual(xl_x, 0.0)
        self.assertAlmostEqual(xl_y, 0.0)
        self.assertAlmostEqual(xl_z, 100.0)


if __name__ == "__main__":
    unittest.main()
