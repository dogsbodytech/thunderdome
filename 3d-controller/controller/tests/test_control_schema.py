import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.effects.registry import BY_NAME
from thunderdome.schemas import EFFECT_SCHEMAS, validate_effect_parameters


class EffectSchemaTests(unittest.TestCase):
    def test_every_registered_effect_and_auto_has_a_json_serializable_schema(self):
        self.assertEqual(set(EFFECT_SCHEMAS), set(BY_NAME) | {"auto"})
        json.dumps({name: schema.as_dict() for name, schema in EFFECT_SCHEMAS.items()})

    def test_brightness_defaults_to_full_scale(self):
        for schema in EFFECT_SCHEMAS.values():
            brightness = schema.parameters["brightness"]
            self.assertEqual(brightness.default, 255)
            self.assertEqual(brightness.maximum, 255)

    def test_validation_rejects_unknown_and_out_of_range_parameters(self):
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            validate_effect_parameters("fire", {"bogus": 1})
        with self.assertRaisesRegex(ValueError, "brightness"):
            validate_effect_parameters("fire", {"brightness": 256})
        with self.assertRaisesRegex(ValueError, "choice"):
            validate_effect_parameters("height-wave", {"direction": "sideways"})

    def test_auto_validates_an_ordered_effect_list(self):
        values = validate_effect_parameters("auto", {"effects": ["fire", "aurora"], "brightness": 255})
        self.assertEqual(values["effects"], ["fire", "aurora"])
        with self.assertRaisesRegex(ValueError, "unknown effect"):
            validate_effect_parameters("auto", {"effects": ["missing"]})


if __name__ == "__main__":
    unittest.main()
