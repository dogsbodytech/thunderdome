# Codex prompt: add WLED map upload and clock-face test pattern to JSON controller app

We are working in the Thunderdome JSON controller app repository. The current app already talks to WLED controllers and includes commands such as effects, palettes, favourites, and JSON/API control. Extend the app to support uploading WLED `ledmap.json` files and running a top-down clock-face mapping test pattern.

## Context

Project: Thunderdome LED dome.

Physical layout:

- Dome diameter: 6m.
- Top-down map target: square 2D grid.
- Current practical map size: 300 x 300.
- LED pitch: 30mm.
- 5 LED strings.
- 1000 LEDs per string.
- Total physical LEDs: 5000.
- Approximately 933 LEDs per string are on the dome spars.
- Approximately 67 LEDs per string hang down from the top centre of the dome.
- Strings start at the centre of the side/pentagon shown in the repo layout.
- Strings follow the descending label path `24, 23, 22, ... 1`.
- Strings end at the top-centre pentagon.
- The final 2m tail hangs down from the top centre.

Generated map package:

- Use the 300 x 300 generated files from `wled_map_top_centre_tail_300_v4`.
- Primary map file to upload/test: `ledmap_on_dome.json`.
- Position source for custom test patterns: `led_positions_2d.json`.

Important WLED details:

- WLED loads mapping from a file named `ledmap.json` in the device filesystem.
- WLED supports `/edit` for file upload.
- WLED supports JSON API POSTs to `/json/state`.
- WLED supports per-segment individual LED control through `seg.i`.
- For individual LED control, prefer hex colours such as `"FF0000"` over RGB arrays because they are smaller.
- Do not send several WLED JSON requests in parallel; send sequentially and wait for each response.
- For large individual LED updates, chunk requests to avoid command buffer/memory issues.

## New feature goals

Add a new top-level CLI command group, probably called `mapping`, with subcommands:

```bash
python3 wledctl.py mapping validate ./ledmap_on_dome.json
python3 wledctl.py mapping upload ./ledmap_on_dome.json --host 192.168.x.x
python3 wledctl.py mapping info ./led_positions_2d.json
python3 wledctl.py mapping clock-test ./led_positions_2d.json --host 192.168.x.x
```

Use the existing project style, argument parsing, logging/printing conventions, and HTTP client patterns. Do not introduce heavy dependencies unless already used in the project.

## Command: mapping validate

Validate a WLED ledmap JSON file.

Checks:

1. JSON parses successfully.
2. Has `map` array.
3. Has `width` and `height` if this is a 2D map.
4. `width * height == len(map)`.
5. Values are integers.
6. Values are either `-1` or valid LED indexes.
7. No duplicated physical LED indexes, except `-1`.
8. Report:
   - width
   - height
   - total cells
   - mapped LEDs
   - blank cells
   - minimum LED index
   - maximum LED index
   - duplicate count

For the current 300 x 300 map, expected shape:

- width: 300
- height: 300
- map entries: 90000
- mapped on-dome LEDs: 4665
- blank cells: 85335

## Command: mapping upload

Upload a selected ledmap file to a WLED controller as `ledmap.json`.

Requirements:

1. Validate the file before upload.
2. Minify the JSON before upload to reduce file size.
3. Upload to WLED using the same mechanism as the web `/edit` file upload.
4. Always upload using the remote filename `ledmap.json`, even if the local filename is different.
5. Print a warning that WLED should be rebooted after upload.
6. Provide an optional `--reboot` flag that POSTs `{"rb": true}` to `/json/state` after successful upload.
7. Support `--dry-run` to validate and show upload size without sending anything.
8. Handle HTTP errors cleanly.
9. If upload via `/edit` fails, print instructions for manual upload via `http://<host>/edit`.

Suggested UX:

```text
Validated ledmap_on_dome.json
Grid: 300 x 300
Mapped LEDs: 4665
Blank cells: 85335
Minified size: <n> bytes
Uploading to http://<host>/edit as ledmap.json...
Upload complete
Reboot WLED to apply the map
```

## Command: mapping info

Read `led_positions_2d.json` and print a concise summary:

