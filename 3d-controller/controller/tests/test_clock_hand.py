from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.effects.ClockHand import angle_for_elapsed, render_clock_hand


LOGICAL_LED_COUNT = 5_000


def positions() -> list[dict[str, object]]:
    """A full logical fixture with a forward, opposite, side, and tail LED."""
    rows = [
        {"global_index": 0, "x": 1.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 1, "x": -1.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 2, "x": 0.0, "y": 1.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 3, "x": 0.0, "y": -1.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 4, "x": 0.0, "y": 0.0, "z": -1.0, "location_type": "tail"},
    ]
    rows.extend(
        {"global_index": index, "x": 0.0, "y": 0.0, "z": 0.0, "location_type": "tail"}
        for index in range(5, LOGICAL_LED_COUNT)
    )
    return rows


class ClockHandRendererTests(unittest.TestCase):
    def test_zero_angle_selects_forward_ray_not_opposite_or_tail(self):
        frame = render_clock_hand(
            positions(), angle_radians=0.0, width_m=0.3,
            color=(255, 0, 0), background=(1, 2, 3), brightness=128, center_xy=(0, 0),
        )
        self.assertEqual(frame.led_count, LOGICAL_LED_COUNT)
        self.assertEqual(tuple(frame.data[0:3]), (128, 0, 0))
        self.assertEqual(tuple(frame.data[3:6]), (0, 1, 1))
        self.assertEqual(tuple(frame.data[6:9]), (0, 1, 1))
        self.assertEqual(tuple(frame.data[12:15]), (128, 0, 0))

    def test_width_is_metres_and_tail_can_be_opted_in(self):
        rows = positions()
        narrow = render_clock_hand(rows, angle_radians=0.0, width_m=0.001, color=(255, 255, 255), center_xy=(0, 0))
        self.assertEqual(tuple(narrow.data[6:9]), (0, 0, 0))
        tail = render_clock_hand(rows, angle_radians=0.0, width_m=0.3, color=(255, 255, 255), center_xy=(0, 0))
        self.assertEqual(tuple(tail.data[12:15]), (32, 32, 32))

    def test_angle_direction_and_offset_are_deterministic(self):
        self.assertAlmostEqual(angle_for_elapsed(0.0, rotation_seconds=3, direction="clockwise", offset_degrees=0), 0.0)
        self.assertAlmostEqual(angle_for_elapsed(0.75, rotation_seconds=3, direction="clockwise", offset_degrees=0), -math.pi / 2)
        self.assertAlmostEqual(angle_for_elapsed(0.75, rotation_seconds=3, direction="counterclockwise", offset_degrees=0), math.pi / 2)
        self.assertAlmostEqual(angle_for_elapsed(0.0, rotation_seconds=3, direction="clockwise", offset_degrees=90), math.pi / 2)

    def test_different_angles_render_different_frames(self):
        rows = positions()
        east = render_clock_hand(rows, angle_radians=0.0, width_m=0.3, color=(255, 255, 255), center_xy=(0, 0))
        north = render_clock_hand(rows, angle_radians=math.pi / 2, width_m=0.3, color=(255, 255, 255), center_xy=(0, 0))
        self.assertNotEqual(east.data, north.data)


if __name__ == "__main__":
    unittest.main()
