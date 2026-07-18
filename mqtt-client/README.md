# MQTT Client

MQTT bridge for the thunderdomedome.

Listens to messages on `open/dogsbody/thunderdome/+` and enacts them on the dome.

Effects: A message on `open/dogsbody/thunderdome/effect` with the effect name as the payload.

## Run

Requires Python 3.10+ and the `thunderdome` CLI on `PATH`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # optional; defaults work
.venv/bin/python mqtt_client.py
```

On connect you'll see `connected to <host>:<port>`. Trigger an effect with e.g.
`mosquitto_pub -h mqtt.emf.camp -t open/dogsbody/thunderdome/effect -m fire`.

## Config

From `.env` or real env vars (env wins). All optional.

| Variable | Default | Notes |
|-----------|-----------|-------|
| `MQTT_HOST` | `mqtt.emf.camp` | Broker hostname |
| `MQTT_PORT` | `1883` | |
| `MQTT_USER` | *(unset)* | Optional; enables auth |
| `MQTT_PASS` | *(unset)* | Only used if `MQTT_USER` set |
| `EFFECT_OUTPUT` | `ddp` | `ddp` = real dome, `simulator` = local test |
| `THUNDERDOME_CONTROLLERS` | *(unset)* | Override the CLI's `controllers.json` path |

Dome targeting lives in the thunderdome CLI's `controllers.json` (see the
`3d-controller` repo), not here.
