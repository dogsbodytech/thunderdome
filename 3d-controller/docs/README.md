# Start here

> **Use this page if you have not used Thunderdome for two years and remember virtually nothing.**

The 3D controller is the software that renders spatial effects for 5,000 LEDs. It is safe to try without the dome: the simulator is local and its normal output cannot contact WLED.

Unless a runbook's entry step says otherwise, shell commands assume you are in the `3d-controller/` directory of your cloned Thunderdome repository and have activated `.venv` where required.

> **If you remember nothing or do not know the current system state: start with [00 — Cold Start](runbooks/00-cold-start.md). Do not skip ahead.**

## Choose a path

```text
Want to prove the software works?
    -> [01 — Software and simulator](runbooks/01-software-and-simulator.md)

Simulator already works and you want the real dome?
    -> [02 — Physical dome startup](runbooks/02-physical-dome-startup.md)

Need to prove the first physical pixel and string mapping?
    -> [03 — First light and DDP](runbooks/03-first-light-and-ddp.md)

A WLED controller was reset or replaced?
    -> [Setup and Recovery: WLED Controller](setup-and-recovery/wled-controller.md)

The controller computer was rebuilt or lost?
    -> [Setup and Recovery: Controller Host](setup-and-recovery/controller-host.md)

Something is broken?
    -> [Troubleshooting](troubleshooting.md)

Need technical internals or contributor contracts?
    -> [Technical documentation](technical/README.md)
```

| Need | Go to |
| --- | --- |
| Complete forgotten-everything procedure | [00 — Cold start](runbooks/00-cold-start.md) |
| Blank Linux machine to moving browser simulator | [01 — Software and simulator](runbooks/01-software-and-simulator.md) |
| Simulator success to physical readiness | [02 — Physical dome startup](runbooks/02-physical-dome-startup.md) |
| First light, one controller, then all five strings | [03 — First light and DDP](runbooks/03-first-light-and-ddp.md) |
| Recommission a WLED device | [Setup and Recovery: WLED Controller](setup-and-recovery/wled-controller.md) |
| Rebuild only this controller host | [Setup and Recovery: Controller Host](setup-and-recovery/controller-host.md) |
| Routine event operation | [04 — Normal operation](runbooks/04-normal-operation.md) |
| Stop software cleanly | [05 — Shutdown](runbooks/05-shutdown.md) |
| Diagnose a failure | [Troubleshooting](troubleshooting.md) |
| Look up addresses and mapping | [Controller network](reference/controller-network.md) |
| Understand Python, WLED and DDP | [WLED and DDP](reference/wled-and-ddp.md) |
| Resolve conflicting facts | [Source of truth](reference/source-of-truth.md) |
| Contributor/API/MQTT details | [Technical documentation index](technical/README.md) |

## The safe milestone

Run the simulator path first. It proves Python, package installation, geometry, routes, positions, effects, the local server, live frame streaming, and browser rendering. It does **not** prove power, physical networking, WLED configuration, DDP delivery to hardware, or string identity.

> ✅ **SOFTWARE CONTROLLER PROVEN**
>
> The Python controller, geometry, routes, positions, effect renderer, simulator, and browser live stream work. No physical WLED/DDP output was required.

The normal journey is:

```text
Install
  |
Validate geometry, routes, positions
  |
Moving local simulator
  |
✅ SOFTWARE CONTROLLER PROVEN
  |
⚠️ Physical readiness: power, network, WLED
  |
First physical light and mapping
  |
Normal operation
```

Only after that checkpoint should you open [02 — Physical dome startup](runbooks/02-physical-dome-startup.md).

## Main sequence

```text
00 Cold Start
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

For the sequence table and recovery shortcuts, open the [runbook index](runbooks/README.md).
