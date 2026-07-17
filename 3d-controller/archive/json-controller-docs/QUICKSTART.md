# WLED JSON Controller Quickstart

This project is a small WLED JSON API exploration/control tool. It does **not** generate the physical dome map, but it can validate/upload generated WLED ledmaps and run low-FPS mapping test patterns.

## 1. Setup

```bash
cd /workspace/thunderdome/json-controller
export WLED_BASE_URL=http://192.168.12.11
```

The IP above is the current known controller. Do not hard-code it in scripts; use `WLED_BASE_URL` or `--base-url`.

If scripts are not executable:

```bash
chmod +x explore_wled.py wledctl.py
```

## 2. Check connectivity

```bash
python3 explore_wled.py --endpoint info
python3 wledctl.py info
python3 wledctl.py state
```

Useful full capture:

```bash
python3 explore_wled.py > wled-snapshot.json.txt
```

## 3. Safe first tests

Start dim. The real controller has 5000 LEDs, so full brightness can be intense and power-hungry.

```bash
python3 wledctl.py brightness 32
python3 wledctl.py on
python3 wledctl.py color 255 0 0
python3 wledctl.py color 0 255 0
python3 wledctl.py color 0 0 255
python3 wledctl.py off
```

Ask WLED v0.13+ to return updated state:

```bash
python3 wledctl.py on --return-state
python3 wledctl.py brightness 32 --return-state
```

## 4. Effects and palettes

List effects:

```bash
python3 wledctl.py effects
python3 wledctl.py effects --filter rainbow
```

Apply effects:

```bash
python3 wledctl.py effect 9
python3 wledctl.py segment 0 effect 9
```

List/apply palettes:

```bash
python3 wledctl.py palettes
python3 wledctl.py palettes --filter rainbow
python3 wledctl.py palette 11
python3 wledctl.py segment 0 palette 11
```

## 5. Raw JSON

Raw JSON posts are useful while experimenting with the WLED docs.

```bash
python3 wledctl.py post '{"on":true,"bri":32,"v":true}'
python3 wledctl.py post '{"seg":[{"id":0,"col":[[255,0,255]]}],"v":true}'
python3 wledctl.py post '{"transition":7,"seg":[{"id":0,"fx":9}],"v":true}'
```

Use the list form for segment payloads:

```json
{"seg":[{"id":0,"col":[[255,0,255]]}]}
```

WLED accepts a single segment object in some cases, but the list form scales to multiple segments and is what this project uses consistently.

## 6. Favourites / favorites

The CLI command is spelled `favorites`; documentation also uses “favourites” so either spelling is searchable. The default file is:

```bash
./wled_favourites.json
```

Use another file if needed:

```bash
python3 wledctl.py favorites list --favorites-file ./my-favourites.json
```

Discover effects:

```bash
python3 wledctl.py effects --filter rainbow
python3 wledctl.py effects --filter dj
```

Add favourites:

```bash
python3 wledctl.py favorites add 9 --notes "Good full-dome colour test"
python3 wledctl.py favorites add-name Rainbow --notes "Easy visual sanity check"
```

List favourites:

```bash
python3 wledctl.py favorites list
```

Set the saved default cycle interval:

```bash
python3 wledctl.py favorites interval 10
```

`favorites interval` updates `default_interval_seconds` in the favourites file and preserves saved effects.

Cycle once through saved favourites:

```bash
python3 wledctl.py favorites cycle
python3 wledctl.py favorites cycle --interval 5
python3 wledctl.py favorites cycle --interval 10
python3 wledctl.py favorites cycle --interval 10 --segment 0
python3 wledctl.py favorites cycle --interval 10 --return-state
```

`favorites cycle` uses the saved default interval. `favorites cycle --interval` overrides the default for that run only. `--return-state` asks WLED to return state from each effect change, but the cycling command is mainly an operator action and does not print each returned state.

Loop until stopped:

```bash
python3 wledctl.py favorites cycle --interval 20 --loop
```

Remove or clear:

```bash
python3 wledctl.py favorites remove 9
python3 wledctl.py favorites clear --yes
```

## 7. How to stop a running loop

Press **Ctrl-C**. The loop prints a short stop message and exits.

## 8. Mapping upload and clock-face test

