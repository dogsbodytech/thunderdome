import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from thunderdome import cli
from thunderdome.cli import parse_args
from thunderdome.effect_defaults import EffectDefaults
from thunderdome.effects.common import SpatialContext
from thunderdome.effects.procedural import TwinkleOverlay, create_renderer, render
from thunderdome.effects.registry import BY_NAME, DEFAULT_PLAYLIST
from thunderdome.frame import RGBFrame
from thunderdome.schemas import EFFECT_SCHEMAS, validate_effect_parameters

COUNT = 5000


def rows():
    base = [
        {"global_index": 0, "x": 0.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 1, "x": 1.0, "y": 0.0, "z": 0.0, "location_type": "spar"},
        {"global_index": 2, "x": 0.0, "y": 1.0, "z": 1.0, "location_type": "spar"},
        {"global_index": 3, "x": -1.0, "y": 0.0, "z": 2.0, "location_type": "spar"},
    ]
    base.extend({"global_index": i, "x": 5.0, "y": 5.0, "z": 5.0, "location_type": "tail"} for i in range(4, COUNT))
    return base


def lit(frame):
    return [i for i in range(frame.led_count) if any(frame.data[i * 3 : i * 3 + 3])]


def px(frame, index):
    return tuple(frame.data[index * 3 : index * 3 + 3])


class TwinkleEffectTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SpatialContext.from_rows(rows(), center=(0, 0, 1), apex=(0, 0, 2))

    def renderer(self, **options):
        defaults = dict(density=.2, spawn_rate=40, fade_in=.5, hold=.2, fade_out=.6, color="FF8000")
        defaults.update(options)
        return create_renderer("twinkle", self.ctx, brightness=255, seed=7, **defaults)  # type: ignore[arg-type]

    def test_fixed_seed_determinism_and_pixel_count(self):
        a = self.renderer(); b = self.renderer()
        frames_a = [a.render(t).data for t in (0, .25, .5, .9)]
        frames_b = [b.render(t).data for t in (0, .25, .5, .9)]
        self.assertEqual(frames_a, frames_b)
        self.assertEqual(len(frames_a[-1]), COUNT * 3)
        self.assertTrue(all(0 <= value <= 255 for value in frames_a[-1]))

    def test_state_persists_and_fades_instead_of_flickering(self):
        renderer = self.renderer(minimum_brightness=.1, maximum_brightness=1)
        first = renderer.render(.25)
        index = lit(first)[0]
        second = renderer.render(.4)
        peak = renderer.render(.95)
        third = renderer.render(1.2)
        self.assertIn(index, lit(second))
        self.assertGreater(sum(px(second, index)), sum(px(first, index)))
        self.assertGreater(sum(px(peak, index)), sum(px(third, index)))

    def test_fixed_and_full_colour_modes(self):
        fixed = self.renderer(mode="fixed", color="00FF00").render(.25)
        random = self.renderer(mode="random", color_change_speed=2).render(.25)
        self.assertTrue(any(g > r and g > b for r, g, b in (px(fixed, i) for i in lit(fixed))))
        self.assertNotEqual({px(random, i) for i in lit(random)}, {px(fixed, i) for i in lit(fixed)})
        overlay = TwinkleOverlay(self.ctx, seed=7, density=.1, spawn_rate=20, mode="random", color_change_speed=2)
        base = RGBFrame.allocate(COUNT)
        first = overlay.apply(base, .2, brightness=255)
        index = next(iter(overlay.active))
        later = overlay.apply(base, .5, brightness=255)
        self.assertNotEqual(px(first, index), px(later, index))

    def test_background_and_overlay_helper(self):
        frame = self.renderer(background="000020", density=0, spawn_rate=0).render(.5)
        self.assertEqual(px(frame, 0), (0, 0, 32))
        overlay = TwinkleOverlay(self.ctx, seed=1, density=.1, spawn_rate=20, color="FFFFFF")
        base = RGBFrame.allocate(COUNT, (10, 0, 0))
        self.assertEqual(overlay.apply(base, .1, brightness=255, mode="brighten").led_count, COUNT)

    def test_validation_schema_registry_saved_defaults_and_auto(self):
        self.assertIn("twinkle", BY_NAME)
        self.assertIn("twinkle", DEFAULT_PLAYLIST)
        self.assertEqual(EFFECT_SCHEMAS["twinkle"].parameters["brightness"].default, 255)
        self.assertEqual(parse_args(["effect", "twinkle"]).brightness, 255)
        validated = validate_effect_parameters("twinkle", {"density": .1, "spawn_rate": 1, "mode": "random"})
        self.assertEqual(validated["mode"], "random")
        with self.assertRaises(ValueError):
            validate_effect_parameters("twinkle", {"density": 2})
        with tempfile.TemporaryDirectory() as directory:
            store = EffectDefaults(Path(directory) / "defaults.json")
            store.save("twinkle", {"density": .12, "mode": "random"})
            resolved = store.payload("twinkle")["resolved"]
            self.assertEqual(resolved["density"], .12)
            self.assertEqual(resolved["brightness"], 255)
        frame = BY_NAME["twinkle"].create_renderer(self.ctx, brightness=255, seed=3).render(.2)
        self.assertEqual(len(frame.data), COUNT * 3)

    def test_cli_auto_resolves_saved_twinkle_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EffectDefaults(root / "config" / "effect-defaults.json")
            store.save("twinkle", {"density": .12, "mode": "random"})
            renderer = Mock(render=lambda _elapsed: RGBFrame.allocate(COUNT))
            args = parse_args(["effect", "auto", "--effects", "twinkle", "--duration", ".2", "--dry-run"])
            with patch("thunderdome.cli.PROJECT_ROOT", root), patch("thunderdome.cli.SpatialContext.load", return_value=self.ctx), patch("thunderdome.effects.registry.create_renderer", return_value=renderer) as create, patch("thunderdome.cli._send_effect_frames", return_value=0):
                self.assertEqual(cli._run_auto(args), 0)
            self.assertEqual(create.call_args.kwargs["density"], .12)
            self.assertEqual(create.call_args.kwargs["mode"], "random")


if __name__ == "__main__":
    unittest.main()
