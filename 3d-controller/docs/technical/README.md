# Technical documentation

These documents describe implementation, protocols, architecture, contributor contracts, and historical decisions. Operators should start with the [runbook index](../runbooks/README.md), not here.

| Topic | Documents |
| --- | --- |
| Architecture and control | [Architecture](architecture.md), [Control architecture](control-architecture.md), [Control service](control-service.md) |
| Runtime interfaces | [REST API](api-rest.md), [Runtime command contract](runtime-command-contract.md), [MQTT contract](mqtt-integration-spec.md) |
| Rendering and transport | [Effects](effects.md), [DDP](ddp.md), [Simulator](simulator.md) |
| Geometry and exports | [Geometry](geometry.md), [Route capture](route-capture.md), [xLights](xlights.md) |
| Decisions and schemas | [ADRs](adr/0002-python-3d-rendering-over-wled-ledmaps.md), [MQTT schemas](schemas/mqtt-override-v1.schema.json) |

Operator-facing factual lookups remain in [Reference](../reference/README.md). Fault recovery remains in [Troubleshooting](../troubleshooting.md).