The mapping commands do **not** generate the dome map. They expect the generated 300 x 300 map bundle to be copied into this repo and extracted under the project root.

Expected local layout from the project root:

```text
/workspace/thunderdome/json-controller/
  wledctl.py
  wled_mapping.py
  wled_map_top_centre_tail_300_v4/
    ledmap_on_dome.json
    led_positions_2d.json
    mapping_summary.json
    preview.svg
```

Place the generated zip beside this project, then extract it so the directory above exists:

```bash
cd /workspace/thunderdome/json-controller
unzip /path/to/thunderdome_wled_map_top_centre_tail_300_v4.zip
ls -la ./wled_map_top_centre_tail_300_v4/
```

If the zip extracts with an extra parent directory, move the map directory into the project root:

```bash
find . -maxdepth 3 -type f -name ledmap_on_dome.json
# Example, adjust the source path to match the find output:
mv ./some/extracted/path/wled_map_top_centre_tail_300_v4 ./
```

The key files are:

```text
wled_map_top_centre_tail_300_v4/ledmap_on_dome.json      # WLED ledmap upload target
wled_map_top_centre_tail_300_v4/led_positions_2d.json    # source for clock-face test patterns
```

`ledmap_on_dome.json` is uploaded to WLED as the remote filename `ledmap.json`; do not rename the local file unless doing a manual upload through the WLED `/edit` page.

Validate the WLED map before uploading:

```bash
python3 wledctl.py mapping validate ./wled_map_top_centre_tail_300_v4/ledmap_on_dome.json
```

Expected current map shape is roughly:

```text
Grid: 300 x 300
Total cells: 90000
Mapped LEDs: 4665
Blank cells: 85335
```

Dry-run upload to see the minified upload size without touching the controller:

```bash
python3 wledctl.py mapping upload ./wled_map_top_centre_tail_300_v4/ledmap_on_dome.json \
  --host 192.168.12.11 \
  --dry-run
```

Upload to WLED as the required remote filename `ledmap.json`:

```bash
python3 wledctl.py mapping upload ./wled_map_top_centre_tail_300_v4/ledmap_on_dome.json \
  --host 192.168.12.11
```

WLED must reboot to apply a new `ledmap.json`. Reboot manually from the WLED UI, power-cycle the controller, or explicitly request a reboot after upload:

```bash
python3 wledctl.py mapping upload ./wled_map_top_centre_tail_300_v4/ledmap_on_dome.json \
  --host 192.168.12.11 \
  --reboot
```

If `/edit` upload fails, manually open this URL and upload the file as `ledmap.json`:

```text
http://192.168.12.11/edit
```

Inspect the generated position source:

```bash
python3 wledctl.py mapping info ./wled_map_top_centre_tail_300_v4/led_positions_2d.json
```

Run a static clock-frame test first to confirm orientation. Angle convention is:

```text
0 degrees   = positive X / right / east
90 degrees  = positive Y / up / north
180 degrees = negative X / left / west
270 degrees = negative Y / down / south
```

```bash
python3 wledctl.py mapping clock-frame ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --angle 90 \
  --brightness 32
```

Run the rotating clock-hand mapping test with conservative defaults:

```bash
python3 wledctl.py mapping clock-test ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 60 \
  --fps 5 \
  --hand-width-deg 3 \
  --brightness 64
```

Preferred current mapping validation test: run a 10-pitch-wide straight physical clock-hand sweep. This uses `led_positions_2d.json` directly and does **not** require uploading `ledmap.json` to WLED. The hand is a straight 300 mm physical band from centre to edge, not an angle-only wedge/cone/arc:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --duration 3 \
  --step-deg 1 \
  --brightness 64 \
  --dry-run
```

Live test:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 3 \
  --step-deg 1 \
  --brightness 64
```

Continuous loop, each full 0°..359° sweep taking about 10 seconds, until Ctrl-C:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 10 \
  --step-deg 1 \
  --brightness 64 \
  --loop
```

Repeat exactly five full sweeps, then clear and stop:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 10 \
  --step-deg 1 \
  --brightness 64 \
  --repeat 5
```

`--loop` and `--repeat` are mutually exclusive. Ctrl-C in loop mode attempts to clear LEDs lit by the test unless `--leave-on` is supplied.

