# Control service

`thunderdome control serve` hosts the local simulator viewer, live frame WebSockets, and REST runtime API on one aiohttp server. It uses one coordinator and one cancellable rendering worker.

## Safe and live-enabled starts

Safe simulator-only service:

```bash
thunderdome control serve \
  --host 127.0.0.1 \
  --port 8080 \
  --open-browser
```

Deliberate physical capability:

```bash
thunderdome control serve \
  --host 127.0.0.1 \
  --port 8080 \
  --controllers config/controllers.json \
  --allow-live-control \
  --open-browser
```

The second command enables the ability to select physical output but does not itself start a physical effect. Keep the bind host local. Do not bind a live-enabled unauthenticated service to `0.0.0.0` on an untrusted network.

`thunderdome simulator serve` remains the simulator-only compatibility command. It has no control API and no physical output capability.

## Runtime model

- A **baseline** is the normal display and replaces the previous baseline.
- A temporary **override** pre-empts the baseline, with priority and expiry.
- Equal-priority newer overrides replace; lower-priority overrides are rejected, never queued.
- Expiry or cancellation restarts the preserved baseline from time zero.
- Stop clears baseline and override.

Rendering and sink work never run in an HTTP callback. Cancellation closes the selected simulator/DDP sinks and prevents concurrent workers.

## Safety and brightness

Default bind and output are local simulator. `ddp` and `both` are available only when both `--controllers FILE` and `--allow-live-control` were supplied at startup. Browser requests cannot provide controller addresses; addresses remain server-owned.

Before a live DDP sink opens, the service sets enabled WLED master brightness to `255`. This can affect WLED power/on state. It does not change WLED current-limit settings. Normal operating brightness is `255` and valid values are `0..255`.

The service does not connect to MQTT. MQTT remains a future adapter contract; see [control architecture](control-architecture.md), [runtime command contract](runtime-command-contract.md), and [MQTT specification](mqtt-integration-spec.md).

## API surface

Full request/response details are in [REST API](api-rest.md). Main endpoints:

- `GET /api/control/capabilities`
- `GET /api/effects` and `GET /api/effects/{name}`
- `GET /api/runtime/status`
- `POST /api/runtime/baseline`
- `POST /api/runtime/override`
- `POST /api/runtime/cancel-override`
- `POST /api/runtime/restart-baseline`
- `POST /api/runtime/stop`

There is no authentication. Use this service on the local host or a controlled network only.
