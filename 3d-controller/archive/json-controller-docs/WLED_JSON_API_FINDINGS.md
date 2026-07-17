# WLED JSON API Findings

Primary documentation reviewed: <https://kno.wled.ge/interfaces/json-api/>

Start with `QUICKSTART.md` for operator commands and `FEATURES.md` for a concise project overview. This file is the lower-level API note.

## Known real controller context

Current observed controller values:

```text
Controller IP: 192.168.12.11
Name: Controller1
Brand: QuinLED
Product: Dig-Uno-V3
Firmware repo: intermittech/QuinLED-Firmware
WLED version: 16.0.0
Architecture: esp32
LED count: 5000
Max WLED segments: 32
RGBW: false
Current model: one logical WLED segment covering LEDs 0-4999
```

Code must still treat the target as generic WLED and use `WLED_BASE_URL` or `--base-url`; do not hard-code this IP.

## Overview

WLED exposes a JSON-over-HTTP API at `/json`. Reads use HTTP `GET`; state changes use HTTP `POST` to `/json` or `/json/state` with a partial `state` object.

The JSON API is appropriate for operator controls: power, brightness, colours, effects, palettes, segment-level updates, presets/playlists, and moderate direct LED tests. It is not the right transport for smooth high-FPS per-pixel animation across 5000 LEDs; use realtime protocols such as DDP/UDP for that in a separate project.

## Key endpoints

| Endpoint | Method | Returns / accepts | Mutability |
|---|---:|---|---|
| `/json` | GET | Full object containing `state`, `info`, `effects`, and `palettes` | Read; POST accepts partial state too |
| `/json/state` | GET/POST | Current mutable light state; POST partial state updates | Most `state` and `seg` fields are changeable |
| `/json/info` | GET | Device metadata, LED count, max segment count, effect/palette counts, version, capabilities | Read-only via JSON API |
| `/json/eff` | GET | Array of effect names; numeric index is effect ID | Read-only list; selected effect changes via `state.seg[].fx` |
| `/json/pal` | GET | Array of palette names; numeric index is palette ID | Read-only list; selected palette changes via `state.seg[].pal` |

Related optional endpoints include `/json/fxdata` for WLED 0.14+ effect metadata and `/json/cfg` for configuration. This project intentionally avoids configuration management.

## Important state fields

| Field | Read? | Change? | Notes |
|---|---:|---:|---|
| `on` | Yes | Yes | Boolean power. String `"t"` toggles. |
| `bri` | Yes | Yes | Global brightness 0-255. Prefer `on:false` for off; response generally does not report `bri:0`. |
| `transition` | Yes | Yes | Persistent transition in 100 ms units; 7 means 700 ms. |
| `tt` | No | Yes | One-request transition in 100 ms units. Not included in state response. |
| `v` | No | Yes | Include `"v":true` in POST to return full updated state on WLED v0.13+. |
| `ps` | Yes | Yes | Current/apply preset ID, ranges/random syntax supported. |
| `psave` | No | Yes | Saves current state to preset slot. This project does not expose preset saves. |
| `pdel` | No | Yes | Deletes preset. This project does not expose preset deletes. |
| `pl` | Yes | Mostly read-only | Current playlist ID. |
| `playlist` | No | Yes | Starts custom playlist; available since v0.11.0. |
| `rb` | No | Yes | Reboots immediately. This project does not expose reboot. |
| `live` | Yes/No | Yes | Enters/exits realtime mode. Use carefully; send `{"live":false}` after realtime stream ends. |
| `mainseg` | Yes | Yes | Main segment ID, 0 to `info.leds.maxseg - 1`. |
| `seg` | Yes | Yes | Segment object or array of segment objects. This project uses array/list form consistently. |

`info` fields are read-only through this API. Important validation fields are `info.leds.count`, `info.leds.maxseg`, `info.fxcount`, `info.palcount`, `info.ver`, and capability fields such as `info.leds.lc`/`seglc`.

## Segments

Segments are WLED virtual regions with independently controllable colours/effects/palettes. Segment state lives in `state.seg`, an array of objects. Since WLED 0.9.0, segments can have different effects. Older WLED v0.8.4 had major segment limitations; the real controller reports WLED 16.0.0.

This project does **not** build physical dome mapping. It can send commands to WLED segment IDs that already exist or are manually created, but mapping LEDs to rings/panels/faces is out of scope.

### Reading current segments

```bash
python3 wledctl.py state
curl --max-time 5 "$WLED_BASE_URL/json/state"
```

Inspect `state.seg` for `id`, `start`, `stop`, `len`, `n`, `col`, `fx`, `pal`, `on`, `bri`, `sel`, `rev`, etc.

### Segment constraints and semantics

- `id`: zero-indexed segment ID. Valid range is documented as `0` to `info.leds.maxseg - 1`.
- `start`: first LED in the segment, 0 to `info.leds.count - 1`.
- `stop`: exclusive stop LED, 0 to `info.leds.count`. If `stop <= start`, the segment is invalidated/deleted; docs recommend `stop:0`.
- `len`: segment length. If `stop` is included, `stop` takes precedence and `len` is ignored.
- `col`: up to three colour slots, each RGB or RGBW byte array, or compact hex string.
- `fx`: effect ID `0` to `info.fxcount - 1`; WLED also supports strings such as `"r"`, `"~"`, and `"~-"`.
- `pal`: palette ID `0` to `info.palcount - 1`; also supports random/increment syntax.
- `sel`: selected segment flag. APIs that do not support segments apply to selected segments; if none selected, segment 0 behaves as selected.
- `on` and `bri`: per-segment power/brightness available since v0.10.0.

