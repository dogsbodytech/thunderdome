import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.cli import parse_args
from thunderdome.effects.Registry import BY_NAME
from thunderdome.schemas import EFFECT_SCHEMAS, validate_effect_parameters


EFFECT_NAMES = (
    "ClockHand",
    "ExpandingRings",
    "HeightWave",
    "Fire",
    "RotatingPlane",
    "Radar",
    "Aurora",
    "Fireflies",
    "Twinkle",
    "Auto",
)

SPACE_BODY_NAMES = (
    "AsteroidBelt",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "KuiperBelt",
    "Voyager1",
    "Sol",
    "Mercury",
    "Venus",
    "Earth",
    "Mars",
)


class EffectNameFormatTests(unittest.TestCase):
    def test_public_effect_identifiers_use_title_case_with_underscores(self):
        self.assertEqual(tuple(BY_NAME), EFFECT_NAMES[:-1] + SPACE_BODY_NAMES)
        self.assertEqual(tuple(EFFECT_SCHEMAS), EFFECT_NAMES + SPACE_BODY_NAMES)
        self.assertTrue(all("-" not in name for name in EFFECT_NAMES + SPACE_BODY_NAMES))

    def test_cli_and_schema_accept_title_case_effect_identifiers(self):
        self.assertEqual(parse_args(["effect", "ClockHand"]).command, "ClockHand")
        self.assertEqual(validate_effect_parameters("Twinkle", {"density": 0.1})["density"], 0.1)


if __name__ == "__main__":
    unittest.main()
