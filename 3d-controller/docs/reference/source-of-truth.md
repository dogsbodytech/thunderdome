# Source of truth

Use this order when facts disagree.

## Software behaviour

1. Current Python code.
2. CLI parser and `--help` output.
3. Tests.
4. Controller documentation.

This refactor did not change code, tests, configuration, geometry, routes, simulator assets, firmware, or MQTT implementation.

## Geometry

`geometry/thunderdome_geometry.json` is authoritative for structural geometry, coordinates, hubs, spars, and H061. `assets/blender/thunderdome_3v_5_8_scaled.blend` is the editable model source.

## Routes

`geometry/routes/string_routes.json` is authoritative for ordered hub traversal, controller/string allocation, and global LED ranges. Do not create a historical Markdown route map or infer routes by symmetry.

## Positions

`geometry/generated/led_positions_3d.json` is generated from geometry and routes. It is derived data and intentionally ignored. Regenerate it with:

```bash
thunderdome positions generate
thunderdome positions validate
```

## Physical installation

Use current repository evidence where available. The public wider-project documents are useful physical references but not software behaviour authority:

- [Dome.md](https://github.com/dogsbodytech/thunderdome/blob/main/Dome.md)
- [Lighting.md](https://github.com/dogsbodytech/thunderdome/blob/main/Lighting.md)
- [Software.md](https://github.com/dogsbodytech/thunderdome/blob/main/Software.md)
- [WLED exports](https://github.com/dogsbodytech/thunderdome/tree/main/lighting)

## Important conflict resolved

The public Lighting document describes Controller 1 as a WLED “main controller” with four virtual remote outputs. The current Python controller source and local controller schema instead implement five direct DDP destinations, each receiving its own 1,000-pixel slice. The direct fan-out path is the active Python authority. The old WLED relay arrangement is retained only as historical installation context in [WLED and DDP](wled-and-ddp.md).

The public Lighting document also records network infrastructure details and an installation SSID. This component repeats only the five deployed controller addresses and DDP port in operator references. Other network details remain historical context unless freshly confirmed.

## Facts not currently captured

- Controller-host hostname/IP: **NOT CURRENTLY CAPTURED**.
- Current router/AP, gateway, subnet, DHCP, and Wi-Fi details: **NOT CURRENTLY CAPTURED** as live operator facts.
- Physical mains/PSU isolation and shutdown procedure: **NOT CURRENTLY CAPTURED**.
- Verified current WLED state/configuration for each deployed device: **NOT CURRENTLY CAPTURED**.
- Exact approved WLED restore/import UI sequence: **NOT CURRENTLY CAPTURED**.

Do not fill these gaps with guessed values. Use [troubleshooting](../troubleshooting.md) and the site/operator's approved physical procedure.