- grid size
- dome diameter
- cell size
- number of strings
- LEDs per string
- on-dome LEDs
- tail LEDs
- path sequence
- top-centre grid coordinate

Also report position counts by `note` and by `on_dome_path`.

## Command: mapping clock-test

Implement an interactive/scheduled clock-face test pattern using `led_positions_2d.json` rather than relying on WLED effects.

Purpose:

Test whether the calculated top-down positions line up with the physical dome by sweeping a radial “second hand” around the dome.

Pattern behaviour:

- Centre point: top centre of the dome.
- In the 300 x 300 grid, the centre is expected to be around `[150, 150]`.
- A single radial hand rotates around the centre like a clock second hand.
- At each frame, LEDs close to the current ray are lit.
- Other LEDs are dimmed/off.
- Optional trailing/fade pixels behind the hand are useful but should be off by default initially.
- Only use LEDs where `on_dome_path == true` by default.
- Add `--include-tail` to include the hanging centre-tail LEDs, but default to excluding them.

Suggested options:

```bash
python3 wledctl.py mapping clock-test ./led_positions_2d.json \
  --host 192.168.x.x \
  --duration 60 \
  --fps 5 \
  --hand-width-deg 3 \
  --radius-min-mm 0 \
  --radius-max-mm 3000 \
  --hand-color FF0000 \
  --background-color 000000 \
  --brightness 64
```

Implementation detail:

For each LED position:

- Use `x_mm` and `y_mm` from `led_positions_2d.json`.
- Compute radius: `sqrt(x_mm^2 + y_mm^2)`.
- Compute angle: `atan2(y_mm, x_mm)`.
- For each frame, compute the hand angle.
- Angular distance should wrap at 0/360.
- If angular distance <= `hand_width_deg / 2`, light that LED.
- Otherwise set it to background/off.

Use sparse updates where possible:

- Track previous frame's lit LED set.
- New frame update should include LEDs that changed from off to on and on to off.
- Send `seg.i` sparse updates like `[led_index, "FF0000", led_index, "000000", ...]`.
- Chunk updates if payloads get too large.
- Send requests sequentially.

Before starting the animation:

1. POST brightness and on-state first:

```json
{"on": true, "bri": 64}
```

2. Clear all on-dome LEDs to background/off, preferably in safe chunks.
3. Then begin the frame loop.

After finishing:

- Clear the lit LEDs unless `--leave-on` is set.
- Provide Ctrl+C handling that tries to clear the current lit LEDs before exiting.

## Optional command: mapping clock-frame

Add a non-animated command for easier debugging:

```bash
python3 wledctl.py mapping clock-frame ./led_positions_2d.json --host 192.168.x.x --angle 90
```

This lights one static hand angle. This is useful for confirming orientation before running the animation.

Angles should be documented clearly. Suggested convention:

- 0 degrees = positive X/right/east.
- 90 degrees = positive Y/up/north in model coordinates.
- 180 degrees = negative X/left/west.
- 270 degrees = negative Y/down/south.

Add `--clock-convention` later if needed, but keep v1 simple.

## Tests

Add unit tests for:

1. ledmap validation success.
2. ledmap validation catches wrong dimensions.
3. ledmap validation catches duplicate LED indexes.
4. angle wrapping, e.g. 359 degrees vs 1 degree.
5. clock-frame LED selection.
6. sparse diff generation between frames.
7. chunking of `seg.i` payloads.

Use fake/mock HTTP clients; do not require a real WLED controller for tests.

## Documentation

Update README/QUICKSTART docs with:

- How to upload `ledmap_on_dome.json`.
- How to manually upload through `/edit` as a fallback.
- How to reboot/apply the map.
- How to run a static clock-frame test.
- How to run the rotating clock-test.
- Safety notes about brightness/current draw.

## Safety/defaults

Use conservative defaults:

- Brightness: 64 or lower.
- FPS: 5.
- Duration: 60 seconds.
- Exclude tail LEDs by default.
- Hand colour: red.
- Background: off.
- Do not reboot automatically unless `--reboot` is supplied.

## Deliverables

Please implement the feature, update docs, and add tests. After implementation, run the project test suite and show the commands and results.
