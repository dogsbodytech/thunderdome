"""Unit tests for the MQTT -> thunderdome bridge.

Run from this directory with:
    .venv/bin/python -m unittest discover
"""
import contextlib
import io
import json
import unittest
from unittest import mock

import mqtt_client


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FakeMessage:
    def __init__(self, payload, topic="open/dogsbody/thunderdome/effect"):
        self.payload = payload if isinstance(payload, bytes) else payload.encode()
        self.topic = topic


def quiet():
    return contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())


class OverridePayloadTests(unittest.TestCase):
    def test_payload_carries_effect_source_and_bounded_duration(self):
        with mock.patch.object(mqtt_client, "OUTPUT", None), mock.patch.object(mqtt_client, "DURATION_SECONDS", 120.0):
            payload = mqtt_client.override_payload("fire")
        self.assertEqual(payload, {"effect": "fire", "source": "mqtt", "duration_seconds": 120.0})

    def test_output_is_forwarded_only_when_forced(self):
        # Payload is a JSON body, not argv, so an odd name can't inject flags; the
        # control service validates the effect name and returns 400 for unknown ones.
        with mock.patch.object(mqtt_client, "OUTPUT", "simulator"):
            self.assertEqual(mqtt_client.override_payload("fire")["output"], "simulator")
        with mock.patch.object(mqtt_client, "OUTPUT", None):
            self.assertNotIn("output", mqtt_client.override_payload("fire"))


class RunEffectTests(unittest.TestCase):
    def post(self, body, name="fire"):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            return FakeResponse(json.dumps(body).encode())

        with mock.patch.object(mqtt_client.urllib.request, "urlopen", fake_urlopen):
            mqtt_client.run_effect(name)
        return captured

    def test_posts_a_temporary_override_not_a_baseline(self):
        captured = self.post({"accepted": True})
        self.assertTrue(captured["url"].endswith("/api/runtime/override"))
        self.assertEqual(captured["body"]["effect"], "fire")
        self.assertEqual(captured["body"]["source"], "mqtt")
        self.assertGreater(captured["body"]["duration_seconds"], 0)

    def test_rejection_raises_with_reason(self):
        with self.assertRaisesRegex(ValueError, "lower priority"):
            self.post({"accepted": False, "reason": "lower priority override rejected"})


class OnMessageTests(unittest.TestCase):
    def test_named_effect_is_run(self):
        out, err = quiet()
        with mock.patch.object(mqtt_client, "run_effect") as run, out, err:
            mqtt_client.on_message(None, None, FakeMessage('{"name": "fire", "x": 1}'))
        run.assert_called_once_with("fire")

    def test_payloads_without_an_effect_name_are_ignored(self):
        out, err = quiet()
        with mock.patch.object(mqtt_client, "run_effect") as run, out, err:
            mqtt_client.on_message(None, None, FakeMessage(""))
            mqtt_client.on_message(None, None, FakeMessage("fire"))  # bare string, not a JSON object
            mqtt_client.on_message(None, None, FakeMessage('{"nope": 1}'))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
