#!/usr/bin/env python3
"""MQTT -> thunderdome effect bridge.

A message on `open/dogsbody/thunderdome/effect` whose payload is an effect name
is POSTed as a temporary override to the running `thunderdome control serve`
HTTP service. Overrides expire after EFFECT_DURATION_SECONDS and the baseline
display restarts, so a public MQTT message can never leave the dome
permanently on an effect.

Start the control service first, e.g.:
    thunderdome control serve --allow-live-control \
        --controllers config/controllers.json --default-output ddp
"""
import json
import os
import re
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
# Optional output override. Unset = inherit the baseline output or the control
# service's --default-output, which is where live-vs-simulator safety already
# lives. Only set to force it.
OUTPUT = os.environ.get("EFFECT_OUTPUT") or None
# How long a publicly triggered effect runs before the baseline is restored.
DURATION_SECONDS = float(os.environ.get("EFFECT_DURATION_SECONDS", "120"))
# Optional comma-separated allow-list. Unset = any well-formed name is forwarded
# and the control service rejects unknown effects with a 400.
ALLOWLIST = frozenset(filter(None, (n.strip() for n in os.environ.get("EFFECT_ALLOWLIST", "").split(",")))) or None
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
    # ponytail: blocks the MQTT loop for up to 5s; keepalive is 60s so it's fine.
    with urllib.request.urlopen(request, timeout=5) as response:
        body = json.load(response)
    if not body.get("accepted"):
        raise ValueError(body.get("error") or body.get("reason") or "rejected")


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
    print(f"{msg.topic} -> override {name} for {DURATION_SECONDS:g}s", flush=True)
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


if __name__ == "__main__":
    main()
