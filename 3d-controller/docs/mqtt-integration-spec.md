# MQTT integration specification (v1)

> **Status:** contract for a future adapter. The current control service does not connect to MQTT.

An MQTT adapter is a local, authenticated ingress adapter for temporary coordinator overrides. It must follow [the control architecture](control-architecture.md) and [runtime command contract](runtime-command-contract.md); it is not a renderer or hardware-control service.

## Topic namespace

Topic names are deployment-configurable. The following `thunderdome` examples are normative shapes.

| Topic | Direction | QoS | Retained | Roles | Public use |
|---|---|---:|---|---|---|
| `thunderdome/command/override` | publisher → adapter | 1 | **No** | trusted integration publishes; adapter subscribes | No; private authenticated broker namespace only. |
| `thunderdome/command/cancel` | publisher → adapter | 1 | **No** | trusted integration publishes; adapter subscribes | No. |
| `thunderdome/status/ack` | adapter → subscribers | 1 | **No** | adapter publishes; operators/integrations subscribe | No; may disclose request IDs and state only. |
| `thunderdome/status/runtime` | control service/adapter → subscribers | 1 | **No** | trusted status producer publishes; operators subscribe | No; redact controller and filesystem details. |

Command topics must not be retained: a broker reconnect must never replay an old override. Status may be republished after reconnect but must not expose sensitive server configuration.

## Override command

Validate the JSON envelope against `schemas/mqtt-override-v1.schema.json` before adapter processing. Example:

```json
{
  "version": 1,
  "request_id": "visitor-123",
  "effect": "Twinkle",
  "parameters": {
    "mode": "random",
    "density": 0.05
  },
  "duration_seconds": 15,
  "priority": 10
}
```

`version`, `request_id`, `effect`, `parameters`, and `duration_seconds` are required. `priority` defaults to `0`; its v1 range is `0` through `100`. `duration_seconds` must be greater than zero and no more than `3600`. Request IDs are 1–128 printable identifier characters (`A-Z`, `a-z`, `0-9`, `.`, `_`, `:` and `-`). The UTF-8 payload limit is **16 KiB**.

The envelope rejects unknown top-level fields. `parameters` intentionally remains an object in the transport schema: the adapter must validate it with the existing server effect schema after decoding. It must reject:

- unknown effects and effects outside the deployment allow-list;
- `auto` (v1 MQTT override effects must be non-auto);
- unknown effect parameters;
- runtime-classified fields such as `brightness`, `fps`, and `exclude_tail`;
- non-finite, malformed, or out-of-range values;
- controller addresses, output modes, DDP configuration, simulator URLs, geometry/position paths, filesystem paths, credentials, or any envelope field not in the v1 schema.

The adapter creates `RuntimeCommand(source=CommandSource.MQTT, action=APPLY_OVERRIDE, output=None, ...)`. `output=None` is mandatory so the coordinator inherits the server-owned baseline output. The adapter must not issue `SET_BASELINE`, `RESTART_BASELINE`, or `STOP_ALL`.

### Idempotency, rate, and reconnect behavior

The adapter maintains a bounded TTL cache of completed `request_id` values. Repeated identical IDs return the original acknowledgement and do not restart the worker. Reuse of an ID with a different body is rejected as invalid. The implementation must rate-limit commands per authenticated publisher; `rate_limited` is acknowledged instead of queuing work.

For a burst of distinct commands, latest-message-wins applies only through the coordinator: equal-priority newer overrides replace the active override; lower priority is rejected. The adapter must not queue stale commands. Broker reconnect must resubscribe to the two command topics, publish/refresh sanitized runtime status, and never replay retained command messages. All parsing, validation, coordinator calls, and any blocking work must run outside the MQTT network callback; the callback should enqueue bounded work only.

## Cancel command

Validate `schemas/mqtt-cancel-v1.schema.json`. A v1 cancel identifies the original `request_id` and may include an optional `reason` for audit display. The adapter may cancel only an active MQTT-owned override with the matching request ID; otherwise it returns `no_active_override` or `not_authorized`. Browser cancellation remains available through the existing REST control path.

## Acknowledgements

Publish an acknowledgement to `thunderdome/status/ack` for every syntactically processable command, using `schemas/mqtt-ack-v1.schema.json`. The payload is stable, redacted, and does not include controller configuration, network addresses, paths, raw exception traces, or DDP details.

| `status` | When emitted | `accepted` |
|---|---|---:|
| `accepted` | Coordinator accepted command | true |
| `malformed_json` | Payload cannot decode as JSON | false |
| `unknown_effect` | Effect absent or not allowed | false |
| `invalid_parameter` | Schema or runtime-field validation failed | false |
| `invalid_duration` | Missing, non-positive, or over-limit duration | false |
| `lower_priority` | Active override has higher priority | false |
| `unavailable_control_service` | Coordinator/service cannot accept work | false |
| `rate_limited` | Publisher exceeds configured rate | false |

Example:

```json
{
  "version": 1,
  "request_id": "visitor-123",
  "accepted": false,
  "status": "lower_priority",
  "message": "active override has higher priority",
  "timestamp": "2026-07-18T18:00:00Z"
}
```

`message` is a bounded operator-facing explanation, never a raw server error. A successful acknowledgement may include `expires_at` and the accepted `priority`. Runtime status is a separate sanitized publication and is not a substitute for an acknowledgement.