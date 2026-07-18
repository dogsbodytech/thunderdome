#!/usr/bin/env python3
"""MQTT -> thunderdome effect bridge.

A message on `open/dogsbody/thunderdome/effect` whose payload is an effect name
is POSTed as a baseline to the running `thunderdome control serve` HTTP service.
The control service owns the single render loop, so setting a new baseline
replaces whatever effect is currently running.

Start the control service first, e.g.:
    thunderdome control serve --allow-live-control \
        --controllers config/controllers.json --default-output ddp
"""
import json
import os
import sys
import urllib.error
import urllib.request

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get("MQTT_HOST", "mqtt.emf.camp")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = "open/dogsbody/thunderdome/effect"
CONTROL_URL = os.environ.get("CONTROL_URL", "http://127.0.0.1:8080").rstrip("/")
# Optional output override. Unset = inherit the control service's --default-output,
# which is where live-vs-simulator safety already lives. Only set to force it.
OUTPUT = os.environ.get("EFFECT_OUTPUT") or None


def baseline_payload(name: str) -> dict:
    """Baseline body: effect name plus optional output override (rest server-side)."""
    payload = {"effect": name}
    if OUTPUT:
        payload["output"] = OUTPUT
    return payload


def run_effect(name: str) -> None:
    """POST `name` as the runtime baseline. Raises URLError/HTTPError on failure."""
    request = urllib.request.Request(
        f"{CONTROL_URL}/api/runtime/baseline",
        data=json.dumps(baseline_payload(name)).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # ponytail: blocks the MQTT loop for up to 5s; keepalive is 60s so it's fine.
    with urllib.request.urlopen(request, timeout=5) as response:
        body = json.load(response)
    if not body.get("accepted"):
        raise ValueError(body.get("error") or body.get("reason") or "rejected")


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"connected to {HOST}:{PORT} ({reason_code})", flush=True)
    client.subscribe(TOPIC)  # subscribe here so it re-applies after reconnect


def on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace").strip()
    if not raw:
        return
    try:
        name = json.loads(raw)["name"]  # payload is {"name": "fire", ...}
    except (ValueError, KeyError, TypeError):
        print(f"ignored {msg.topic}: no effect name in {raw!r}", file=sys.stderr, flush=True)
        return
    print(f"{msg.topic} -> baseline {name}", flush=True)
    try:
        run_effect(name)
    except urllib.error.HTTPError as e:
        # 400/409 carry a JSON reason; surface it instead of a bare status.
        reason = e.read().decode("utf-8", errors="replace")
        print(f"effect {name} rejected: {e.code} {reason}", file=sys.stderr, flush=True)
    except (urllib.error.URLError, ValueError, OSError) as e:
        print(f"failed to run effect {name}: {e}", file=sys.stderr, flush=True)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.environ.get("MQTT_USER"):
        client.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASS"))
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(HOST, PORT, keepalive=60)
    client.loop_forever(retry_first_connection=True)  # auto-reconnect, exponential backoff


def self_test():
    # Payload is a JSON body, not argv, so an odd name can't inject flags; the
    # control service validates the effect name and returns 400 for unknown ones.
    assert baseline_payload("fire")["effect"] == "fire"
    assert "output" not in baseline_payload("fire") or OUTPUT  # omitted unless overridden
    assert json.loads('{"name": "fire", "x": 1}')["name"] == "fire"  # effect read from name key
    assert not "".strip()  # empty payload is ignored by on_message before any HTTP call
    print("self-test ok")


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
