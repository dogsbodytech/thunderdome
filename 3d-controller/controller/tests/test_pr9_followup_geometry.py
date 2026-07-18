from __future__ import annotations

import math
import io
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome import cli
from thunderdome.effects.common import SpatialContext
from thunderdome.effects.procedural import (
    build_rotating_plane_samples,
    finite_vector,
    plane_intensity_from_samples,
    render_rotating_plane,
    rotating_plane_intensity,
    rotating_plane_normal,
    rotate_vector,
)
from thunderdome.frame import RGBFrame

ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS = ROOT / "config" / "controllers.example.json"


def tiny_context() -> SpatialContext:
    points = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
        (0.7, 0.7, 0.0),
        (-0.7, 0.7, 0.0),
        (0.7, -0.7, 0.0),
    ]
    rows = []
    for index in range(5000):
        x, y, z = points[index % len(points)]
        rows.append({"global_index": index, "x": x, "y": y, "z": z, "location_type": "spar"})
    return SpatialContext.from_rows(rows, center=(0.0, 0.0, 0.0), apex=(0.0, 0.0, 1.0))


class FakeStats:
    frames_sent = 1
    elapsed_seconds = 0.0
    interrupted = False


def fake_loop(producer, sender, **_kwargs):
    frame = producer(0, 0.0)
    assert isinstance(frame, RGBFrame)
    assert len(frame.data) == 15000
    sender(frame)
    return FakeStats()


class AutoTimingFollowupTests(unittest.TestCase):
    def test_incoming_elapsed_is_monotonic_across_transition_boundary(self):
        names = ["fire", "aurora", "fireflies"]
        samples = [0.299, 0.300, 0.350, 0.399, 0.400, 0.401]
        calls_by_sample = {}

        def renderer(name, elapsed):
            calls_by_sample.setdefault(current[0], []).append((name, elapsed))
            return RGBFrame.allocate(5000, (100 if name == "fire" else 200 if name == "aurora" else 50, 0, 0))

        current = [0.0]
        for sample in samples:
            current[0] = sample
            cli._auto_frame_for_elapsed(names, renderer, elapsed=sample, interval=0.4, transition=0.1, brightness=24)

        self.assertEqual(calls_by_sample[0.299], [("fire", 0.299)])
        self.assertAlmostEqual(calls_by_sample[0.300][1][1], 0.0, places=6)
        self.assertAlmostEqual(calls_by_sample[0.350][1][1], 0.050, places=6)
        self.assertAlmostEqual(calls_by_sample[0.399][1][1], 0.099, places=6)
        self.assertEqual(calls_by_sample[0.400][0][0], "aurora")
        self.assertAlmostEqual(calls_by_sample[0.400][0][1], 0.100, places=6)
        self.assertAlmostEqual(calls_by_sample[0.401][0][1], 0.101, places=6)
        incoming_times = [calls_by_sample[t][-1][1] for t in (0.300, 0.350, 0.399, 0.400, 0.401)]
        self.assertEqual(incoming_times, sorted(incoming_times))

    def test_zero_transition_and_playlist_wrap_have_expected_starts(self):
        names = ["fire", "aurora", "fireflies"]
        calls = []

        def renderer(name, elapsed):
            calls.append((name, round(elapsed, 3)))
            return RGBFrame.allocate(5000, (1, 0, 0))

        cli._auto_frame_for_elapsed(names, renderer, elapsed=0.0, interval=0.4, transition=0.1, brightness=255)
        self.assertEqual(calls[-1], ("fire", 0.0))
        cli._auto_frame_for_elapsed(names, renderer, elapsed=0.4, interval=0.4, transition=0.0, brightness=255)
        self.assertEqual(calls[-1], ("aurora", 0.0))
        cli._auto_frame_for_elapsed(names, renderer, elapsed=1.2, interval=0.4, transition=0.1, brightness=255)
        self.assertEqual(calls[-1], ("fire", 0.1))
        cli._auto_frame_for_elapsed(names, renderer, elapsed=1.6, interval=0.4, transition=0.1, brightness=255)
        self.assertEqual(calls[-1], ("aurora", 0.1))


