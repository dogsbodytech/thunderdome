#!/usr/bin/env python3
"""MQTT -> shell bridge: message on open/dogsbody/dome/<name> runs scripts/tildagon_<name>.sh <payload>."""
import os
import re
import subprocess
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()  # .env -> os.environ; handlers inherit these via Popen

HOST = os.environ.get("MQTT_HOST", "mqtt.emf.camp")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = "open/dogsbody/dome/+"
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# Network input feeds an exec path: allowlist the script name strictly.
NAME_RE = re.compile(r"[A-Za-z0-9_-]+")


def script_for(topic: str) -> Path | None:
    name = topic.rsplit("/", 1)[-1]
    if not NAME_RE.fullmatch(name):
        return None
    return SCRIPTS_DIR / f"tildagon_{name}.py"


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"connected to {HOST}:{PORT} ({reason_code})", flush=True)
    client.subscribe(TOPIC)  # subscribe here so it re-applies after reconnect


def on_message(client, userdata, msg):
    script = script_for(msg.topic)
    if script is None or not script.is_file():
        print(f"ignored {msg.topic}: no matching script", flush=True)
        return
    payload = msg.payload.decode("utf-8", errors="replace")
    print(f"{msg.topic} -> {script.name}", flush=True)
    try:
        # argv form, payload never shell-interpolated; Popen so a slow script
        # can't block the network loop and time out the keepalive.
        # sys.executable = this venv's python, so handlers get dotenv etc.
        subprocess.Popen([sys.executable, str(script), payload])
    except OSError as e:
        print(f"failed to run {script.name}: {e}", file=sys.stderr, flush=True)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.environ.get("MQTT_USER"):
        client.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASS"))
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(HOST, PORT, keepalive=60)
    client.loop_forever(retry_first_connection=True)  # auto-reconnect, exponential backoff


def self_test():
    assert script_for("open/dogsbody/dome/rainbow").name == "tildagon_rainbow.py"
    assert script_for("open/dogsbody/dome/A-1_x").name == "tildagon_A-1_x.py"
    assert script_for("open/dogsbody/dome/..") is None
    assert script_for("open/dogsbody/dome/a b") is None
    assert script_for("open/dogsbody/dome/") is None
    print("self-test ok")


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
