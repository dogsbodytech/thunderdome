# ADR 0001: MQTT as a temporary override adapter

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

Thunderdome already has one source-neutral control path: validated `RuntimeCommand` instances are arbitrated by `RuntimeCoordinator`, rendered by one `FrameRuntime` worker, and delivered to server-owned simulator/DDP sinks. External installations may need MQTT triggers without allowing an external publisher to own the normal display or physical hardware configuration.

## Decision

An MQTT integration is a temporary-override adapter into the existing coordinator.

- It submits only `APPLY_OVERRIDE` commands with `CommandSource.MQTT`.
- Browser/REST/Auto owns the baseline.
- MQTT override output is inherited from the baseline and remains server-controlled.
- MQTT overrides have coordinator priority and expiry semantics; expiry or cancellation restarts the baseline from time zero.
- The browser operator retains cancellation authority.
- MQTT envelope validation occurs before existing effect-schema validation. The adapter rejects runtime fields and sensitive transport/hardware/path fields.

## Rationale

This preserves one arbitration lock, one worker, one lifecycle model, and one audit/status surface. It lets an installation add transient interactive behavior without permitting a broker client to persistently replace the operator’s display or direct physical hardware.

## Consequences

- MQTT is intentionally unable to start Auto, replace a baseline, select output mode, provide controller addresses, or change DDP configuration.
- Adapter implementations must be non-blocking at the network callback boundary and must not render frames or send DDP themselves.
- Deployments need broker authentication, topic ACLs, rate limits, idempotency handling, and an effect allow-list.
- Existing REST/browser behavior and `RuntimeCoordinator` semantics remain the compatibility authority.

## Rejected alternatives

### MQTT owns the baseline

Rejected because retained/replayed broker messages could silently replace the operator display and because it would create competing ownership.

### MQTT controls hardware addresses or output transport

Rejected because controller configuration and live-output safety remain server-owned; exposing them would disclose sensitive topology and bypass local safety policy.

### Separate MQTT renderer

Rejected because it would create concurrent renderers/sinks and diverge from cancellation, failure, brightness, and geometry behavior.

### Second MQTT priority/arbitration system

Rejected because duplicate queues and locks create race conditions and make baseline restoration ambiguous. `RuntimeCoordinator` remains the sole authority.

## Compatibility expectations

MQTT v1 messages use the schemas and topic contract in [mqtt-integration-spec.md](../mqtt-integration-spec.md). Future adapters must preserve `CommandSource.MQTT`, request-ID acknowledgement behavior, baseline inheritance, and the no-controller-details boundary. They must not require changes to existing browser, REST, Auto, simulator, DDP, or renderer contracts.