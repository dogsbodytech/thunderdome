# MQTT Client

MQTT bridge for the thunderdome dome.

Listens on `open/dogsbody/thunderdome/effect` and forwards each message to the
`thunderdome control serve` REST API as a temporary runtime override. The
effect runs for `EFFECT_DURATION_SECONDS`, then the baseline display is
restored — a public MQTT message can never leave the dome permanently on an
effect. Operators can pre-empt MQTT by applying a browser override with a
higher `priority`. See `3d-controller/docs/api-rest.md` for the API.

## Getting Started

Ensure the `thunderdome control serve` service is running.

### Installation
```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp .env.example .env
```

### Start the Bridge
```sh
.venv/bin/python mqtt_client.py
```

On connect you'll see `connected to <host>:<port>`. The payload is JSON with a
`name` key, e.g. `mosquitto_pub -h mqtt.emf.camp -t
open/dogsbody/thunderdome/effect -m '{"name": "fire"}'`.
Valid names come from `GET /api/effects`: `clock-hand`, `expanding-rings`,
`height-wave`, `fire`, `rotating-plane`, `radar`, `aurora`, `fireflies`, `auto`.

## Config

From `.env` or real env vars (env wins). All optional.

| Variable | Default | Notes |
|-----------|-----------|-------|
| `MQTT_HOST` | `mqtt.emf.camp` | Broker hostname |
| `MQTT_PORT` | `1883` | |
| `MQTT_USER` | *(unset)* | Optional; enables auth |
| `MQTT_PASS` | *(unset)* | Only used if `MQTT_USER` set |
| `CONTROL_URL` | `http://127.0.0.1:8080` | `thunderdome control serve` base URL |
| `EFFECT_OUTPUT` | *(unset)* | Force `simulator`/`ddp`/`both`; unset inherits the baseline output or the service's `--default-output` |
| `EFFECT_DURATION_SECONDS` | `120` | How long a triggered effect runs before the baseline is restored |
| `EFFECT_ALLOWLIST` | *(unset)* | Comma-separated effect names to accept, e.g. `fire,aurora`; unset forwards any well-formed name (the control service still rejects unknown effects) |

Output policy (simulator vs live dome) and dome targeting live in the control
service (`--controllers`, `--allow-live-control`, `--default-output`), not here.

## Tests

```sh
.venv/bin/python -m unittest discover
```
