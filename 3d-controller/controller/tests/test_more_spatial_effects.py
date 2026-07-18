from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import main, parse_args
from thunderdome.effects.Common import SpatialContext
from thunderdome.effects.Procedural import (
    SPACE_BODIES, ParticleSystem, angular_delta, blend, finite_vector, palette_color, render,
    render_fire, render_fireflies, signed_plane_distance,
)
from thunderdome.effects.Registry import BY_NAME, REGISTRY
from thunderdome.frame import RGBFrame
from thunderdome.transport.multi_ddp import SendResult

ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS = ROOT / "config" / "controllers.example.json"
COUNT = 5000


def rows():
    base = [
        {"global_index": 0, "x": 0.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 1, "x": 1.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 2, "x": 0.0, "y": 1.0, "z": 1.0, "location_type": "spar"},
        {"global_index": 3, "x": -1.0, "y": 0.0, "z": 2.0, "location_type": "spar"},
        {"global_index": 4, "x": 0.0, "y": 0.0, "z": -1.0, "location_type": "tail"},
    ]
    base.extend({"global_index": i, "x": 5.0, "y": 5.0, "z": 5.0, "location_type": "tail"} for i in range(5, COUNT))
    return base


def px(frame, i):
    return tuple(frame.data[i * 3:i * 3 + 3])


class MoreSpatialEffectsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SpatialContext.from_rows(rows(), center=(0, 0, 1), apex=(0, 0, 2))

    def test_registry_has_unique_expected_auto_effects(self):
        names = [r.name for r in REGISTRY]
        self.assertEqual(names, ["ClockHand", "ExpandingRings", "HeightWave", "Fire", "RotatingPlane", "Radar", "Aurora", "Fireflies", "Twinkle",
                                 "asteroid-belt", "jupiter", "saturn", "uranus", "neptune", "kuiper-belt", "voyager-1", "sol", "mercury", "venus", "earth", "mars"])
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(BY_NAME[name].supports_auto and BY_NAME[name].auto_options for name in names))

    def test_space_bodies_render_representative_dominant_colours_and_animate(self):
        def avg(frame):
            data, n = frame.data, frame.led_count
            return tuple(sum(data[c::3]) / n for c in range(3))

        # every space_body renders a full 15k-byte frame; continuous styles animate.
        # (sparse "belt" styles can stay dark on this degenerate test geometry.)
        for name, space_body in SPACE_BODIES.items():
            a = render(name, self.ctx, 0.0, brightness=255, seed=3)
            b = render(name, self.ctx, 3.0, brightness=255, seed=3)
            self.assertEqual(len(a.data), 15000)
            if space_body.style != "belt":
                self.assertNotEqual(a.data, b.data, name)

        r, g, b = avg(render("sol", self.ctx, 1.0, brightness=255))
        self.assertGreater(r, 150); self.assertGreater(g, 120); self.assertLess(b, r)  # bright yellow
        r, g, b = avg(render("mars", self.ctx, 1.0, brightness=255))
        self.assertGreater(r, g); self.assertGreater(r, b)  # red dominant
        r, g, b = avg(render("earth", self.ctx, 1.0, brightness=255))
        self.assertGreater(b + g, r * 2)  # blue+green over red

    def test_fire_is_xyz_turbulent_seeded_time_varying_and_tail_aware(self):
        a = render_fire(self.ctx, 0, brightness=255, seed=7, flame_height_m=2.5)
        b = render_fire(self.ctx, 0.5, brightness=255, seed=7, flame_height_m=2.5)
        c = render_fire(self.ctx, 0, brightness=255, seed=8, flame_height_m=2.5)
        excluded = render_fire(self.ctx, 0, brightness=255, seed=7, exclude_tail=True)
        self.assertEqual(len(a.data), 15000)
        self.assertNotEqual(a.data, b.data)
        self.assertNotEqual(a.data, c.data)
        self.assertNotEqual(px(a, 0), px(a, 1))  # XY turbulence, not uniform Z gradient
        self.assertGreater(sum(px(a, 0)), sum(px(a, 3)))
        self.assertEqual(px(excluded, 4), (0, 0, 0))
        with self.assertRaises(ValueError):
            render_fire(self.ctx, 0, flame_height_m=0)
        self.assertTrue(all(0 <= v <= 255 for v in palette_color("inferno", 0.7)))

    def test_rotating_plane_distance_axis_direction_and_frame_size(self):
        self.assertAlmostEqual(signed_plane_distance((1, 0, 0), (0, 0, 0), (1, 0, 0)), 1)
        self.assertEqual(finite_vector("2,0,0", option="axis"), (1, 0, 0))
        with self.assertRaises(ValueError):
            finite_vector("0,0,0", option="axis")
        a = render("RotatingPlane", self.ctx, 0, brightness=255, axis="vertical", thickness_mm=3000, color="FF0000")
        b = render("RotatingPlane", self.ctx, 2.5, brightness=255, axis="vertical", rotation_seconds=10, thickness_mm=3000, color="FF0000")
        ccw = render("RotatingPlane", self.ctx, 1.25, brightness=255, axis="vertical", direction="counterclockwise", thickness_mm=3000, color="FF0000")
        self.assertEqual(len(a.data), 15000)
        self.assertNotEqual(a.data, b.data)
        self.assertNotEqual(b.data, ccw.data)

    def test_radar_wrap_trail_range_direction_and_size(self):
        self.assertAlmostEqual(abs(angular_delta(-3.13, 3.13)), 0.023185307179586445, places=2)
        a = render("Radar", self.ctx, 0, brightness=255, beam_width_degrees=30, trail_degrees=60, range_m=2, color="00FF00")
        far_limited = render("Radar", self.ctx, 0, brightness=255, beam_width_degrees=30, trail_degrees=60, range_m=0.1, color="00FF00")
        b = render("Radar", self.ctx, 1, brightness=255, direction="counterclockwise", color="00FF00")
        self.assertEqual(len(a.data), 15000)
        self.assertGreater(sum(px(a, 1)), sum(px(far_limited, 1)))
        self.assertNotEqual(a.data, b.data)

    def test_aurora_seed_direction_palette_and_time(self):
        a = render("Aurora", self.ctx, 0, brightness=255, seed=1, direction="1,0,0", palette="mixed")
        b = render("Aurora", self.ctx, 0.25, brightness=255, seed=1, direction="1,0,0", palette="mixed")
        c = render("Aurora", self.ctx, 0, brightness=255, seed=2, direction="1,0,0", palette="mixed")
        self.assertEqual(len(a.data), 15000)
        self.assertNotEqual(a.data, b.data)
        self.assertNotEqual(a.data, c.data)
        with self.assertRaises(ValueError):
            render("Aurora", self.ctx, 0, direction="0,0,0")

    def test_fireflies_particles_lifecycle_falloff_overlap_and_validation(self):
        bounds = ((-1, -1, -1), (1, 1, 1))
        system = ParticleSystem(3, 42, bounds, color="FFFFFF")
        p0 = system.particles(0, speed=1, lifetime_seconds=8)
        p1 = system.particles(1, speed=1, lifetime_seconds=8)
        self.assertNotEqual(p0[0].position, p1[0].position)
        self.assertNotEqual(p0[0].brightness, p1[0].brightness)
        frame = render_fireflies(self.ctx, 0, brightness=255, seed=42, count=5, glow_radius_mm=3000, color="FFFFFF")
        self.assertEqual(len(frame.data), 15000)
        self.assertTrue(all(0 <= value <= 255 for value in frame.data))
        with self.assertRaises(ValueError):
            render_fireflies(self.ctx, 0, count=0)
        with self.assertRaises(ValueError):
            system.particles(0, speed=0, lifetime_seconds=8)

    def test_blend_uses_one_frame_and_smooth_crossfade(self):
        a = RGBFrame.allocate(2, (100, 0, 0)); b = RGBFrame.allocate(2, (0, 100, 0))
        mid = blend(a, b, 0.5)
        self.assertEqual(tuple(mid.data[:3]), (50, 50, 0))


