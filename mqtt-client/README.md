# MQTT Client

MQTT bridge for the thunderdome dome.

Listens on `open/dogsbody/thunderdome/effect` and forwards each message to the
`thunderdome control serve` REST API as a runtime baseline. The control service
owns the single render loop, so each new effect replaces the running one. See
`3d-controller/docs/api-rest.md` for the API.

## Run

1. Start the control service (in the `3d-controller` repo). Simulator-only:

   ```sh
   thunderdome control serve --port 8080
   ```

   Or driving the physical dome:

   ```sh
   thunderdome control serve --controllers config/controllers.json \
     --allow-live-control --default-output ddp
   ```

2. Start this bridge:

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp .env.example .env        # optional; defaults work
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
| `EFFECT_OUTPUT` | *(unset)* | Force `simulator`/`ddp`/`both`; unset inherits the service's `--default-output` |

Output policy (simulator vs live dome) and dome targeting live in the control
service (`--controllers`, `--allow-live-control`, `--default-output`), not here.
