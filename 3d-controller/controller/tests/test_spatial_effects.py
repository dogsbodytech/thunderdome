from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.effects.common import SpatialContext
from thunderdome.effects.expanding_rings import render_expanding_rings
from thunderdome.effects.height_wave import render_height_wave


LOGICAL_LED_COUNT = 5_000


def rows() -> list[dict[str, object]]:
    """Full logical fixture with known radial, height, and tail LEDs."""
    fixture = [
        {"global_index": 0, "x": 0.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 1, "x": 1.0, "y": 0.0, "z": 0.5, "location_type": "spar"},
        {"global_index": 2, "x": 2.0, "y": 0.0, "z": 1.0, "location_type": "spar"},
        {"global_index": 3, "x": 0.0, "y": 0.0, "z": -1.0, "location_type": "tail"},
    ]
    fixture.extend(
        {"global_index": index, "x": 9.0, "y": 0.0, "z": 9.0, "location_type": "tail"}
        for index in range(4, LOGICAL_LED_COUNT)
    )
    return fixture


class SpatialEffectRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = SpatialContext.from_rows(rows(), center=(0.0, 0.0, 0.0))

    def test_context_derives_immutable_coordinates_and_bounds(self):
        self.assertEqual(self.context.radius_xy[:4], (0.0, 1.0, 2.0, 0.0))
        self.assertEqual(self.context.z_bounds, (-1.0, 9.0))
        self.assertEqual(self.context.tails[:4], (False, False, False, True))

    def test_expanding_ring_moves_outward_and_can_exclude_tails(self):
        frame = render_expanding_rings(
            self.context,
            elapsed_seconds=1.11803398875,
            speed_m_per_s=1.0,
            thickness_m=0.2,
            color=(255, 0, 0),
            brightness=255,
            exclude_tail=True,
        )
        self.assertEqual(tuple(frame.data[0:3]), (0, 0, 0))
        self.assertEqual(tuple(frame.data[3:6]), (255, 0, 0))
        self.assertEqual(tuple(frame.data[6:9]), (0, 0, 0))
        self.assertEqual(tuple(frame.data[9:12]), (0, 0, 0))

    def test_height_wave_moves_upward_through_z_and_honours_background(self):
        frame = render_height_wave(
            self.context,
            elapsed_seconds=0.5,
            speed_m_per_s=1.0,
            height_m=0.2,
            color=(0, 255, 0),
            background=(1, 2, 3),
            brightness=255,
            exclude_tail=True,
        )
        self.assertEqual(tuple(frame.data[0:3]), (1, 2, 3))
        self.assertEqual(tuple(frame.data[3:6]), (0, 255, 0))
        self.assertEqual(tuple(frame.data[6:9]), (1, 2, 3))
        self.assertEqual(tuple(frame.data[9:12]), (1, 2, 3))

    def test_effects_reject_nonpositive_spatial_parameters(self):
        with self.assertRaises(ValueError):
            render_expanding_rings(self.context, elapsed_seconds=0, speed_m_per_s=1, thickness_m=0)
        with self.assertRaises(ValueError):
            render_height_wave(self.context, elapsed_seconds=0, speed_m_per_s=1, height_m=0)
        with self.assertRaises(ValueError):
            render_expanding_rings(self.context, elapsed_seconds=0, speed_m_per_s=0, thickness_m=0.1)


if __name__ == "__main__":
    unittest.main()
