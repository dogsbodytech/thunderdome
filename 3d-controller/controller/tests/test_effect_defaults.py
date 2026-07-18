import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import cast

from aiohttp import web

from thunderdome.control import ControlAPI, ControlSettings, make_effect_producer
from thunderdome.effect_defaults import EffectDefaults
from thunderdome.runtime import CommandSource, DisplayDefinition, OutputMode
from thunderdome.schemas import validate_effect_parameters


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

    def test_effect_catalogue_exposes_saved_and_resolved_defaults(self):
        self.defaults.save("aurora", {"speed": .5})
        api = ControlAPI(ControlSettings("ws://127.0.0.1:8080/ws/producer", effect_defaults_path=str(self.path)))
        response = asyncio.run(api.effects(cast(web.Request, None)))
        payload = json.loads(cast(bytes, response.body))
        aurora = next(effect for effect in payload["effects"] if effect["name"] == "aurora")
        self.assertEqual(aurora["saved_defaults"], {"speed": .5})
        self.assertEqual(aurora["resolved_defaults"]["speed"], .5)

    def test_auto_refreshes_saved_procedural_defaults_while_running(self):
        self.defaults.save("twinkle", {"density": 0, "background": "100000"})
        parameters = validate_effect_parameters("auto", {"effects": ["twinkle"], "interval": 30, "transition": 0})
        display = DisplayDefinition("auto", parameters, OutputMode.NULL, CommandSource.BROWSER, "auto-defaults", time.monotonic())
        producer, _, _ = make_effect_producer(display, self.defaults)
        self.assertEqual(tuple(producer(0, .2).data[:3]), (16, 0, 0))
        self.defaults.save("twinkle", {"density": 0, "background": "001000"})
        self.assertEqual(tuple(producer(1, .4).data[:3]), (0, 16, 0))


if __name__ == "__main__": unittest.main()
