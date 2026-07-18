from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.effects.Common import SpatialContext, parse_spatial_origin
from thunderdome.effects.ExpandingRings import render_expanding_rings
from thunderdome.effects.HeightWave import render_height_wave


COUNT = 5_000


def rows() -> list[dict[str, object]]:
    records = [
        {"global_index": 0, "x": 1.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 1, "x": 1.0, "y": 0.0, "z": 2.0, "location_type": "spar"},
        {"global_index": 2, "x": 0.0, "y": 0.0, "z": -1.0, "location_type": "spar"},
        {"global_index": 3, "x": 0.0, "y": 0.0, "z": 3.0, "location_type": "spar"},
        {"global_index": 4, "x": 1.0, "y": 0.0, "z": 0.0, "location_type": "tail"},
    ]
    records.extend(
        {"global_index": index, "x": 0.0, "y": 0.0, "z": -5.0, "location_type": "tail"}
        for index in range(len(records), COUNT)
    )
    return records


class SpatialEffectCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = SpatialContext.from_rows(rows(), center=(0.0, 0.0, 3.0))

    def pixel(self, frame, index: int) -> tuple[int, int, int]:
        start = index * 3
        return tuple(frame.data[start : start + 3])

    def test_expanding_shell_uses_xyz_not_xy_and_is_exactly_15000_bytes(self):
        frame = render_expanding_rings(
            self.context, elapsed_seconds=1.0, speed_m_per_s=1.0, thickness_m=0.2,
            origin=(0.0, 0.0, 0.0), color=(255, 0, 0), brightness=255,
        )
        self.assertEqual(self.pixel(frame, 0), (255, 0, 0))
        self.assertEqual(self.pixel(frame, 1), (0, 0, 0))
        self.assertEqual(len(frame.data), 15_000)

    def test_shell_wraps_at_selected_maximum_distance_and_tails_are_opt_out(self):
        included = render_expanding_rings(
            self.context, elapsed_seconds=1.0, speed_m_per_s=1.0, thickness_m=0.2,
            origin=(0.0, 0.0, 0.0), color=(255, 0, 0), brightness=255,
        )
        excluded = render_expanding_rings(
            self.context, elapsed_seconds=1.0, speed_m_per_s=1.0, thickness_m=0.2,
            origin=(0.0, 0.0, 0.0), color=(255, 0, 0), brightness=255, exclude_tail=True,
        )
        wrapped = render_expanding_rings(
            self.context, elapsed_seconds=6.0, speed_m_per_s=1.0, thickness_m=0.2,
            origin=(0.0, 0.0, 0.0), color=(255, 0, 0), brightness=255,
        )
        self.assertEqual(self.pixel(included, 4), (255, 0, 0))
        self.assertEqual(self.pixel(excluded, 4), (0, 0, 0))
        self.assertEqual(included.data, wrapped.data)

    def test_origin_parser_supports_apex_centre_base_and_explicit_coordinates(self):
        self.assertEqual(parse_spatial_origin("apex", self.context), (0.0, 0.0, 3.0))
        self.assertEqual(parse_spatial_origin("centre", self.context), (0.0, 0.0, 1.0))
        self.assertEqual(parse_spatial_origin("base", self.context), (0.0, 0.0, -1.0))
        self.assertEqual(parse_spatial_origin("0.5,1.0,1.5", self.context), (0.5, 1.0, 1.5))
        for value in ("0,1", "x,1,2", "0,1,nan"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, value):
                parse_spatial_origin(value, self.context)

    def test_height_wave_up_down_bounce_and_tail_bounds(self):
        common = dict(speed_m_per_s=1.0, height_m=0.2, color=(0, 255, 0), brightness=255, exclude_tail=True)
        up = render_height_wave(self.context, elapsed_seconds=0.0, direction="up", **common)
        up_later = render_height_wave(self.context, elapsed_seconds=1.0, direction="up", **common)
        down = render_height_wave(self.context, elapsed_seconds=0.0, direction="down", **common)
        bounce_out = render_height_wave(self.context, elapsed_seconds=3.0, direction="bounce", **common)
        bounce_back = render_height_wave(self.context, elapsed_seconds=5.0, direction="bounce", **common)
        self.assertEqual(self.pixel(up, 2), (0, 255, 0))
        self.assertEqual(self.pixel(up_later, 0), (0, 255, 0))
        self.assertEqual(self.pixel(down, 3), (0, 255, 0))
        self.assertEqual(self.pixel(bounce_out, 1), (0, 255, 0))
        self.assertEqual(self.pixel(bounce_back, 1), (0, 255, 0))
        self.assertEqual(len(up.data), 15_000)
        flat_rows = [
            {"global_index": index, "x": 0.0, "y": 0.0, "z": 0.0, "location_type": "spar"}
            for index in range(COUNT)
        ]
        flat = SpatialContext.from_rows(flat_rows, center=(0.0, 0.0, 0.0))
        with self.assertRaisesRegex(ValueError, "selected Z bounds"):
            render_height_wave(flat, elapsed_seconds=0, direction="up", speed_m_per_s=1, height_m=1)


if __name__ == "__main__":
    unittest.main()
