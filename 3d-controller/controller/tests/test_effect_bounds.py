"""Resource limits for the 5,000-LED procedural renderers."""
import unittest

from thunderdome.effects.Common import SpatialContext
from thunderdome.effects.Procedural import SPACE_BODIES, ParticleSystem, create_renderer, particle_templates, render_fireflies
from thunderdome.schemas import EFFECT_SCHEMAS, validate_effect_parameters


class EffectBoundsTests(unittest.TestCase):
    def test_renderer_domain_parameters_reject_pathological_finite_values(self):
        expected = {
            "Fire": {"speed": 100.0, "scale": 100.0},
            "Aurora": {"speed": 100.0, "scale": 100.0},
        }
        expected.update({name: {"speed": 100.0} for name in SPACE_BODIES})
        for effect, parameters in expected.items():
            for name, maximum in parameters.items():
                with self.subTest(effect=effect, name=name):
                    self.assertEqual(EFFECT_SCHEMAS[effect].parameters[name].maximum, maximum)
                    self.assertEqual(validate_effect_parameters(effect, {name: maximum})[name], maximum)
                    with self.assertRaises(ValueError):
                        validate_effect_parameters(effect, {name: 1e308})

    def test_large_seed_does_not_overflow_noise_arithmetic(self):
        import math
        from thunderdome.effects.procedural_math import _noise
        for seed in (10 ** 308, -(10 ** 308)):
            validated = validate_effect_parameters("Fire", {"seed": seed})
            first = _noise(1, 2, 3, 4, validated["seed"])
            self.assertTrue(math.isfinite(first))
            self.assertEqual(first, _noise(1, 2, 3, 4, seed))
            self.assertGreaterEqual(first, 0)
            self.assertLessEqual(first, 1)

    def test_extreme_finite_direction_vectors_normalize_without_overflow(self):
        import math
        from thunderdome.effects.procedural_math import finite_vector
        for vector in ([1e308, 1e308, 0], [1.7e308] * 3, [1e-308, 1e-308, 0]):
            validated = validate_effect_parameters("Aurora", {"direction": vector})
            normalized = finite_vector(validated["direction"])
            self.assertAlmostEqual(math.hypot(*normalized), 1)
            self.assertAlmostEqual(normalized[0], normalized[1])
            self.assertTrue(all(math.isfinite(component) for component in normalized))

    def test_oversized_integers_are_validation_errors_not_overflows(self):
        for effect, values in (
            ("Fireflies", {"count": 10 ** 400}),
            ("Fire", {"seed": 10 ** 400}),
            ("Twinkle", {"spawn_rate": 10 ** 400}),
            ("Aurora", {"direction": [10 ** 400, 0, 1]}),
        ):
            with self.subTest(effect=effect, values=values), self.assertRaises(ValueError):
                validate_effect_parameters(effect, values)

    def test_twinkle_spawn_rate_has_finite_led_scale_bound(self):
        self.assertEqual(EFFECT_SCHEMAS["Twinkle"].parameters["spawn_rate"].maximum, 5000)
        for rate in (0, 5000):
            self.assertEqual(validate_effect_parameters("Twinkle", {"spawn_rate": rate})["spawn_rate"], rate)
        for rate in (-1, 5001, 1e308, float("inf"), float("nan")):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                validate_effect_parameters("Twinkle", {"spawn_rate": rate})
            with self.subTest(direct_rate=rate), self.assertRaises(ValueError):
                create_renderer("Twinkle", None, spawn_rate=rate)

    def test_template_cache_is_small_lru_and_reuses_live_entries(self):
        particle_templates.cache_clear()
        self.addCleanup(particle_templates.cache_clear)
        first = particle_templates(100, 0)
        for seed in range(1, 16):
            particle_templates(100, seed)
        self.assertIs(first, particle_templates(100, 0))
        particle_templates(100, 16)
        self.assertEqual(particle_templates.cache_info().currsize, 16)
        self.assertIs(first, particle_templates(100, 0))
        misses = particle_templates.cache_info().misses
        particle_templates(100, 1)
        self.assertEqual(particle_templates.cache_info().misses, misses + 1)

    def test_firefly_count_is_bounded_at_schema_and_render_entry_points(self):
        context = SpatialContext.from_rows([
            {"global_index": i, "x": float(i % 5), "y": 0., "z": float(i % 3), "location_type": "spar"}
            for i in range(5000)
        ], center=(0, 0, 1), apex=(0, 0, 2))
        self.assertEqual(validate_effect_parameters("Fireflies", {"count": 100})["count"], 100)
        self.assertEqual(EFFECT_SCHEMAS["Fireflies"].parameters["count"].maximum, 100)
        for count in (0, 101):
            for operation in (
                lambda: validate_effect_parameters("Fireflies", {"count": count}),
                lambda: particle_templates(count, 1),
                lambda: ParticleSystem(count, 1, ((0, 0, 0), (1, 1, 1))),
                lambda: create_renderer("Fireflies", context, count=count),
                lambda: render_fireflies(context, 0, count=count),
            ):
                with self.subTest(count=count, operation=operation), self.assertRaises(ValueError):
                    operation()


if __name__ == "__main__":
    unittest.main()