### Updating a specific segment

Use list form:

```jsonc
{"seg": [{"id": 0, "col": [[0, 255, 200]], "fx": 0, "pal": 0}]}
```

CLI:

```bash
python3 wledctl.py segment 0 color 0 255 200
python3 wledctl.py segment 0 effect 9
python3 wledctl.py segment 0 palette 11
```

### Creating/updating multiple WLED segments

WLED supports multiple segment objects in one request:

```jsonc
{
  "seg": [
    {"id": 0, "start": 0, "stop": 2500, "n": "section-a"},
    {"id": 1, "start": 2500, "stop": 5000, "n": "section-b"}
  ]
}
```

These are plain WLED segment ranges, not a dome mapping system.

## Effects and palettes

`/json/eff` and `/json/pal` return arrays. The array index is the numeric ID.

```bash
python3 wledctl.py effects
python3 wledctl.py effects --filter rainbow
python3 wledctl.py effect 9
python3 wledctl.py palettes
python3 wledctl.py palette 11
```

In WLED 0.14+, some effect IDs may be unsupported in a build and listed as `RSVD` or `-`. Operator UIs should hide or skip those.

## Effect favourites

The CLI stores favourite effects in `./wled_favourites.json` by default:

```json
{
  "default_interval_seconds": 30,
  "effects": [
    {
      "id": 9,
      "name": "Rainbow",
      "notes": "Good basic full-dome test"
    }
  ]
}
```

Normal use does not require manual editing:

```bash
python3 wledctl.py effects --filter rainbow
python3 wledctl.py favorites add 9 --notes "Good full-dome colour test"
python3 wledctl.py favorites list
python3 wledctl.py favorites cycle --interval 10
python3 wledctl.py favorites cycle --interval 20 --loop
```

Use `--favorites-file ./my-favourites.json` to keep a separate set.

## Direct per-LED control

WLED supports per-segment individual LED control with segment field `i`, available since v0.10.2. It is not included in state responses and is non-persistent. Using `i` freezes the segment's effect.

Use list-form `seg` payloads for consistency:

```jsonc
{"seg": [{"id": 0, "i": ["FF0000", "00FF00", "0000FF"]}]}
```

```jsonc
{"seg": [{"id": 0, "i": [0, "FF0000", 2, "00FF00", 4, "0000FF"]}]}
```

```jsonc
{"seg": [{"id": 0, "i": [0, 8, "FF0000", 10, 18, "0000FF"]}]}
```

Important limitations:

- Indices are segment-relative, not global strip indices.
- Set desired brightness before individual LED control; turning on from off and setting individual LEDs in the same request may not work correctly.
- Prefer hex strings for large payloads.
- Split large updates into sequential chunks of about 256 colours.
- Do not send chunks in parallel; wait for each request to complete.
- JSON buffer limits can be around 10 KB on ESP8266 and 24 KB on ESP32, depending on build.
- For smooth/high-FPS dome animation, use realtime DDP/UDP/E1.31 rather than HTTP JSON.

## Presets and playlists

Presets are relevant once stable looks are defined. Apply a preset with raw JSON such as `{"ps":5}` if needed. This project does not expose preset save/delete commands.

Playlist example from the docs:

```json
{
  "playlist": {
    "ps": [26, 20, 18, 20],
    "dur": [30, 20, 10, 50],
    "transition": 0,
    "repeat": 10,
    "end": 21
  }
}
```

`dur` and playlist `transition` values are in tenths of seconds. `repeat:0` means indefinite.

## Safety and reliability notes

- Configure the target with `WLED_BASE_URL`; never hard-code the installation IP in code.
- Use timeouts. The client defaults to 5 seconds.
- Validate brightness and RGB byte ranges before sending.
- Validate effect and palette IDs using `info.fxcount`, `info.palcount`, `/json/eff`, or `/json/pal`.
- Read `/json/info` first to learn LED count, max segment count, version, and capabilities.
- Avoid `rb`, `psave`, `pdel`, and configuration-changing endpoints in normal control paths.
- Do not spam the controller. Coalesce state changes into one JSON POST when possible.
- Test first at low brightness.
- WLED version differences matter: segment support improved after 0.9.0, per-segment power/brightness after 0.10.0, individual LED control after 0.10.2, playlists after 0.11.0, response `v:true` documented for v0.13+, and effect metadata `/json/fxdata` in 0.14+.

## Files

- `QUICKSTART.md`: start here; operator commands.
- `FEATURES.md`: concise overview of what this project can/cannot do.
- `explore_wled.py`: fetches and pretty-prints core JSON endpoints.
- `wled_client.py`: minimal reusable Python client.
- `wledctl.py`: CLI wrapper.
- `wled_favorites.py`: favourites config and cycle helpers.
- `example_payloads.md`: raw JSON examples.
- `tests/test_wled_client.py`: unit tests.

## Follow-up TODOs

- Run `python3 explore_wled.py --endpoint info` against the real controller and save an operator snapshot.
- Add more operator-vetted favourite effects after testing at low brightness.
- Consider a separate DDP/realtime project for high-FPS animation.
- Keep physical LED/dome mapping separate from this JSON API control tool.
