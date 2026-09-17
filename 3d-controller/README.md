# Thunderdome 3D controller

The 3D controller turns the dome's tracked geometry and LED routes into spatial RGB animation. Python renders one logical frame for **5,000 LEDs**, splits it into five 1,000-LED controller frames, and sends those frames directly to five WLED devices with DDP over UDP.

The safe place to start is the local simulator. You can prove the software without powering the dome, contacting WLED, or sending DDP.

## Start here

**I have forgotten how this works:** [Start here](docs/START-HERE.md)

That page leads to:

1. [Cold start](docs/runbooks/cold-start.md) — the complete “remember nothing” path.
2. [Software and simulator](docs/runbooks/software-and-simulator.md) — install and see a moving browser effect without hardware.
3. [Physical dome startup](docs/runbooks/physical-dome-startup.md) — the explicit boundary where WLED and physical DDP begin.
4. [First light and DDP](docs/runbooks/first-light-and-ddp.md) — layered commissioning and string identification.
5. [Normal operation](docs/runbooks/normal-operation.md) and [shutdown](docs/runbooks/shutdown.md) — routine event use.

Do not start with physical output. The simulator is the software milestone.

## What does what?

```text
geometry JSON + structured routes
              |
              v
     Python position generation
              |
              v
     Python effects render 5,000 RGB pixels
              |
       split by global range
       /       |       \\
      v        v        v
   WLED 1   WLED 2   ... WLED 5
      |        |        |
   string 1 string 2 ... string 5
```

- **Python controller:** geometry, routes, XYZ positions, effects, and the RGB value for every physical LED.
- **WLED:** LED output/GPIO, chipset and colour order, LED count, network, power/current configuration, realtime state, and DDP reception.
- **DDP:** the transport carrying Python-rendered RGB8 pixels to WLED. When an effect is run with `--output ddp`, WLED is not calculating that effect.

The current Python path addresses all five WLED devices directly. Controller 1 is not a relay or master for application DDP.

## The important files

| Purpose | File |
| --- | --- |
| Structural geometry authority | `geometry/thunderdome_geometry.json` |
| LED traversal and allocation authority | `geometry/routes/string_routes.json` |
| Derived positions (generated, ignored) | `geometry/generated/led_positions_3d.json` |
| Local runtime controller configuration | `config/controllers.json` |
| Configuration template | `config/controllers.example.json` |
| Python package and CLI | `controller/thunderdome/` |
| Local simulator assets | `simulator/static/` |
| Tests | `controller/tests/` |

Generated positions are derived data. A fresh checkout may not contain them; [the simulator runbook](docs/runbooks/software-and-simulator.md) generates and validates them.

## Physical controller map

The runtime uses zero-based internal `string_id` values, while people use controller/string numbers 1–5. Keep that distinction visible:

| Human controller/string | WLED address | Internal `string_id` | Start hub | Global frame range | Local range |
| ---: | --- | ---: | --- | --- | --- |
| 1 | `192.168.12.10` | 0 | H032 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | H033 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | H034 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | H035 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | H031 | 4000..4999 | 0..999 |

The DDP destination is UDP port `4048`. See [controller network reference](docs/reference/controller-network.md) and [physical installation reference](docs/reference/physical-installation.md).

## Technical reference

- [Architecture](docs/architecture.md)
- [WLED and DDP](docs/reference/wled-and-ddp.md)
- [Source of truth](docs/reference/source-of-truth.md)
- [Geometry](docs/geometry.md)
- [Routes](docs/route-capture.md)
- [Effects](docs/effects.md)
- [Simulator technical reference](docs/simulator.md)
- [Control service](docs/control-service.md) and [REST API](docs/api-rest.md)
- [MQTT contract](docs/mqtt-integration-spec.md) — future adapter; not currently connected
- [xLights export](docs/xlights.md)
- [Troubleshooting](docs/troubleshooting.md)

## External physical references

The wider public repository contains the detailed installation material. The controller-local references link to it rather than copying it:

- [Dome construction](https://github.com/dogsbodytech/thunderdome/blob/main/Dome.md)
- [Lighting and power](https://github.com/dogsbodytech/thunderdome/blob/main/Lighting.md)
- [Project software overview](https://github.com/dogsbodytech/thunderdome/blob/main/Software.md)

## Scope

This directory documents and operates the Python controller, simulator, WLED/DDP boundary, and controller-specific commissioning. It does not document whole-project deployment, physical electrical isolation, router administration, or DNS cutover. Where this component lacks a fact, it says **NOT CURRENTLY CAPTURED** instead of guessing.
