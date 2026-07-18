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
        response = await self.client.post("/api/runtime/baseline", json={"effect": "fire"})
        body = await response.json()
        self.assertEqual(response.status, 200)
        self.assertEqual(body["status"]["baseline"]["source"], "browser")

    async def test_declared_source_is_reported_in_status(self):
        response = await self.client.post(
            "/api/runtime/override",
            json={"effect": "fire", "source": "mqtt", "output": "null", "duration_seconds": 5},
        )
        body = await response.json()
        self.assertEqual(response.status, 200)
        self.assertEqual(body["status"]["override"]["source"], "mqtt")

    async def test_unknown_source_is_rejected(self):
        response = await self.client.post("/api/runtime/baseline", json={"effect": "fire", "source": "wizard"})
        self.assertEqual(response.status, 400)
        self.assertFalse((await response.json())["accepted"])


if __name__ == "__main__":
    unittest.main()
