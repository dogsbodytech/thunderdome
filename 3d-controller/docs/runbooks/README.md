# Runbooks

This directory is the operator sequence. Read the numbered documents in order when the system state is unknown; do not use the technical documents as a substitute for the next operational step.

## Choose the sequence

### I remember nothing / state is unknown

```text
00 → 01 → 02 → 03 → 04 → 05
```

Start with [00 — Cold start](00-cold-start.md). It is the master checklist and links to the one authoritative procedure for each phase.

### The installation is known-good and this is normal event use

```text
04 → 05
```

Use [04 — Normal operation](04-normal-operation.md), then [05 — Shutdown](05-shutdown.md). Repeat first-light testing only after a change, rebuild, or unexplained physical fault.

### The controller host was rebuilt

```text
Setup & Recovery: [Controller Host](../setup-and-recovery/controller-host.md)
    ↓
01 → 02 → 03 → 04 → 05
```

### A WLED controller was reset or replaced

```text
Setup & Recovery: [WLED Controller](../setup-and-recovery/wled-controller.md)
    ↓
02 → 03 → 04 → 05
```

## Main sequence

| Order | Runbook | Purpose | Required when |
| ---: | --- | --- | --- |
| 00 | [Cold start](00-cold-start.md) | Master checklist | Forgotten or unknown state |
| 01 | [Software + simulator](01-software-and-simulator.md) | Prove software safely | New, rebuilt, or unknown system |
| 02 | [Physical dome startup](02-physical-dome-startup.md) | Prove WLED/network readiness | Before physical setup |
| 03 | [First light + DDP](03-first-light-and-ddp.md) | Prove physical mapping | After rebuild, change, or unknown state |
| 04 | [Normal operation](04-normal-operation.md) | Routine use | Every normal session |
| 05 | [Shutdown](05-shutdown.md) | Stop cleanly | End of session |

## Convention

Unless a runbook's entry step says otherwise, shell commands assume you are in the `3d-controller/` directory of your cloned Thunderdome repository and have activated `.venv` where required.

For architecture, protocol details, and contributor contracts, use the [technical documentation index](../technical/README.md). For factual lookups, use the [reference index](../reference/README.md). For faults, use [troubleshooting](../troubleshooting.md), then return to the numbered checkpoint named there.
