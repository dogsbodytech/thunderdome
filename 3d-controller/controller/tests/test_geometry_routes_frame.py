from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thunderdome.frame import FrameError, RGBFrame
from thunderdome.geometry import GeometryError, load_geometry
from thunderdome.routes import RouteDefinition, RouteError, validate_routes

GEOMETRY = ROOT.parent / "geometry" / "thunderdome_geometry.json"


class GeometryAndRouteTests(unittest.TestCase):
    def test_loads_authoritative_geometry_and_connected_graph(self):
        geometry = load_geometry(GEOMETRY)
        self.assertEqual(len(geometry.hubs), 61)
        self.assertEqual(len(geometry.spars), 165)
        self.assertEqual(geometry.hubs["H061"].xyz, (0.0, 0.0, 3.532091))
        self.assertEqual(geometry.spar_type_counts, {"A": 30, "B": 55, "C": 80})
        self.assertTrue(geometry.is_connected())

    def test_route_accepts_real_edges_and_rejects_missing_edges(self):
        geometry = load_geometry(GEOMETRY)
        route = RouteDefinition(string_id=0, hubs=("H032", "H019", "H018"), rotation_degrees=0.0)
        validate_routes(geometry, [route])
        with self.assertRaises(RouteError):
            validate_routes(geometry, [RouteDefinition(string_id=0, hubs=("H001", "H061"), rotation_degrees=0.0)])

    def test_routes_reject_shared_spars_between_strings(self):
        geometry = load_geometry(GEOMETRY)
        with self.assertRaises(RouteError):
            validate_routes(geometry, [
                RouteDefinition(string_id=0, hubs=("H032", "H019"), rotation_degrees=0.0),
                RouteDefinition(string_id=1, hubs=("H032", "H019"), rotation_degrees=72.0),
            ])


class FrameTests(unittest.TestCase):
    def test_frame_allocates_5000_rgb_pixels_and_scales(self):
        frame = RGBFrame.allocate()
        self.assertEqual(len(frame.data), 15000)
        frame.set_pixel(3, (255, 128, 1))
        frame.set_range(4, 2, (1, 2, 3))
        frame.apply_brightness(128)
        self.assertEqual(frame.data[9:12], bytes((128, 64, 0)))
        self.assertEqual(frame.data[12:18], bytes((0, 1, 1, 0, 1, 1)))

    def test_frame_rejects_invalid_rgb_and_range(self):
        frame = RGBFrame.allocate(2)
        with self.assertRaises(FrameError):
            frame.set_pixel(0, (256, 0, 0))
        with self.assertRaises(FrameError):
            frame.set_range(1, 2, (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
