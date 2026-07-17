"""Contract tests for the deterministic Thunderdome 2D-to-3D mapping pipeline."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome_mapping import (  # noqa: E402
    GeometryError,
    apply_transform,
    build_graph,
    interpolate_xyz,
    load_geometry,
    match_point_to_spar,
    validate_positions,
    _transition_is_valid,
    infer,
)

PROJECT = ROOT
GEOMETRY = ROOT / "geometry/thunderdome_geometry.json"
POSITIONS = ROOT / "archive/wled-2d-map-experiment/data/wled_map_top_centre_tail_300_v4/led_positions_2d.json"


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = load_geometry(GEOMETRY)

    def test_loads_expected_hubs_spars_and_types(self):
        self.assertEqual(len(self.geometry.hubs), 61)
        self.assertEqual(len(self.geometry.spars), 165)
        self.assertEqual(
            {kind: sum(s.type == kind for s in self.geometry.spars) for kind in "ABC"},
            {"A": 30, "B": 55, "C": 80},
        )

    def test_spar_graph_is_connected(self):
        graph = build_graph(self.geometry)
        visited = {"H001"}
        frontier = ["H001"]
        while frontier:
            hub = frontier.pop()
            for next_hub, _spar in graph[hub]:
                if next_hub not in visited:
                    visited.add(next_hub)
                    frontier.append(next_hub)
        self.assertEqual(visited, set(self.geometry.hubs))

    def test_projection_transform_can_rotate_translate_scale_and_reflect(self):
        transformed = apply_transform((1.0, 2.0), scale=2.0, rotation_degrees=90.0, tx=10.0, ty=-3.0, reflect_y=True)
        self.assertAlmostEqual(transformed[0], 6.0)
        self.assertAlmostEqual(transformed[1], -5.0)

    def test_point_to_line_match_and_xyz_interpolation(self):
        spar = self.geometry.spars[0]
        start = self.geometry.hubs[spar.start_hub]
        end = self.geometry.hubs[spar.end_hub]
        midpoint = ((start.x + end.x) * 500.0, (start.y + end.y) * 500.0)
        match = match_point_to_spar(midpoint, spar, self.geometry.hubs, scale=1000.0)
        self.assertAlmostEqual(match.fraction, 0.5, places=6)
        self.assertAlmostEqual(match.distance, 0.0, places=6)
        xyz = interpolate_xyz(start, end, 0.5)
        self.assertAlmostEqual(xyz[0], (start.x + end.x) / 2.0)
        self.assertAlmostEqual(xyz[2], (start.z + end.z) / 2.0)

    def test_schema_preserves_five_thousand_indexes_and_explicit_tail(self):
        positions = validate_positions(json.loads(POSITIONS.read_text()))
        self.assertEqual(len(positions), 5000)
        self.assertEqual([p.global_index for p in positions], list(range(5000)))
        self.assertEqual(sum(not p.on_dome_path for p in positions), 335)
        self.assertEqual({p.string_id for p in positions}, {0, 1, 2, 3, 4})

    def test_continuity_allows_shared_hub_transition_and_rejects_unshared_jump(self):
        spar_by_id = {spar.id: spar for spar in self.geometry.spars}
        first = self.geometry.spars[0]
        connected = next(s for s in self.geometry.spars if s.id != first.id and {first.start_hub, first.end_hub} & {s.start_hub, s.end_hub})
        shared = ({first.start_hub, first.end_hub} & {connected.start_hub, connected.end_hub}).pop()
        first_t = 0.0 if first.start_hub == shared else 1.0
        connected_t = 0.0 if connected.start_hub == shared else 1.0
        previous = {"spar_id": first.id, "fraction_along_spar": first_t}
        current = {"spar_id": connected.id, "fraction_along_spar": connected_t}
        self.assertTrue(_transition_is_valid(previous, current, spar_by_id, self.geometry.hubs))
        disconnected = next(s for s in self.geometry.spars if not ({first.start_hub, first.end_hub} & {s.start_hub, s.end_hub}))
        self.assertFalse(_transition_is_valid(previous, {"spar_id": disconnected.id, "fraction_along_spar": 0.0}, spar_by_id, self.geometry.hubs))

    def test_inference_is_deterministic_and_keeps_all_records(self):
        summary, positions = __import__("thunderdome_mapping").load_positions(POSITIONS)
        first = infer(self.geometry, positions, summary)
        second = infer(self.geometry, positions, summary)
        self.assertEqual(json.dumps(first[0], sort_keys=True), json.dumps(second[0], sort_keys=True))
        self.assertEqual(json.dumps(first[1], sort_keys=True), json.dumps(second[1], sort_keys=True))
        self.assertEqual(len(first[1]["leds"]), 5000)
        self.assertTrue(all(row["location_type"] in {"spar", "tail", "unresolved"} for row in first[1]["leds"]))

    def test_invalid_position_indexes_fail_usefully(self):
        with self.assertRaises(GeometryError):
            validate_positions({"positions": [{"physical_index": 1}]})


if __name__ == "__main__":
    unittest.main()
