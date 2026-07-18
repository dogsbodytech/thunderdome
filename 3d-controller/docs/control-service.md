# Control service (Stage C1)

`thunderdome control serve` is the local operator service. It hosts the existing simulator viewer, its live-frame WebSockets, and a single control-runtime API on one local aiohttp server.

```bash
# Safe simulator-only operator service
thunderdome control serve --host 127.0.0.1 --port 8080 --open-browser

# Deliberate physical-output capability; controller addresses stay server-owned.
thunderdome control serve --host 127.0.0.1 --port 8080 \
  --controllers config/controllers.json --allow-live-control --open-browser
```

`thunderdome simulator serve` remains the simulator-only compatibility command. It never exposes control APIs or physical DDP output.

## Runtime model

Browser/API commands and future MQTT integration use the same command model and coordinator. Stage C1 does **not** connect to MQTT.

- A **baseline** is the normal effect or auto display and replaces the prior baseline.
- An **override** temporarily pre-empts it. Higher priority wins; equal priority newer overrides replace; lower priority requests are rejected and never queued.
- On override expiry or cancellation, the baseline restarts from the beginning rather than attempting effect-local pause/resume.
- Stop clears baseline and override.

One cancellable worker thread owns one renderer and its selected sink set. Cancellation wakes the frame loop promptly, closes sinks, and prevents concurrent renderers/DDP sessions. Rendering never runs on the aiohttp event loop.

## Safety

The default bind host is `127.0.0.1`; simulator output is the default and DDP never falls back from it. Live DDP capability exists only when both `--controllers FILE` and `--allow-live-control` are supplied at service startup. Browser requests cannot submit controller addresses, and controller addresses are not returned by APIs.

Do not bind a live-enabled service to `0.0.0.0` on an untrusted network. Live controls affect the physical dome. No WLED preparation or power-management command is sent by this service.

Brightness defaults to **255** in schemas and control requests.

## APIs

Full endpoint reference with request/response bodies and examples: [rest-api.md](api.md).

- `GET /api/control/capabilities`
- `GET /api/effects`
- `GET /api/effects/{name}`
- `GET /api/runtime/status`
- `POST /api/runtime/baseline`
- `POST /api/runtime/override`
- `POST /api/runtime/cancel-override`
- `POST /api/runtime/restart-baseline`
- `POST /api/runtime/stop`

Baseline/override bodies contain `effect`, `parameters`, optional `output`, `priority`, `duration_seconds`, and optional `request_id`. API validation is server-side and returns structured JSON errors. `ddp` and `both` are rejected unless live capability was explicitly enabled.

Stage C1 exposes schemas and runtime status for the next browser-controls stage; it intentionally does not implement dynamic effect forms, an MQTT listener, recording/replay, or a playlist editor.
