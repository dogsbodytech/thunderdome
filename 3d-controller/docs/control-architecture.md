# Control architecture

This document is the authority for contributors connecting new control sources to Thunderdome. It documents the existing control system; it does not add an MQTT client.

```text
Browser / REST / MQTT adapter
        ↓
Validation
        ↓
RuntimeCoordinator
        ↓
Baseline + optional temporary override
        ↓
FrameRuntime
        ↓
Simulator / DDP / both
```

## Ownership and authority

- The browser operator (including browser-started Auto mode) owns the **baseline**.
- An MQTT adapter creates **temporary overrides only**. It must never issue `SET_BASELINE`.
- `RuntimeCoordinator` is the single arbitration authority. An adapter must not maintain a second queue, priority scheme, renderer, or worker.
- MQTT commands retain `CommandSource.MQTT`; adapters must not relabel them as browser or CLI commands.
- An override inherits the baseline's server-selected output. MQTT may not supply an output mode, controller address, DDP setting, simulator URL, geometry path, position path, or filesystem path.
- A browser operator may cancel an active MQTT override through the existing cancel-override API. Cancellation restarts the baseline from its beginning.

## Lifecycle

A baseline is the normal display. It can be a single effect or Auto. `APPLY_OVERRIDE` replaces only the effective display, preserving the baseline. The coordinator accepts a higher-priority override and accepts an equal-priority newer override; it rejects a lower-priority override and never queues it. An accepted override has a positive expiry. Expiry or cancellation removes the override and restarts the preserved baseline from time zero.

`FrameRuntime` owns the one cancellable rendering worker and the chosen sink set. Rendering and sink work do not run in an HTTP or MQTT network callback. The runtime reports failures through its status state; an adapter must acknowledge an unavailable/failed service rather than attempting direct rendering or hardware control.

## Security boundary

The adapter is an untrusted ingress boundary. It validates its MQTT envelope, then submits an in-memory `RuntimeCommand` to the existing coordinator. It must use the existing effect schemas for effect parameters and reject runtime-classified fields. Controller configuration, controller hostnames, DDP port/chunk settings, credentials, paths, and exception internals are server-owned and must never appear in MQTT messages or acknowledgements.

See [Runtime command contract](runtime-command-contract.md) for coordinator semantics and [MQTT integration specification](mqtt-integration-spec.md) for the adapter contract.