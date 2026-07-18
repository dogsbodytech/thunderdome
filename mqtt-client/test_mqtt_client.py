"""Unit tests for the MQTT -> thunderdome bridge.

Run from this directory with:
    .venv/bin/python -m unittest discover
"""
import contextlib
import io
import json
import threading
import time
import unittest
import urllib.error
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


class ConnectionLoggingTests(unittest.TestCase):
    def test_disconnects_are_logged_with_the_reason(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            mqtt_client.on_disconnect(None, None, None, "Keep alive timeout", None)
        self.assertIn("disconnected", err.getvalue())
        self.assertIn("Keep alive timeout", err.getvalue())


class ApplyEffectStatusTests(unittest.TestCase):
    def run_apply(self, urlopen):
        published = []
        out, err = quiet()
        with mock.patch.object(mqtt_client.urllib.request, "urlopen", urlopen), out, err:
            mqtt_client.apply_effect("fire", published.append)
        return published

    def test_ack_is_published_on_success(self):
        published = self.run_apply(lambda request, timeout: FakeResponse(b'{"accepted": true}'))
        self.assertEqual(published, [{"effect": "fire", "accepted": True}])

    def test_server_rejection_reason_is_published(self):
        def reject(request, timeout):
            body = io.BytesIO(b'{"accepted": false, "error": "unknown effect"}')
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", None, body)

        published = self.run_apply(reject)
        self.assertEqual(published, [{"effect": "fire", "accepted": False, "error": "unknown effect"}])

    def test_connection_failures_do_not_leak_internals(self):
        def down(request, timeout):
            raise urllib.error.URLError("connection refused for http://127.0.0.1:8080")

        published = self.run_apply(down)
        self.assertEqual(published, [{"effect": "fire", "accepted": False, "error": "control service unavailable"}])

    def test_publish_is_optional(self):
        out, err = quiet()
        with mock.patch.object(mqtt_client, "run_effect"), out, err:
            mqtt_client.apply_effect("fire")  # no publisher wired: just logs


class ValidateNameTests(unittest.TestCase):
    def test_wellformed_names_pass_without_allowlist(self):
        with mock.patch.object(mqtt_client, "ALLOWLIST", None):
            for name in ("fire", "expanding-rings", "auto"):
                self.assertEqual(mqtt_client.validate_name(name), name)

    def test_malformed_names_are_rejected(self):
        with mock.patch.object(mqtt_client, "ALLOWLIST", None):
            for bad in (None, 7, "", "Fire", "fire effect", "fire\n", "-fire", "a" * 65, {"n": 1}):
                self.assertIsNone(mqtt_client.validate_name(bad))

    def test_allowlist_restricts_names(self):
        with mock.patch.object(mqtt_client, "ALLOWLIST", frozenset({"fire"})):
            self.assertEqual(mqtt_client.validate_name("fire"), "fire")
            self.assertIsNone(mqtt_client.validate_name("aurora"))


class FakeDispatcher:
    def __init__(self):
        self.submitted = []

    def submit(self, name):
        self.submitted.append(name)


class OnMessageTests(unittest.TestCase):
    def test_named_effect_is_queued(self):
        dispatcher = FakeDispatcher()
        out, err = quiet()
        with out, err:
            mqtt_client.on_message(None, dispatcher, FakeMessage('{"name": "fire", "x": 1}'))
        self.assertEqual(dispatcher.submitted, ["fire"])

    def test_payloads_without_an_effect_name_are_ignored(self):
        dispatcher = FakeDispatcher()
        out, err = quiet()
        with out, err:
            mqtt_client.on_message(None, dispatcher, FakeMessage(""))
            mqtt_client.on_message(None, dispatcher, FakeMessage("fire"))  # bare string, not a JSON object
            mqtt_client.on_message(None, dispatcher, FakeMessage('{"nope": 1}'))
        self.assertEqual(dispatcher.submitted, [])

    def test_oversized_payloads_are_ignored_before_parsing(self):
        dispatcher = FakeDispatcher()
        big = b'{"name": "' + b"a" * (mqtt_client.MAX_PAYLOAD_BYTES + 1) + b'"}'
        out, err = quiet()
        with out, err:
            mqtt_client.on_message(None, dispatcher, FakeMessage(big))
        self.assertEqual(dispatcher.submitted, [])

    def test_disallowed_names_are_not_queued(self):
        dispatcher = FakeDispatcher()
        out, err = quiet()
        with mock.patch.object(mqtt_client, "ALLOWLIST", frozenset({"fire"})), out, err:
            mqtt_client.on_message(None, dispatcher, FakeMessage('{"name": "aurora"}'))
            mqtt_client.on_message(None, dispatcher, FakeMessage('{"name": "fire; rm -rf /"}'))
        self.assertEqual(dispatcher.submitted, [])


class EffectDispatcherTests(unittest.TestCase):
    def wait_for(self, condition, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.01)
        return condition()

    def test_burst_applies_only_the_newest_request(self):
        applied = []
        dispatcher = mqtt_client.EffectDispatcher(applied.append, debounce_seconds=0.05)
        dispatcher.start()
        try:
            for name in ("fire", "aurora", "radar"):
                dispatcher.submit(name)
            self.assertTrue(self.wait_for(lambda: applied == ["radar"]))
            time.sleep(0.15)  # no stale second apply after the burst
            self.assertEqual(applied, ["radar"])
        finally:
            dispatcher.stop()

    def test_message_arriving_during_apply_is_applied_next(self):
        applied = []
        first_started = threading.Event()
        release = threading.Event()

        def apply(name):
            applied.append(name)
            if len(applied) == 1:
                first_started.set()
                release.wait(2)

        dispatcher = mqtt_client.EffectDispatcher(apply, debounce_seconds=0.01)
        dispatcher.start()
        try:
            dispatcher.submit("fire")
            self.assertTrue(first_started.wait(2))
            dispatcher.submit("aurora")
            release.set()
            self.assertTrue(self.wait_for(lambda: applied == ["fire", "aurora"]))
        finally:
            dispatcher.stop()

    def test_apply_errors_do_not_kill_the_worker(self):
        applied = []

        def apply(name):
            if name == "boom":
                raise RuntimeError("kaboom")
            applied.append(name)

        dispatcher = mqtt_client.EffectDispatcher(apply, debounce_seconds=0.01)
        dispatcher.start()
        err = contextlib.redirect_stderr(io.StringIO())
        try:
            with err:
                dispatcher.submit("boom")
                time.sleep(0.1)
                dispatcher.submit("fire")
                self.assertTrue(self.wait_for(lambda: applied == ["fire"]))
        finally:
            dispatcher.stop()

    def test_stop_terminates_the_worker(self):
        dispatcher = mqtt_client.EffectDispatcher(lambda name: None, debounce_seconds=0.01)
        dispatcher.start()
        dispatcher.stop()
        self.assertFalse(dispatcher._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
