import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from thunderdome.control import ControlAPI, ControlSettings
from thunderdome.runtime import OutputMode


class FakeRuntime:
    def __init__(self):
        self.started = []
        self.frames = 0
        self.active_since = None
        self.error = None
        self.on_baseline_complete = None

    def start(self, display):
        self.started.append(display)

    def stop(self):
        pass

    def shutdown(self):
        pass


class CommandSourceTests(AioHTTPTestCase):
    async def get_application(self):
        settings = ControlSettings(simulator_url="http://127.0.0.1:1", default_output=OutputMode.NULL)
        self.api = ControlAPI(settings, runtime=FakeRuntime())
        app = web.Application()
        self.api.register_routes(app)
        return app

    async def asyncTearDown(self):
        self.api.shutdown()
        await super().asyncTearDown()

    async def test_source_defaults_to_browser(self):
        response = await self.client.post("/api/runtime/baseline", json={"effect": "Fire"})
        body = await response.json()
        self.assertEqual(response.status, 200)
        self.assertEqual(body["status"]["baseline"]["source"], "browser")

    async def test_declared_source_is_rejected(self):
        response = await self.client.post(
            "/api/runtime/override",
            json={"effect": "Fire", "source": "mqtt", "output": "null", "duration_seconds": 5},
        )
        body = await response.json()
        self.assertEqual(response.status, 400)
        self.assertFalse(body["accepted"])
        self.assertIn("source", body["error"])

    async def test_unknown_source_is_rejected(self):
        response = await self.client.post("/api/runtime/baseline", json={"effect": "Fire", "source": "wizard"})
        self.assertEqual(response.status, 400)
        self.assertFalse((await response.json())["accepted"])

    async def test_effect_schema_lookup_resolves_canonical_and_legacy_names(self):
        listing = await (await self.client.get("/api/effects")).json()
        self.assertIn("Fire", [effect["name"] for effect in listing["effects"]])
        self.assertNotIn("fire", [effect["name"] for effect in listing["effects"]])
        for canonical, legacy in (("Fire", "fire"), ("ClockHand", "clock-hand")):
            with self.subTest(canonical=canonical):
                canonical_response = await self.client.get(f"/api/effects/{canonical}")
                legacy_response = await self.client.get(f"/api/effects/{legacy}")
                self.assertEqual(canonical_response.status, 200)
                self.assertEqual(legacy_response.status, 200)
                self.assertEqual(await legacy_response.json(), await canonical_response.json())


if __name__ == "__main__":
    unittest.main()
