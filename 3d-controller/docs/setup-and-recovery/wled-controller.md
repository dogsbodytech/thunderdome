# WLED Controller — setup, reset, and replacement recovery

## Purpose

Use this when one of the five WLED controllers has been factory-reset, replaced, or is otherwise no longer known-good. This documents what the Python controller expects; it is not a general WLED installation manual.

> ⚠️ **PHYSICAL CHANGE**
>
> WLED reads and configuration changes affect the physical LED installation. Confirm the correct device and its power/current configuration before enabling output.

## Known hardware evidence

The wider public project records:

- QuinLED-Dig-Uno controllers: four standard units and one Ethernet-capable unit.
- Five 12 V, 100 W power supplies, one per 1,000-pixel string.
- WS2815/WS2818-described 12 V RGB pixels, 30 mm pitch, 1,000 pixels per string.
- Firmware asset: [`lighting/WLED_16.0.0_Dig-Uno-V3.bin`](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/WLED_16.0.0_Dig-Uno-V3.bin).

The public export files are:

- [Controller 1](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/wled_cfg_Controller1.json)
- [Controller 2](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/wled_cfg_Controller2.json)
- [Controller 3](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/wled_cfg_Controller3.json)
- [Controller 4](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/wled_cfg_Controller4.json)
- [Controller 5](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/wled_cfg_Controller5.json)

The export filenames and firmware filename are repository evidence. They are not live proof of what is installed today.

## Rejoin the main sequence

After the replacement device matches the required settings and the local controller file validates, continue with [02 — Physical dome startup](../runbooks/02-physical-dome-startup.md), then [03 — First light and DDP](../runbooks/03-first-light-and-ddp.md), [04 — Normal operation](../runbooks/04-normal-operation.md), and [05 — Shutdown](../runbooks/05-shutdown.md).

## Settings the Python/DDP path depends on

Before first light, compare the replacement device with its corresponding known-good export and the current physical wiring. The relevant expectations are:

| Setting | Expected evidence/target |
| --- | --- |
| Device identity | QuinLED-Dig-Uno family; controller number must match the intended string. |
| Network address | See [controller network](../reference/controller-network.md). |
| LED count | 1,000 for controllers 2–5. The export records 5,000 on Controller 1 because it also contains historical virtual remote outputs; the Python path still addresses five direct 1,000-LED slices. |
| Data output | The exports record a local LED input on pin 16. Confirm the pin/output selection in the WLED UI for the installed board. |
| Pixel type/order | The exports record numeric WLED output fields (`type` 22 and `order` 1) for the local segment. Confirm their meaning in the installed WLED build rather than guessing from numbers. |
| Realtime/DDP | Realtime reception must be enabled and the device must accept RGB8 DDP on UDP/4048. The current Python controller is the authority for destination port and packet behaviour. |
| Power/current | Confirm the recorded power/current limit against the physical PSU, injection, fusing, and wiring before brightness `255`. Do not invent or copy a limit without checking the device and installation. |
| Colour/state | Test with a finite direct frame; do not assume the saved WLED effect is the Python spatial effect. |

The exports record a WLED `live` configuration with realtime enabled and a 25-second timeout. A timeout may let WLED leave realtime mode after a one-shot frame; held/finite application loops are documented in [DDP reference](../reference/wled-and-ddp.md).

## Controllers.json

Create the local runtime file from the tracked template:

```bash
cd 3d-controller
cp config/controllers.example.json config/controllers.json
```

`config/controllers.json` is ignored by Git because each installation supplies its own hosts. It must contain the fixed allocation below:

| Human controller | Address | `string_id` | Start hub | Global range | Local count |
| ---: | --- | ---: | --- | --- | ---: |
| 1 | `192.168.12.10` | 0 | H032 | 0..999 | 1,000 |
| 2 | `192.168.12.20` | 1 | H033 | 1000..1999 | 1,000 |
| 3 | `192.168.12.30` | 2 | H034 | 2000..2999 | 1,000 |
| 4 | `192.168.12.40` | 3 | H035 | 3000..3999 | 1,000 |
| 5 | `192.168.12.50` | 4 | H031 | 4000..4999 | 1,000 |

Validate before any physical command:

```bash
thunderdome controllers validate --controllers config/controllers.json
thunderdome controllers summary --controllers config/controllers.json
```

The runtime file is ignored so local addresses are not committed. The template is not a safe physical configuration until its host placeholders are replaced.

## Replacement procedure boundary

The repository proves the expected files and settings above, but it does not provide a verified universal WLED restore/import UI workflow. Do not invent one. Use the device's approved WLED/QuinLED procedure to flash or configure the controller, then compare the resulting state with the corresponding public export and run the controller-local checks below.

## Validate a replacement

1. Identify the physical unit and intended controller number.
2. Confirm its WLED HTTP endpoint at the address in the table.
3. Check LED count, output pin, colour order, realtime/DDP enablement, and power/current configuration.
4. Run `controllers validate` locally.
5. Run `controllers state --controllers config/controllers.json` to read all configured devices.
6. Run the layered [first-light and DDP](../runbooks/03-first-light-and-ddp.md) procedure.

Do not change `string_id`, route JSON, or geometry to accommodate a wiring or controller identity mistake.

## Secrets

The public exports contain credential-related fields and network metadata. This controller documentation deliberately does not reproduce Wi-Fi passwords, tokens, or export bodies. Obtain any restricted credentials through the site's approved secret-handling method.
