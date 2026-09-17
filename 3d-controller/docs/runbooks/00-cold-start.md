# 00 — Cold start: remember nothing
**Position:** Master checklist
**Previous:** None — this is the starting point.

**Use this when:** You return after a long gap, or the current system state is unknown.
**Prerequisite:** A checkout of the Thunderdome repository and a Linux machine. If the host was rebuilt, start with [Controller Host](../setup-and-recovery/controller-host.md).
**Ends when:** The system has either reached normal operation or stopped at a named failed checkpoint.
**Next:** Begin with Step 1 below; do not skip to physical output.

## Main sequence

```text
00 Cold Start   ← YOU ARE HERE
   ↓
01 Software + Simulator
   ↓
02 Physical Dome Startup
   ↓
03 First Light + DDP
   ↓
04 Normal Operation
   ↓
05 Shutdown
```

This document is a master checklist, not a second copy of the procedures. Each phase has one authoritative runbook.

## Step 1 — prove the software

- [ ] Follow [01 — Software and simulator](01-software-and-simulator.md) from its first step through its clean stop.
- [ ] Do not continue until it displays:

> ✅ **SOFTWARE CONTROLLER PROVEN**
>
> Python, installation, geometry, routes, positions, effects, simulator service, browser rendering, and live local frame streaming work. No physical WLED/DDP output was required.

**If it fails:** Use [troubleshooting](../troubleshooting.md), then return to the failed step in 01. Do not troubleshoot physical DDP yet.

## Step 2 — prove physical readiness

- [ ] Follow [02 — Physical dome startup](02-physical-dome-startup.md).
- [ ] Do not continue until it displays:

> ✅ **FIVE CONTROLLERS READY**
>
> The local controller configuration is valid, the five recorded WLED addresses are reachable, and power/current settings have been checked before physical output.

**If it fails:** Use [troubleshooting](../troubleshooting.md), then return to the failed step in 02. Do not send a physical effect.

## Step 3 — prove physical mapping

- [ ] Follow [03 — First light and DDP](03-first-light-and-ddp.md).
- [ ] Do not continue until it displays:

> ✅ **PHYSICAL MAPPING PROVEN**
>
> The five responding WLED devices have been matched to the expected controller/string rows, and a whole-dome effect has completed or been stopped cleanly.

**If it fails:** Use [troubleshooting](../troubleshooting.md), then repeat 03 after correcting the fault.

## Step 4 — operate

- [ ] Follow [04 — Normal operation](04-normal-operation.md).
- [ ] Choose `--output simulator`, `--output ddp`, or `--output both` deliberately. Physical output is never implied by the simulator path.

## Step 5 — stop

- [ ] Follow [05 — Shutdown](05-shutdown.md) at the end of the session.

## Shortcuts after the system is known-good

- Normal event: [04 — Normal operation](04-normal-operation.md) → [05 — Shutdown](05-shutdown.md)
- WLED reset/replacement: [WLED Controller](../setup-and-recovery/wled-controller.md) → [02 — Physical dome startup](02-physical-dome-startup.md) → 03 → 04 → 05
- Controller-host rebuild: [Controller Host](../setup-and-recovery/controller-host.md) → [01 — Software and simulator](01-software-and-simulator.md) → 02 → 03 → 04 → 05
