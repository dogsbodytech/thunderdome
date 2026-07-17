# WLED JSON API Example Control Payloads

All examples POST JSON to:

```text
${WLED_BASE_URL}/json/state
```

Use a timeout and `Content-Type: application/json`.

```bash
curl --max-time 5 -X POST "$WLED_BASE_URL/json/state" \
  -H 'Content-Type: application/json' \
  -d '{"on":true,"v":true}'
```

This project uses the list form for segment payloads:

```json
{"seg":[{"id":0,"col":[[255,0,255]]}]}
```

WLED accepts a single segment object in some cases, but the list form is easier to extend to multiple segments and is used consistently in code and docs.

## Power

```jsonc
{"on": true}
```
Turn LEDs on.

```jsonc
{"on": false}
```
Turn LEDs off.

```jsonc
{"on": "t", "v": true}
```
Toggle LEDs and, on WLED v0.13+, return the updated state because `v` is true.

## Brightness

```jsonc
{"bri": 32}
```
Safe low-brightness first test.

```jsonc
{"bri": 128}
```
Set global brightness to 128 on a 0-255 scale. WLED recommends using `on:false` for off instead of relying on `bri:0`.

## Transition timing

```jsonc
{"transition": 7}
```
Persist transition time. Units are 100 ms, so `7` is 700 ms.

```jsonc
{"tt": 4, "seg": [{"id": 0, "col": [[255, 0, 0]]}]}
```
Use a 400 ms transition only for this request.

## Colours

```jsonc
{"seg": [{"id": 0, "col": [[255, 0, 0]]}]}
```
Set segment 0's primary colour to red. `col` may contain up to three RGB/RGBW colour slots: primary, secondary/background, tertiary.

```jsonc
{"seg": [{"id": 0, "col": [[0, 255, 200]]}]}
```
Set segment 0 to teal.

```jsonc
{"seg": [{"id": 0, "col": ["FF00CC", "000000", "202020"]}]}
```
Set segment 0 colours with compact hex strings.

## Effects and palettes

```jsonc
{"seg": [{"id": 0, "fx": 9}]}
```
Set segment 0's effect by numeric ID from `/json/eff`.

```jsonc
{"seg": [{"id": 0, "pal": 11}]}
```
Set segment 0's palette by numeric ID from `/json/pal`.

```jsonc
{"seg": [{"fx": "r"}]}
```
Select a random effect on selected/default segment(s).

```jsonc
{"seg": [{"id": 0, "pal": "5~10r"}]}
```
Select a random palette between IDs 5 and 10 for segment 0.

## Segments

```jsonc
{"seg": [{"id": 0, "start": 0, "stop": 5000, "n": "whole logical segment"}]}
```
Create/update one logical segment spanning LEDs 0-4999. `stop` is exclusive.

```jsonc
{
  "seg": [
    {"id": 0, "start": 0, "stop": 2500, "n": "section-a"},
    {"id": 1, "start": 2500, "stop": 5000, "n": "section-b"}
  ]
}
```
Create/update multiple plain WLED segments in one request. This is not a physical dome mapping system.

```jsonc
{"seg": [{"id": 0, "on": "t"}]}
```
Toggle segment 0 only.

```jsonc
{"seg": [{"id": 3, "stop": 0}]}
```
Invalidate/delete segment 3 by setting `stop` lower than or equal to `start`; docs recommend `stop:0`. Be careful with segment deletion during operations.

## Per-segment individual LED control

```jsonc
{"seg": [{"id": 0, "i": ["FF0000", "00FF00", "0000FF"]}]}
```
Set the first three LEDs of segment 0 to red, green, blue.

```jsonc
{"seg": [{"id": 0, "i": [0, "FF0000", 2, "00FF00", 4, "0000FF"]}]}
```
Set individual segment-relative LED indices 0, 2, and 4.

```jsonc
{"seg": [{"id": 0, "i": [0, 8, "FF0000", 10, 18, "0000FF"]}]}
```
Set segment-relative ranges: LEDs 0-7 red and 10-17 blue.

For large LED counts, prefer hex strings and split into sequential chunks of roughly 256 colours rather than parallel requests. For smooth high-FPS per-pixel animation, use DDP/UDP realtime protocols in a separate tool.

## Effect favourites config

Default config file:

```text
./wled_favourites.json
```

Shape:

```json
{
  "default_interval_seconds": 30,
  "effects": [
    {
      "id": 9,
      "name": "Rainbow",
      "notes": "Good basic full-dome test"
    },
    {
      "id": 163,
      "name": "DJ Light",
      "notes": "Good active party look"
    }
  ]
}
```

Normal operators should use CLI commands rather than hand-editing:

```bash
python3 wledctl.py effects --filter rainbow
python3 wledctl.py favorites add 9 --notes "Good full-dome colour test"
python3 wledctl.py favorites list
python3 wledctl.py favorites cycle --interval 10
python3 wledctl.py favorites cycle --interval 20 --loop
python3 wledctl.py favorites remove 9
```