class RotatingPlaneGeometryFollowupTests(unittest.TestCase):
    def setUp(self):
        self.ctx = tiny_context()

    def test_named_axes_and_explicit_axis_validation(self):
        self.assertEqual(finite_vector("vertical", allow_named_axis=True), (0.0, 0.0, 1.0))
        self.assertEqual(finite_vector("horizontal", allow_named_axis=True), (1.0, 0.0, 0.0))
        tilted = finite_vector("tilted", allow_named_axis=True)
        self.assertTrue(all(math.isclose(component, 1 / math.sqrt(3), rel_tol=1e-9) for component in tilted))
        self.assertEqual(finite_vector("1,0,0", allow_named_axis=True), (1.0, 0.0, 0.0))
        for bad in ("0,0,0", "bad", "1,2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                finite_vector(bad, allow_named_axis=True)

    def test_rodrigues_rotation_uses_all_axis_components_and_wraps(self):
        nx = rotating_plane_normal("1,0,0", elapsed=0.125, rotation_seconds=1.0, direction="clockwise")
        ny = rotating_plane_normal("0,1,0", elapsed=0.125, rotation_seconds=1.0, direction="clockwise")
        nz = rotating_plane_normal("0,0,1", elapsed=0.125, rotation_seconds=1.0, direction="clockwise")
        self.assertNotEqual(tuple(round(v, 6) for v in nx), tuple(round(v, 6) for v in ny))
        self.assertNotEqual(tuple(round(v, 6) for v in nx), tuple(round(v, 6) for v in nz))
        initial = rotating_plane_normal("tilted", elapsed=0.0, rotation_seconds=2.0, direction="clockwise")
        full = rotating_plane_normal("tilted", elapsed=2.0, rotation_seconds=2.0, direction="clockwise")
        for a, b in zip(initial, full):
            self.assertAlmostEqual(a, b, places=6)
        cw = rotating_plane_normal("tilted", elapsed=0.5, rotation_seconds=2.0, direction="clockwise")
        ccw = rotating_plane_normal("tilted", elapsed=0.5, rotation_seconds=2.0, direction="counterclockwise")
        self.assertNotEqual(tuple(round(v, 6) for v in cw), tuple(round(v, 6) for v in ccw))

    def test_axis_and_trail_change_rendered_output_and_keep_frame_shape(self):
        x_axis = render_rotating_plane(self.ctx, 0.125, brightness=255, axis="1,0,0", rotation_seconds=1.0, thickness_mm=200, trail_degrees=0)
        y_axis = render_rotating_plane(self.ctx, 0.125, brightness=255, axis="0,1,0", rotation_seconds=1.0, thickness_mm=200, trail_degrees=0)
        z_axis = render_rotating_plane(self.ctx, 0.125, brightness=255, axis="0,0,1", rotation_seconds=1.0, thickness_mm=200, trail_degrees=0)
        self.assertEqual(len(x_axis.data), 15000)
        self.assertNotEqual(bytes(x_axis.data), bytes(y_axis.data))
        self.assertNotEqual(bytes(x_axis.data), bytes(z_axis.data))
        no_trail = render_rotating_plane(self.ctx, 0.25, brightness=255, axis="0,0,1", rotation_seconds=1.0, thickness_mm=300, trail_degrees=0)
        with_trail = render_rotating_plane(self.ctx, 0.25, brightness=255, axis="0,0,1", rotation_seconds=1.0, thickness_mm=300, trail_degrees=60)
        self.assertNotEqual(bytes(no_trail.data), bytes(with_trail.data))
        self.assertTrue(all(0 <= byte <= 255 for byte in with_trail.data))

    def test_rotating_plane_builds_geometry_once_per_frame(self):
        with patch("thunderdome.effects.procedural.build_rotating_plane_samples", wraps=build_rotating_plane_samples) as builder, patch(
            "thunderdome.effects.procedural.plane_intensity_from_samples", wraps=plane_intensity_from_samples
        ) as intensity:
            render_rotating_plane(self.ctx, 0.25, brightness=255, axis="tilted", rotation_seconds=1.0, thickness_mm=200, trail_degrees=45)

        builder.assert_called_once()
        self.assertEqual(intensity.call_count, len(self.ctx.xyz))
        sample_arg = intensity.call_args_list[0].args[2]
        self.assertTrue(all(call.args[2] is sample_arg for call in intensity.call_args_list))

    def test_rotation_helper_calls_are_sample_bounded_not_led_bounded(self):
        with patch("thunderdome.effects.procedural.rotate_vector", wraps=rotate_vector) as rotate:
            render_rotating_plane(self.ctx, 0.25, brightness=255, axis="tilted", rotation_seconds=1.0, thickness_mm=200, trail_degrees=180)
        self.assertLessEqual(rotate.call_count, 13)
        self.assertLess(rotate.call_count, len(self.ctx.xyz) // 100)

    def test_sample_builder_counts_and_weights_are_bounded(self):
        only_main = build_rotating_plane_samples(axis="tilted", elapsed=0.0, rotation_seconds=1.0, trail_degrees=0, direction="clockwise")
        small = build_rotating_plane_samples(axis="tilted", elapsed=0.0, rotation_seconds=1.0, trail_degrees=5, direction="clockwise")
        full = build_rotating_plane_samples(axis="tilted", elapsed=0.0, rotation_seconds=1.0, trail_degrees=180, direction="clockwise")

        self.assertEqual(len(only_main), 1)
        self.assertGreater(len(small), 1)
        self.assertLessEqual(len(full), 13)
        self.assertEqual(full[0].weight, 1.0)
        weights = [sample.weight for sample in full]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertAlmostEqual(weights[-1], 0.0, places=6)

    def test_trail_is_behind_directional_and_fades(self):
        axis = "0,0,1"
        kwargs = dict(axis=axis, elapsed=0.25, rotation_seconds=1.0, thickness_m=0.05)
        behind_near = (0.5, -0.8660254038, 0.0)
        behind_far = (0.8660254038, -0.5, 0.0)
        ahead = (0.5, 0.8660254038, 0.0)
        no_trail = rotating_plane_intensity(behind_near, (0, 0, 0), trail_degrees=0, direction="clockwise", **kwargs)
        near = rotating_plane_intensity(behind_near, (0, 0, 0), trail_degrees=80, direction="clockwise", **kwargs)
        far = rotating_plane_intensity(behind_far, (0, 0, 0), trail_degrees=120, direction="clockwise", **kwargs)
        ahead_level = rotating_plane_intensity(ahead, (0, 0, 0), trail_degrees=80, direction="clockwise", **kwargs)
        opposite = rotating_plane_intensity(ahead, (0, 0, 0), trail_degrees=80, direction="counterclockwise", **kwargs)
        self.assertEqual(no_trail, 0.0)
        self.assertGreater(near, 0.0)
        self.assertGreater(near, far)
        self.assertEqual(ahead_level, 0.0)
        self.assertGreater(opposite, 0.0)

    def test_registry_auto_trail_degrees_has_visible_effect(self):
        no_trail = render_rotating_plane(self.ctx, 0.25, brightness=255, axis="tilted", rotation_seconds=10, thickness_mm=220, trail_degrees=0)
        preset_trail = render_rotating_plane(self.ctx, 0.25, brightness=255, axis="tilted", rotation_seconds=10, thickness_mm=220, trail_degrees=20)
        self.assertNotEqual(bytes(no_trail.data), bytes(preset_trail.data))

    def test_trail_validation_range_is_zero_through_180(self):
        render_rotating_plane(self.ctx, 0.0, brightness=255, trail_degrees=0)
        render_rotating_plane(self.ctx, 0.0, brightness=255, trail_degrees=180)
        for bad in (-0.1, 180.0001, 181):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "trail-degrees.*0..180"):
                build_rotating_plane_samples(axis="tilted", elapsed=0.0, rotation_seconds=1.0, trail_degrees=bad, direction="clockwise")


class ProceduralValidationFollowupTests(unittest.TestCase):
    def run_command(self, extra):
        with patch("thunderdome.cli.run_frame_loop", side_effect=fake_loop), patch("thunderdome.cli.run_wled_operation") as wled:
            result = cli.main(["effect", *extra, "--controllers", str(CONTROLLERS), "--duration", "0.2", "--fps", "5", "--dry-run"])
        wled.assert_not_called()
        return result

    def test_valid_zero_values_are_accepted_through_main(self):
        cases = [
            ["fire", "--turbulence", "0", "--cooling", "0"],
            ["rotating-plane", "--trail-degrees", "0"],
            ["radar", "--trail-degrees", "0", "--vertical-falloff", "0"],
            ["fireflies", "--color-variation", "0", "--count", "3"],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(self.run_command(args), 0)

    def test_invalid_negative_and_upper_bounds_fail_clearly(self):
        cases = [
            ["fire", "--turbulence", "-0.1"],
            ["fire", "--cooling", "1.1"],
            ["rotating-plane", "--trail-degrees", "-1"],
            ["rotating-plane", "--trail-degrees", "181"],
            ["radar", "--beam-width-degrees", "361"],
            ["fireflies", "--color-variation", "-0.1", "--count", "3"],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(self.run_command(args), 1)

    def test_real_main_trail_181_error_names_valid_range(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = self.run_command(["rotating-plane", "--trail-degrees", "181"])
        self.assertEqual(result, 1)
        self.assertIn("trail-degrees", stderr.getvalue())
        self.assertIn("181", stderr.getvalue())
        self.assertIn("0..180", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
