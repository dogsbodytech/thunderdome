# Start here

> **Use this page if you have not used Thunderdome for two years and remember virtually nothing.**

The 3D controller is the software that renders spatial effects for 5,000 LEDs. It is safe to try without the dome: the simulator is local and its normal output cannot contact WLED.

## Choose a path

```text
Want to prove the software works?
    -> Software and simulator

Simulator already works and you want the real dome?
    -> Physical dome startup

Need to prove the first physical pixel and string mapping?
    -> First light and DDP

A WLED controller was reset or replaced?
    -> WLED commissioning

The controller computer was rebuilt or lost?
    -> Rebuild controller host

Something is broken?
    -> Troubleshooting

Need technical internals or contributor contracts?
    -> Technical reference
```

| Need | Go to |
| --- | --- |
| Complete forgotten-everything procedure | [Cold start](runbooks/cold-start.md) |
| Blank Linux machine to moving browser simulator | [Software and simulator](runbooks/software-and-simulator.md) |
| Simulator success to physical readiness | [Physical dome startup](runbooks/physical-dome-startup.md) |
| First light, one controller, then all five strings | [First light and DDP](runbooks/first-light-and-ddp.md) |
| Recommission a WLED device | [WLED commissioning](commissioning/wled-controller.md) |
| Rebuild only this controller host | [Rebuild controller host](commissioning/rebuild-controller-host.md) |
| Routine event operation | [Normal operation](runbooks/normal-operation.md) |
| Stop software cleanly | [Shutdown](runbooks/shutdown.md) |
| Diagnose a failure | [Troubleshooting](troubleshooting.md) |
| Look up addresses and mapping | [Controller network](reference/controller-network.md) |
| Understand Python, WLED and DDP | [WLED and DDP](reference/wled-and-ddp.md) |
| Resolve conflicting facts | [Source of truth](reference/source-of-truth.md) |
| Contributor/API/MQTT details | [Technical reference index](../README.md#technical-reference) |

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

Only after that checkpoint should you open [Physical dome startup](runbooks/physical-dome-startup.md).
