# MQTT Client

MQTT-to-shell bridge for the dome: publishes on `open/dogsbody/dome/<name>` run the
matching `scripts/tildagon_<name>.py`.

## Run

Requires Python 3.10+.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then set WLED_HOST
.venv/bin/python mqtt_client.py
```

On connect you'll see `connected to <host>:<port>`.

## Config

From `.env` or real env vars (env wins).

| Variable | Default | Notes |
|-----------|-----------|-------|
| `WLED_HOST` | *(required)* | WLED host/IP the scripts target |
| `MQTT_HOST` | `mqtt.emf.camp` | Broker hostname |
| `MQTT_PORT` | `1883` | |
| `MQTT_USER` | *(unset)* | Optional; enables auth |
| `MQTT_PASS` | *(unset)* | Only used if `MQTT_USER` set |

Handler scripts live in `scripts/` (`tildagon_<name>.py`, case-sensitive).