class AutoCliTests(unittest.TestCase):
    def test_auto_defaults_playlist_shuffle_and_validation(self):
        args = parse_args(["effect", "Auto"])
        self.assertEqual((args.interval, args.transition, args.brightness, args.fps), (30, 2, 32, 30))
        explicit = parse_args(["effect", "Auto", "--effects", "fire,aurora,fireflies", "--cycles", "1"])
        self.assertEqual(explicit.effects, "fire,aurora,fireflies")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(main(["effect", "Auto", "--effects", "fire,fire", "--dry-run", "--cycles", "1"]), 1)
        self.assertIn("duplicates", stderr.getvalue())

    def test_auto_dry_run_uses_one_context_one_session_no_http_and_reports_packets(self):
        stdout = io.StringIO()
        with patch("thunderdome.cli.run_wled_operation") as prepare:
            with contextlib.redirect_stdout(stdout):
                result = main([
                    "effect", "Auto", "--controllers", str(CONTROLLERS), "--effects", "fire,aurora,fireflies",
                    "--cycles", "1", "--interval", "1", "--transition", "0.2", "--fps", "5", "--dry-run",
                ])
        self.assertEqual(result, 0)
        prepare.assert_not_called()
        self.assertIn("Fire, Aurora, Fireflies", stdout.getvalue())
        self.assertIn("Output mode: null", stdout.getvalue())

    def test_new_effect_help_commands_parse(self):
        for name in ("Fire", "RotatingPlane", "Radar", "Aurora", "Fireflies", "Twinkle", "Auto"):
            with self.subTest(name=name), self.assertRaises(SystemExit) as ctx:
                parse_args(["effect", name, "--help"])
            self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
