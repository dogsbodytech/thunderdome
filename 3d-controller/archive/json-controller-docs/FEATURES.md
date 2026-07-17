# Feature Overview

This project is a lightweight WLED JSON API exploration and control tool for a human operator experimenting with a WLED-controlled LED dome.

## What it can do

- Explore WLED JSON endpoints with `explore_wled.py`:
  - `/json`
  - `/json/state`
  - `/json/info`
  - `/json/eff`
  - `/json/pal`
- Read controller state, info, effects, and palettes.
- Turn LEDs on, off, or toggle power.
- Set global brightness.
- Set solid RGB colour.
- Set WLED effect by numeric ID.
- Set WLED palette by numeric ID.
- Apply colour/effect/palette commands to a specific WLED segment ID.
- Send raw JSON state payloads for API exploration.
- Use configurable target URL via `WLED_BASE_URL` or `--base-url`.
- Send realtime RGB frames to WLED over DDP/UDP port 4048.
- Use DDP clear, solid, single-pixel, and range tests for physical index validation.
- Use configurable DDP packet chunking, defaulting to 480 LEDs per packet.
- Use configurable HTTP timeout via `--timeout`.
- Save favourite effects in a local JSON config file.
- List, add, remove, and clear favourite effects.
- Resolve favourite effect names from `/json/eff` when adding by ID.
- Search effects and palettes with simple case-insensitive substring filters.
- Configure the saved default favourites cycle interval.
- Cycle favourite effects once or in a Ctrl-C-stoppable loop.
- Override favourite cycle interval from the CLI.
- Apply favourite cycling globally or to a specific segment.
- Validate WLED 2D `ledmap.json` files.
- Upload ledmaps to WLED `/edit` as `ledmap.json`, with dry-run and optional reboot.
- Summarize generated `led_positions_2d.json` position files.
- Run a static top-down clock-frame mapping check.
- Run the preferred 10-pitch-wide straight physical clock-hand sweep from `led_positions_2d.json` without requiring `ledmap.json` upload, either once, for a fixed repeat count, or continuously with Ctrl-C cleanup; transport can be HTTP JSON `seg.i` or DDP full-frame UDP.
- Run a rotating top-down clock-hand mapping test using sparse `seg.i` updates.
- Handle common errors with clear messages:
  - missing base URL
  - controller unavailable
  - timeout
  - HTTP errors
  - invalid JSON
  - invalid brightness/RGB/effect/palette ranges

## Important project choices

- Standard library only: no package install is required.
- No hard-coded controller IP in code.
- Segment payload examples use list form: `{"seg":[{"id":0,...}]}`.
- Default favourites file: `./wled_favourites.json`.
- Python 3.11 compatible.

## Intentionally out of scope

- Physical dome mapping.
- Ring, panel, face, or layout abstractions.
- High-FPS animation.
- DDP/realtime protocol implementation.
- WLED configuration management.
- Destructive preset save/delete workflows.
- Controller reboot commands.
- Managing WLED firmware or the web UI.

Mapping and realtime animation should be separate projects layered on top of this basic WLED JSON control tool.
