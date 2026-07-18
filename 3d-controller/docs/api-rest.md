# REST API

`thunderdome control serve` exposes a JSON REST API for driving the dome: query available effects, set a baseline display, apply temporary overrides, and read runtime status. The same server also hosts the simulator viewer and its read-only JSON endpoints.

```bash
# Simulator-only (safe default) — http://127.0.0.1:8080
thunderdome control serve --host 127.0.0.1 --port 8080

# With physical DDP capability — deliberate opt-in at startup
thunderdome control serve \
  --controllers config/controllers.json --allow-live-control
```

There is no authentication; the service is designed for `127.0.0.1`. Controller addresses are server-owned: clients can never submit them, and no API returns them. `ddp`/`both` output is rejected unless the service was started with both `--controllers` and `--allow-live-control`. See [control-service.md](control-service.md) for the safety model.

This service is the HTTP ingress into the same `RuntimeCoordinator` used by future adapters (e.g. MQTT); it is not an MQTT bridge and does not connect to MQTT.

## Conventions

- All requests and responses are JSON (`Content-Type: application/json`).
- Every `POST` requires a JSON body — send `{}` when an endpoint needs no fields.
- Output modes are `simulator`, `ddp`, `both`, or `null`.
- Colours are 6-digit hex strings, with or without `#` (e.g. `"FF8800"`).
- Status codes:

| Status | Meaning | Body |
| --- | --- | --- |
| 200 | Success / command accepted | endpoint payload |
| 400 | Invalid input (unknown parameter, bad value, disabled output) | `{"accepted": false, "error": "..."}` or `{"error": "..."}` |
| 404 | Unknown effect name in URL | `{"error": "unknown effect"}` |
| 409 | Command rejected by arbitration | `{"accepted": false, "reason": "...", "status": {...}}` |

## Runtime model

A **baseline** is the normal ongoing display; setting a new one replaces the old. An **override** temporarily pre-empts the baseline: a higher-priority override replaces a lower one, equal priority replaces, lower priority is rejected with 409 (never queued). When an override expires or is cancelled, the baseline restarts from the beginning. Full semantics in [control-service.md](control-service.md).

## Discovery endpoints

### `GET /api/control/capabilities`

What this service instance can do. Check `supported_outputs` before requesting `ddp` or `both`.

```json
{
  "service_mode": "control",
  "simulator_available": true,
  "live_ddp_available": false,
  "both_available": false,
  "controller_config_loaded": false,
  "live_control_enabled": false,
  "default_output": "simulator",
  "supported_outputs": ["simulator"],
  "brightness_default": 255,
  "effect_count": 22,
  "auto_mode_available": true,
  "mqtt_configured": false
}
```

### `GET /api/effects`

All effect schemas: `clock-hand`, `expanding-rings`, `height-wave`, `fire`, `rotating-plane`, `radar`, `aurora`, `fireflies`, `twinkle`, `auto`, and the solar-system bodies (`sol`, `mercury`, `venus`, `earth`, `mars`, `jupiter`, `saturn`, `uranus`, `neptune`, `asteroid-belt`, `kuiper-belt`, `voyager-1`). Each entry lists every parameter with its type, default, bounds, units, and choices — this is the authoritative parameter reference; use it instead of hard-coding parameter lists. Non-`auto` entries also include `resolved_defaults` (built-in defaults merged with saved operator defaults).

### `GET /api/effects/{name}`

One effect schema, or 404. Example (abridged):

```json
{
  "name": "height-wave",
  "label": "Height wave",
  "description": "Horizontal band sweeping the dome's height.",
  "parameters": [
    {"name": "brightness", "type": "integer", "default": 255, "minimum": 0, "maximum": 255, "classification": "runtime", ...},
    {"name": "fps", "type": "integer", "default": 30, "minimum": 1, "maximum": 60, "classification": "runtime", ...},
    {"name": "exclude_tail", "type": "boolean", "default": false, "classification": "runtime", ...},
    {"name": "speed_mps", "type": "float", "default": 0.5, "minimum": 0.001, "units": "m/s", ...},
    {"name": "height_mm", "type": "float", "default": 200.0, "minimum": 0.001, "units": "mm", ...},
    {"name": "direction", "type": "choice", "default": "up", "choices": ["up", "down", "bounce"], ...},
    {"name": "color", "type": "colour", "default": "FFFFFF", ...},
    {"name": "background", "type": "colour", "default": "000000", ...}
  ]
}
```

Every effect shares three `runtime`-classified parameters: `brightness` (0–255, default 255), `fps` (1–60, default 30), and `exclude_tail` (boolean, default false).

## Effect defaults

Operator-saved parameter defaults, persisted server-side in `config/effect-defaults.json` and merged over built-in defaults. `auto` and runtime parameters (`brightness`, `fps`, `exclude_tail`) cannot be saved as defaults.

| Method and path | Behaviour |
| --- | --- |
| `GET /api/effect-defaults` | All effects: `{"effects": [payload, ...]}` |
| `GET /api/effect-defaults/{effect}` | One payload (below) |
| `PUT /api/effect-defaults/{effect}` | Save; body `{"parameters": {...}}`; returns updated payload |
| `DELETE /api/effect-defaults/{effect}` | Remove saved defaults; returns updated payload |

Payload shape:

```json
{
  "effect": "fire",
  "built_in":  {"speed": 1.0, "flame_height_m": 2.5, ...},
  "saved":     {"flame_height_m": 3.0},
  "resolved":  {"speed": 1.0, "flame_height_m": 3.0, ...}
}
```

## Runtime status

### `GET /api/runtime/status`

