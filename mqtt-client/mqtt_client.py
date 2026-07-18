#!/usr/bin/env python3
"""MQTT -> thunderdome effect bridge.

A message on `open/dogsbody/thunderdome/effect` whose payload is an effect name
is POSTed as a temporary override to the running `thunderdome control serve`
HTTP service. Overrides expire after EFFECT_DURATION_SECONDS and the baseline
display restarts, so a public MQTT message can never leave the dome
permanently on an effect. Bursts are debounced (DEBOUNCE_SECONDS, newest
message wins) and the HTTP call runs on a worker thread, never inside the
MQTT network loop.

Start the control service first, e.g.:
    thunderdome control serve --allow-live-control \
        --controllers config/controllers.json --default-output ddp
"""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get("MQTT_HOST", "mqtt.emf.camp")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = "open/dogsbody/thunderdome/effect"
STATUS_TOPIC = TOPIC + "/status"
CONTROL_URL = os.environ.get("CONTROL_URL", "http://127.0.0.1:8080").rstrip("/")
# Optional output override. Unset = inherit the baseline output or the control
# service's --default-output, which is where live-vs-simulator safety already
# lives. Only set to force it.
OUTPUT = os.environ.get("EFFECT_OUTPUT") or None
# How long a publicly triggered effect runs before the baseline is restored.
DURATION_SECONDS = float(os.environ.get("EFFECT_DURATION_SECONDS", "120"))
# Optional comma-separated allow-list. Unset = any well-formed name is forwarded
# and the control service rejects unknown effects with a 400.
ALLOWLIST = frozenset(filter(None, (n.strip() for n in os.environ.get("EFFECT_ALLOWLIST", "").split(",")))) or None
# Let a burst of messages settle before forwarding; the newest request wins.
DEBOUNCE_SECONDS = float(os.environ.get("DEBOUNCE_SECONDS", "2"))
# The topic is public, so bound what we parse and forward.
MAX_PAYLOAD_BYTES = 4096
NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def validate_name(name) -> str | None:
    """Return `name` if it is a well-formed, allowed effect name, else None."""
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        return None
    if ALLOWLIST is not None and name not in ALLOWLIST:
        return None
    return name


def override_payload(name: str) -> dict:
    """Override body: effect, bounded duration, and mqtt source (rest server-side)."""
    payload = {"effect": name, "source": "mqtt", "duration_seconds": DURATION_SECONDS}
    if OUTPUT:
        payload["output"] = OUTPUT
    return payload


def run_effect(name: str) -> None:
    """POST `name` as a temporary runtime override. Raises URLError/HTTPError on failure."""
    request = urllib.request.Request(
        f"{CONTROL_URL}/api/runtime/override",
        data=json.dumps(override_payload(name)).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        body = json.load(response)
    if not body.get("accepted"):
        raise ValueError(body.get("error") or body.get("reason") or "rejected")


def apply_effect(name: str, publish=None) -> None:
    """run_effect plus operator logging and an MQTT ack; runs off the MQTT loop."""
    accepted, error = False, None
    try:
        run_effect(name)
        accepted = True
        print(f"override {name} accepted for {DURATION_SECONDS:g}s", flush=True)
    except urllib.error.HTTPError as e:
        # 400/409 carry a JSON reason; surface it instead of a bare status.
        body = e.read().decode("utf-8", errors="replace")
        print(f"effect {name} rejected: {e.code} {body}", file=sys.stderr, flush=True)
        try:
            details = json.loads(body)
            error = details.get("error") or details.get("reason") or f"rejected (HTTP {e.code})"
        except ValueError:
            error = f"rejected (HTTP {e.code})"
    except ValueError as e:
        print(f"effect {name} rejected: {e}", file=sys.stderr, flush=True)
        error = str(e)
    except (urllib.error.URLError, OSError) as e:
        print(f"failed to run effect {name}: {e}", file=sys.stderr, flush=True)
        error = "control service unavailable"  # keep internals off the public topic
    if publish is not None:
        payload = {"effect": name, "accepted": accepted}
        if error is not None:
            payload["error"] = error
        publish(payload)


class EffectDispatcher:
    """Applies the newest requested effect on a worker thread.

    `submit` never blocks: it records the latest name and wakes the worker.
    The worker waits out the debounce window, then applies whichever request
    arrived last, so a burst of messages costs one HTTP call and the slow
    urlopen never runs inside Paho's network loop.
    """

    def __init__(self, apply, debounce_seconds):
        self._apply = apply
        self._debounce = debounce_seconds
        self._lock = threading.Lock()
        self._pending = None
        self._wakeup = threading.Event()
        self._stopping = False
        self._thread = threading.Thread(target=self._run, name="effect-dispatcher", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        self._wakeup.set()
        self._thread.join(timeout=5)

    def submit(self, name: str) -> None:
        with self._lock:
            self._pending = name
        self._wakeup.set()

    def _run(self) -> None:
        while True:
            self._wakeup.wait()
            if self._stopping:
                return
            time.sleep(self._debounce)  # let the burst settle; newest wins
            with self._lock:
                name, self._pending = self._pending, None
                self._wakeup.clear()
            if self._stopping:
                return
            if name is None:
                continue
            try:
                self._apply(name)
            except Exception as e:  # keep the worker alive; apply reports its own errors
                print(f"unexpected error applying {name}: {e}", file=sys.stderr, flush=True)


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"connected to {HOST}:{PORT} ({reason_code})", flush=True)
    client.subscribe(TOPIC)  # subscribe here so it re-applies after reconnect


def on_message(client, userdata, msg):
    if len(msg.payload) > MAX_PAYLOAD_BYTES:
        print(f"ignored {msg.topic}: payload over {MAX_PAYLOAD_BYTES} bytes", file=sys.stderr, flush=True)
        return
    raw = msg.payload.decode("utf-8", errors="replace").strip()
    if not raw:
        return
    try:
        name = json.loads(raw)["name"]  # payload is {"name": "fire", ...}
    except (ValueError, KeyError, TypeError):
        print(f"ignored {msg.topic}: no effect name in {raw!r}", file=sys.stderr, flush=True)
        return
    if validate_name(name) is None:
        print(f"ignored {msg.topic}: invalid or disallowed effect name {name!r:.80}", file=sys.stderr, flush=True)
        return
    print(f"{msg.topic} -> queued {name} (debounce {DEBOUNCE_SECONDS:g}s)", flush=True)
    userdata.submit(name)  # userdata is the EffectDispatcher; never block the MQTT loop


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def publish_status(payload: dict) -> None:
        client.publish(STATUS_TOPIC, json.dumps(payload))

    dispatcher = EffectDispatcher(lambda name: apply_effect(name, publish_status), DEBOUNCE_SECONDS)
    dispatcher.start()
    client.user_data_set(dispatcher)
    if os.environ.get("MQTT_USER"):
        client.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASS"))
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(HOST, PORT, keepalive=60)
    try:
        client.loop_forever(retry_first_connection=True)  # auto-reconnect, exponential backoff
    finally:
        dispatcher.stop()


if __name__ == "__main__":
    main()
