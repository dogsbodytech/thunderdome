import json
import tempfile
import unittest
from pathlib import Path

from thunderdome.effect_defaults import EffectDefaults


class EffectDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "effect-defaults.json"
        self.defaults = EffectDefaults(self.path)

    def tearDown(self): self.directory.cleanup()

    def test_missing_file_uses_builtins_and_first_save_is_atomic(self):
        self.assertEqual(self.defaults.resolved("aurora")["speed"], .25)
        self.defaults.save("aurora", {"speed": .5})
        self.assertTrue(self.path.exists()); self.assertFalse(self.path.with_suffix(".json.tmp").exists())
        self.assertEqual(self.defaults.resolved("aurora")["speed"], .5)

    def test_save_preserves_other_effects_and_delete_restores_builtin(self):
        self.defaults.save("aurora", {"speed": .5}); self.defaults.save("fire", {"speed": 2.0})
        self.assertEqual(self.defaults.resolved("aurora")["speed"], .5)
        self.defaults.delete("aurora")
        self.assertEqual(self.defaults.resolved("aurora")["speed"], .25)
        self.assertEqual(self.defaults.resolved("fire")["speed"], 2.0)

    def test_invalid_data_is_rejected(self):
        with self.assertRaises(ValueError): self.defaults.save("missing", {})
        with self.assertRaises(ValueError): self.defaults.save("aurora", {"unknown": 1})
        with self.assertRaises(ValueError): self.defaults.save("aurora", {"speed": 0})
        self.path.write_text("{")
        with self.assertRaises(ValueError): self.defaults.saved("aurora")


if __name__ == "__main__": unittest.main()