```json
{
  "service_state": "running",
  "baseline":  {"effect": "auto", "parameters": {...}, "output": "simulator", "source": "browser", "request_id": "…", "created_at": 12345.6, "priority": 0, "expires_at": null},
  "override":  null,
  "effective": {"effect": "auto", ...},
  "remaining_override_seconds": null,
  "latest_error": null,
  "rendered_frames": 4213,
  "active_since": 12345.6,
  "latest_sink_error": null
}
```

- `service_state` — `"idle"` or `"running"`.
- `effective` — what is actually displaying: the override if one is active, otherwise the baseline.
- `remaining_override_seconds` — seconds until the active override expires, if it has a duration.
- `latest_error` — last rejected/failed command; `latest_sink_error` — last frame-delivery failure (e.g. simulator not running).
- Timestamps (`created_at`, `expires_at`, `active_since`) are server monotonic-clock seconds, useful only relative to each other.

## Runtime commands

All five command endpoints are `POST` and share one body shape and one response shape.

Request body:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `effect` | string | for `baseline`/`override` | Name from `GET /api/effects` |
| `parameters` | object | no | Validated against the effect schema; omitted parameters use resolved defaults; unknown names are rejected |
| `output` | string | no | `simulator`, `ddp`, `both`, `null`. Baseline defaults to the service default (`simulator`); an override inherits the baseline's output |
| `priority` | integer ≥ 0 | no | Default 0; only meaningful for `override` |
| `duration_seconds` | number > 0 | no | Auto-expire an override, or make a baseline finite |
| `request_id` | string | no | Client-supplied idempotency/tracking ID; server generates a UUID when omitted |

Response, 200 when accepted, 409 when rejected:

```json
{"accepted": true, "reason": null, "status": { ...same shape as /api/runtime/status... }}
```

### `POST /api/runtime/baseline`

Set the normal display, replacing any existing baseline. If an override is active, the new baseline takes effect when the override ends. A baseline with `duration_seconds` stops on its own and leaves the service idle.

```bash
curl -s -X POST http://127.0.0.1:8080/api/runtime/baseline \
  -H 'Content-Type: application/json' \
  -d '{"effect": "auto", "parameters": {"effects": ["aurora", "fireflies"], "interval": 30, "brightness": 32}}'
```

### `POST /api/runtime/override`

Temporarily pre-empt the baseline. Rejected with 409 (`"lower priority override rejected"`) if an active override has higher priority. When it expires or is cancelled, the baseline restarts from the beginning.

```bash
curl -s -X POST http://127.0.0.1:8080/api/runtime/override \
  -H 'Content-Type: application/json' \
  -d '{"effect": "expanding-rings", "parameters": {"origin": "apex", "brightness": 64}, "priority": 10, "duration_seconds": 15}'
```

### `POST /api/runtime/cancel-override`

Body `{}`. Ends the active override and restarts the baseline. 409 `"no active override"` if there is none.

### `POST /api/runtime/restart-baseline`

Body `{}`. Clears any override and restarts the baseline from the beginning. 409 `"no baseline configured"` if there is none.

### `POST /api/runtime/stop`

Body `{}`. Clears baseline and override; the service goes idle.

## Parameter validation

Server-side, strict, applied to `parameters` and to saved defaults:

- Unknown parameter names and unknown effects are rejected.
- `integer`/`float` values must be finite numbers; booleans are not accepted as numbers.
- `colour` values must match `#RRGGBB` or `RRGGBB`.
- `vector` values (`rotating-plane --axis`, `aurora --direction`) accept the names `vertical`, `horizontal`, `tilted`, a `"X,Y,Z"` string, or a three-number array; zero vectors are rejected.
- `choice` values must be one of the schema's `choices`.
- `auto.effects` must be a non-empty list of known effect names without duplicates, and `transition` must be less than `interval`.
- Minimum/maximum bounds from the schema are enforced.

## Simulator read-only endpoints

Hosted by both `control serve` and `simulator serve`; no control capability involved. Documented in [simulator.md](simulator.md).

| Endpoint | Returns |
| --- | --- |
| `GET /api/simulator/metadata` | Schema version, data sources, LED/hub/spar counts, bounds |
| `GET /api/simulator/status` | Connection and frame counters |
| `GET /api/simulator/geometry` | Hubs, spars, apex, dome bounds |
| `GET /api/simulator/leds` | All 5,000 LED records in global-index order |
| `WS /ws/producer` | Binary live-frame input (one producer) |
| `WS /ws/viewer` | Binary live-frame output (many viewers) |

## Worked example

```bash
# 1. What can this service do?
curl -s http://127.0.0.1:8080/api/control/capabilities

# 2. Set a calm baseline in the simulator
curl -s -X POST http://127.0.0.1:8080/api/runtime/baseline \
  -H 'Content-Type: application/json' \
  -d '{"effect": "aurora", "parameters": {"brightness": 32}}'

# 3. Flash a 10-second red alert over it
curl -s -X POST http://127.0.0.1:8080/api/runtime/override \
  -H 'Content-Type: application/json' \
  -d '{"effect": "height-wave", "parameters": {"color": "FF0000", "direction": "bounce", "brightness": 64}, "priority": 10, "duration_seconds": 10}'

# 4. Watch it hand back to the baseline
curl -s http://127.0.0.1:8080/api/runtime/status

# 5. All off
curl -s -X POST http://127.0.0.1:8080/api/runtime/stop \
  -H 'Content-Type: application/json' -d '{}'
```

## Related contributor contracts

- [Control architecture](control-architecture.md)
- [Runtime command contract](runtime-command-contract.md)
- [MQTT integration specification](mqtt-integration-spec.md) — future adapter contract; current service does not connect to MQTT.
- [MQTT temporary overrides ADR](adr/0001-mqtt-temporary-overrides.md)
