# Architecture

## Active data flow

```text
tracked geometry
      + structured routes
              |
              v
      generated XYZ positions
              |
              v
       Python effect renderer
              |
      one logical 5,000-pixel RGB frame
              |
       split by fixed ranges
       /       |        |        |       \\
      v        v        v        v        v
   WLED 1   WLED 2   WLED 3   WLED 4   WLED 5
      |        |        |        |        |
  string 1 string 2 string 3 string 4 string 5
```

The authoritative sequence is **geometry → structured routes → generated XYZ positions → effects → RGB frame → direct DDP fan-out → WLED**.

- `geometry/thunderdome_geometry.json` holds structural coordinates.
- `geometry/routes/string_routes.json` holds ordered hub routes and global allocation.
- `geometry/generated/led_positions_3d.json` is derived and regenerated locally.
- Python renders all 5,000 RGB pixels in physical route order.
- Five direct DDP destinations receive local 1,000-pixel slices.

WLED HTTP is secondary controller management and fallback/native-effect support. WLED's 2D ledmap and old coordinate experiments are not active mapping authorities.

## Simulator and frame delivery

`thunderdome simulator serve` validates compatible geometry, routes, and positions, serves the offline browser, and accepts local live frames. It sends no WLED HTTP requests and no UDP/DDP packets. Effects select a sink:

- `simulator` — local binary WebSocket preview;
- `ddp` — direct physical DDP;
- `both` — the same logical frame to both;
- `null` — render and discard.

The simulator has static geometry APIs plus `/ws/producer` and `/ws/viewer` for live frames. It uses bundled Three.js r160 assets; no Node.js, npm, CDN, or remote browser asset is required at runtime.

## Runtime scheduling

`run_frame_loop` uses a monotonic scheduler for one-shot, held, finite-duration, and finite-loop output. One DDP session reuses its UDP socket(s) for the session. Ctrl+C cancels the loop and closes sinks.

Spatial effects use generated XYZ records. `clock-hand` uses H061's XY coordinate; `expanding-rings` uses true XYZ Euclidean distance; `height-wave` uses selected Z bounds; procedural effects use the same index-aligned context. Tails are included by default and removed only with `--exclude-tail`.

## Brightness and WLED state

Normal operation uses brightness **255**, the maximum valid 8-bit value. Valid values are `0..255`; `256` is invalid. Before live effect DDP opens, the controller sets enabled WLED master brightness to `255`. This HTTP state call can affect WLED on/off state; it does not set current limits. Physical power/current readiness remains an operator check.

## Control service

`thunderdome control serve` hosts the simulator and local REST/runtime coordinator. It has one worker and one sink set, with browser baseline and temporary override arbitration. The safe default is local simulator output. Physical capability exists only when both `--controllers FILE` and `--allow-live-control` are supplied at startup. See [control-service.md](control-service.md), [api-rest.md](api-rest.md), and [runtime-command-contract.md](runtime-command-contract.md).

## Effect registry and Auto

The registry aligns standalone effect names, schemas, saved defaults, and Auto playlists. `effect auto` loads spatial context once, reuses one sink/session, and crossfades full-brightness source frames before applying the requested global brightness once. It runs continuously unless `--cycles` or `--duration` is supplied.