Slower diagnostic version:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 15 \
  --step-deg 1 \
  --brightness 64
```

Wider diagnostic version, 20 pitches = 600 mm:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --duration 5 \
  --step-deg 1 \
  --hand-width-pitches 20 \
  --brightness 64
```

Defaults for `clock-hand-sweep`:

```text
pitch: 30 mm
hand width: 10 pitches = 300 mm
step: 1 degree
sweep: 0..359 degrees
brightness: 64
colour: FFFFFF
background: 000000/off
tail: excluded
```

The hanging centre tail is excluded by default. Include it only when intentionally testing the tail:

```bash
python3 wledctl.py mapping clock-test ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --include-tail
```

Safety notes:

- Start with low brightness such as 16-64.
- The clock tests use WLED `seg.i` individual LED control and send requests sequentially.
- Large updates are chunked to reduce WLED JSON buffer pressure.
- Do not use JSON for high-FPS 5000-LED animation; use realtime DDP/UDP in a separate tool.

## 9. DDP realtime output

DDP is the preferred transport for realtime animation. It does **not** upload `ledmap.json`; the app still uses `led_positions_2d.json` as the geometry source of truth, then sends direct RGB pixel frames to WLED over UDP.

WLED setup notes:

- DDP uses UDP port `4048` by default.
- WLED must allow realtime UDP/DDP input.
- If frames do not display, check WLED **Config -> Sync Interfaces / Realtime** settings.
- Start at low brightness; DDP can update all 5000 pixels quickly.

Basic DDP tests:

```bash
# Clear all LEDs over DDP
python3 wledctl.py ddp clear --host 192.168.12.11 --led-count 5000

# Solid low-brightness red
python3 wledctl.py ddp solid --host 192.168.12.11 --led-count 5000 --color FF0000 --brightness 32

# Single physical pixel test
python3 wledctl.py ddp pixel --host 192.168.12.11 --led-count 5000 --index 0 --color FFFFFF --brightness 64

# Contiguous physical range test
python3 wledctl.py ddp range --host 192.168.12.11 --led-count 5000 --start 0 --count 50 --color FFFFFF --brightness 64
```

Run the 10-pitch clock-hand sweep over DDP:

```bash
python3 wledctl.py mapping clock-hand-sweep ./wled_map_top_centre_tail_300_v4/led_positions_2d.json \
  --host 192.168.12.11 \
  --transport ddp \
  --duration 10 \
  --step-deg 1 \
  --brightness 64
```

DDP transport options:

```text
--ddp-port 4048
--ddp-chunk-leds 480
--led-count 5000
--verbose
```

For mapping commands, `--led-count` defaults to `max(physical_index) + 1` from `led_positions_2d.json`; pass `--led-count 5000` explicitly when testing the full dome.

## 10. Troubleshooting

### Missing `WLED_BASE_URL`

Set it or pass `--base-url`:

```bash
export WLED_BASE_URL=http://192.168.12.11
python3 wledctl.py info

python3 wledctl.py info --base-url http://192.168.12.11
```

### Wrong IP or controller offline

Check network reachability:

```bash
ping 192.168.12.11
python3 explore_wled.py --base-url http://192.168.12.11 --endpoint info
```

### Timeout

Use a slightly longer timeout if Wi-Fi is slow:

```bash
python3 wledctl.py info --timeout 10
```

If repeated timeouts happen, check power, Wi-Fi signal, and whether the controller is rebooting.

### Invalid JSON

Shell quoting matters. Prefer single quotes around JSON:

```bash
python3 wledctl.py post '{"on":true,"bri":32}'
```

Validate complex JSON before sending:

```bash
python3 -m json.tool <<< '{"on":true,"bri":32}'
```

### Permission issues

Run with `python3` directly or mark scripts executable:

```bash
python3 wledctl.py info
chmod +x wledctl.py explore_wled.py
./wledctl.py info
```

### Too bright / too much power

Start low:

```bash
python3 wledctl.py brightness 16
python3 wledctl.py on
```

Avoid high-FPS per-pixel animation through JSON. For smooth 5000-LED animation, investigate WLED realtime protocols such as DDP/UDP in a separate project.
