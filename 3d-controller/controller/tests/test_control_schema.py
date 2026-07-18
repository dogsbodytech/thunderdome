import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.effects.Registry import BY_NAME
from thunderdome.schemas import EFFECT_SCHEMAS, validate_effect_parameters


class EffectSchemaTests(unittest.TestCase):
    def test_every_registered_effect_and_auto_has_a_json_serializable_schema(self):
        self.assertEqual(set(EFFECT_SCHEMAS), set(BY_NAME) | {"Auto"})
        json.dumps({name: schema.as_dict() for name, schema in EFFECT_SCHEMAS.items()})

    def test_brightness_defaults_to_full_scale(self):
        for schema in EFFECT_SCHEMAS.values():
            brightness = schema.parameters["brightness"]
            self.assertEqual(brightness.default, 255)
            self.assertEqual(brightness.maximum, 255)

    def test_validation_rejects_unknown_and_out_of_range_parameters(self):
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            validate_effect_parameters("Fire", {"bogus": 1})
        with self.assertRaisesRegex(ValueError, "brightness"):
            validate_effect_parameters("Fire", {"brightness": 256})
        with self.assertRaisesRegex(ValueError, "choice"):
            validate_effect_parameters("HeightWave", {"direction": "sideways"})

    def test_auto_validates_an_ordered_effect_list(self):
        values = validate_effect_parameters("Auto", {"effects": ["Fire", "Aurora"], "brightness": 255})
        self.assertEqual(values["effects"], ["Fire", "Aurora"])
        with self.assertRaisesRegex(ValueError, "unknown effect"):
            validate_effect_parameters("Auto", {"effects": ["missing"]})


if __name__ == "__main__":
    unittest.main()
