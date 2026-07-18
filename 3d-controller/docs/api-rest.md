# REST control API

The local control service exposes the browser-facing REST API. It is the HTTP ingress into the same `RuntimeCoordinator` used by future adapters; it is not an MQTT bridge.

Start it with `thunderdome control serve`. See [control-service.md](control-service.md) for capability and live-output safety details.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/control/capabilities` | Safe service capabilities and allowed outputs. |
| GET | `/api/effects` | Effect schemas and resolved defaults. |
| GET | `/api/effects/{name}` | One effect schema. |
| GET / PUT / DELETE | `/api/effect-defaults/{effect}` | Read, save, or restore effect-only operator defaults. |
| GET | `/api/runtime/status` | Sanitized baseline/override/runtime status. |
| POST | `/api/runtime/baseline` | Set browser-owned baseline. |
| POST | `/api/runtime/override` | Apply a temporary override. |
| POST | `/api/runtime/cancel-override` | Cancel active override and restart baseline. |
| POST | `/api/runtime/restart-baseline` | Restart baseline and clear override. |
| POST | `/api/runtime/stop` | Stop and clear baseline plus override. |

Requests are server-side validated with the authoritative effect schema. Live `ddp`/`both` output is available only when the service is deliberately configured with server-owned controllers and live control enabled. Client requests cannot provide controller addresses.

## Related contributor contracts

- [Control architecture](control-architecture.md)
- [Runtime command contract](runtime-command-contract.md)
- [MQTT integration specification](mqtt-integration-spec.md) — future adapter contract; current service does not connect to MQTT.
- [MQTT temporary overrides ADR](adr/0001-mqtt-temporary-overrides.md)
