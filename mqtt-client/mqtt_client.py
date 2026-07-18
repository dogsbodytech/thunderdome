#!/usr/bin/env python3
"""MQTT -> thunderdome effect bridge.

A message on `open/dogsbody/thunderdome/effect` whose payload is an effect name
runs `thunderdome effect <name>` against the dome. Each new effect replaces the
one currently running, so only one process drives DDP at a time.
"""
import os
import subprocess
import sys

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get("MQTT_HOST", "mqtt.emf.camp")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = "open/dogsbody/thunderdome/effect"
OUTPUT = os.environ.get("EFFECT_OUTPUT", "ddp")  # ddp = real dome; simulator = local test
CONTROLLERS = os.environ.get("THUNDERDOME_CONTROLLERS")  # optional controllers.json override

# Allowlist of effect names -> `thunderdome effect <name>`. The payload comes
# off the network and is passed as an argv positional, so we never forward an
# unvetted string (an allowlist also blocks flag injection like "--output").
# ponytail: hardcoded to avoid importing the heavy thunderdome package here;
# keep in sync with the CLI's `effect` subcommands (thunderdome/effects/_registry.py).
EFFECTS = {
    "clock-hand", "expanding-rings", "height-wave", "fire",
    "rotating-plane", "radar", "aurora", "fireflies",
}

_current: subprocess.Popen | None = None


def run_effect(name: str) -> subprocess.Popen:
    """Stop the running effect (if any) and start `name`. Returns the new process."""
    global _current
    if _current and _current.poll() is None:
        _current.terminate()  # one effect at a time; SIGTERM stops its DDP stream
    cmd = ["thunderdome", "effect", name, "--output", OUTPUT, "--hold"]
    if CONTROLLERS:
        cmd += ["--controllers", CONTROLLERS]
    _current = subprocess.Popen(cmd)  # non-blocking so the network loop keeps its keepalive
    return _current


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"connected to {HOST}:{PORT} ({reason_code})", flush=True)
    client.subscribe(TOPIC)  # subscribe here so it re-applies after reconnect


def on_message(client, userdata, msg):
    name = msg.payload.decode("utf-8", errors="replace").strip()
    if name not in EFFECTS:
        print(f"ignored {msg.topic}: unknown effect {name!r}", flush=True)
        return
    print(f"{msg.topic} -> thunderdome effect {name}", flush=True)
    try:
        run_effect(name)
    except OSError as e:
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
    assert "height-wave" in EFFECTS
    assert "auto" not in EFFECTS       # meta-playlist, not a single effect
    assert "--output" not in EFFECTS   # allowlist blocks flag injection
    assert "" not in EFFECTS           # empty payload ignored
    print("self-test ok")


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
