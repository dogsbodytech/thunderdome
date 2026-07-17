# Spatial effects

Thunderdome renders application effects from `geometry/generated/led_positions_3d.json`, builds one logical 5,000-pixel linear RGB frame, and fans that exact 15,000-byte frame out to the five direct-DDP WLED controllers. WLED is the transport endpoint; XYZ mapping lives in Python.

Generate/validate positions before effects:

```bash
thunderdome positions generate
thunderdome positions validate
```

Built-in default geometry, positions, and controller paths are project-root-safe: they work from the repository root, from `3d-controller/`, or from an unrelated CWD such as `/tmp`. Explicit relative paths supplied by the user remain relative to the process CWD.

## Command table

| Effect | Spatial basis | Important options | Default finite behaviour | Example |
| --- | --- | --- | --- | --- |
| `clock-hand` | Forward XY half-ray from H061 XY | `--width-mm`, `--rotation-seconds`, `--direction`, `--rotations` | One rotation | `thunderdome effect clock-hand --brightness 24 --rotations 1` |
| `expanding-rings` | True XYZ Euclidean spherical shell | `--origin`, `--speed-mps`, `--thickness-mm`, `--loops` | One shell expansion | `thunderdome effect expanding-rings --origin apex --loops 1 --brightness 24` |
| `height-wave` | Horizontal band over selected physical Z bounds | `--direction`, `--speed-mps`, `--height-mm`, `--loops` | One movement cycle | `thunderdome effect height-wave --direction bounce --loops 1 --brightness 24` |
| `fire` | XYZ height, radial position, deterministic turbulence | `--speed`, `--flame-height-m`, `--turbulence`, `--cooling`, `--palette`, `--spark-rate` | One procedural loop | `thunderdome effect fire --brightness 24 --loops 1` |
| `rotating-plane` | Signed distance to a rotating 3D plane | `--axis`, `--rotation-seconds`, `--thickness-mm`, `--color` | One plane rotation | `thunderdome effect rotating-plane --axis tilted --loops 1` |
| `radar` | Angular XYZ/XY sweep around dome centre | `--rotation-seconds`, `--beam-width-degrees`, `--trail-degrees`, `--color` | One sweep | `thunderdome effect radar --loops 1 --brightness 24` |
| `aurora` | Height/angle/direction waves in XYZ | `--direction X,Y,Z`, `--speed`, `--scale`, `--intensity`, `--palette` | One slow cycle | `thunderdome effect aurora --duration 20 --brightness 24` |
| `fireflies` | Deterministic moving 3D particles and distance falloff | `--count`, `--speed`, `--glow-radius-mm`, `--lifetime-seconds`, `--color` | One lifecycle loop | `thunderdome effect fireflies --count 30 --loops 1` |
| `auto` | Registry playlist of production effects | `--playlist`, `--preset`, `--interval`, `--crossfade`, `--loops`, `--shuffle` | One complete playlist | `thunderdome effect auto --preset calm --loops 1 --dry-run` |

## Shared controls

All spatial effects produce exactly 5,000 RGB pixels / 15,000 bytes. Tails are included by default and use their real generated XYZ coordinates. Add `--exclude-tail` to remove tail LEDs from selection and bounds.

`--loops COUNT`, `--duration SECONDS`, and `--hold` are mutually exclusive for non-clock spatial effects. `--loops` means complete effect cycles; for `height-wave --direction bounce`, one loop is a complete out-and-back. `clock-hand` keeps the older clock-specific `--rotations`; non-clock effects use `--loops`.

`--fps` controls frame rate, 1..60, default 30. Ctrl+C cleanly stops held streams, closes DDP sessions, and reports frame statistics. Start at safe low brightness such as `--brightness 24`.

`--dry-run` renders and validates without opening UDP sockets. With `--prepare-ddp`, dry-run reports what would happen and makes no HTTP request.

`--prepare-ddp` reuses the existing multi-controller WLED operation exactly once before streaming. It posts the combined safe fallback payload `{"on": false, "bri": 255, "live": false}` to every enabled controller, continues through all controllers to report failures, aborts before DDP if any preparation fails, and returns non-zero on failure. This sets persistent WLED fallback off with WLED master brightness 255; Python frame brightness remains controlled by the effect `--brightness` option.

## Existing spatial effects

### Clock hand

`clock-hand` is a rotating radial hand in the XY plane centred on authoritative H061 XY. It uses `--rotations` because that command is explicitly clock-like.

### Expanding spherical shell

`expanding-rings` is a true 3D spherical shell, not a flat XY ring. Each LED uses:

```python
distance = sqrt((x - origin_x) ** 2 + (y - origin_y) ** 2 + (z - origin_z) ** 2)
```

LEDs within half the full `--thickness-mm` of the elapsed-time shell radius are illuminated. The shell radius increases with elapsed time using `--speed-mps` and wraps after the maximum selected LED distance from the selected origin.

`--origin` defaults to `apex`:

- `apex`: authoritative H061 XYZ from `geometry/thunderdome_geometry.json`.
- `centre`: H061 X/Y, and Z midpoint between H061 Z and the dome-only minimum Z.
- `base`: H061 X/Y, and the dome-only minimum Z.
- `X,Y,Z`: explicit metre coordinates, for example `0.0,0.0,1.5`.

```bash
thunderdome effect expanding-rings \
  --controllers config/controllers.json \
  --origin apex \
  --speed-mps 1.0 \
  --thickness-mm 250 \
  --brightness 24 \
  --loops 2

thunderdome effect expanding-rings \
  --controllers config/controllers.json \
  --origin base \
  --brightness 24 \
  --duration 20
```

### Height wave

`height-wave` selects a full-thickness `--height-mm` horizontal band over actual selected Z coordinates.

- `--direction up`: minimum Z to maximum Z, then wraps.
- `--direction down`: maximum Z to minimum Z, then wraps.
- `--direction bounce`: reverses cleanly at bounds; one loop is out-and-back.

```bash
thunderdome effect height-wave \
  --controllers config/controllers.json \
  --direction bounce \
  --height-mm 300 \
  --brightness 24 \
  --hold
```

## New procedural effects

`fire` renders a volumetric plume using Z height, radial position, and deterministic turbulence. The palette defaults to red/orange/yellow flame tones. `--cooling` controls height falloff; `--turbulence` and `--speed` control flicker. `--spark-rate` is parsed for the fire command and reserved for sparkle density tuning.

`rotating-plane` lights LEDs near a signed-distance plane rotating through the generated XYZ volume. `--axis` accepts named axes such as `vertical`, `horizontal`, `tilted`, or explicit `X,Y,Z` vectors. `--thickness-mm` is the full luminous band thickness.

`radar` sweeps an angular beam around the dome centre. `--beam-width-degrees` controls the bright beam, `--trail-degrees` controls the fading tail, and `--range-m`/`--vertical-falloff` can limit influence.

`aurora` creates slow layered luminous curtains using deterministic multi-frequency waves in XYZ. `--direction X,Y,Z` controls wave flow; `--scale`, `--speed`, `--band-width`, and `--intensity` shape the curtains.

`fireflies` uses a deterministic reusable particle system. Particles have stable seeded position/velocity/lifecycle templates; each frame computes moving 3D particle positions and lights nearby LEDs by true 3D distance to active particles. `--count` is bounded by parser positive-integer validation and renderer validation; use moderate counts for live operation.

## Auto showcase

`thunderdome effect auto` cycles through the registry playlist with optional linear RGB crossfade. Crossfade blends full-brightness source frames first and applies global `--brightness` exactly once to the blended frame.

Default playlist:

```text
clock-hand, expanding-rings, height-wave, fire, rotating-plane, radar, aurora, fireflies
```

Presets:

- `--preset calm`: `height-wave, aurora, fireflies, expanding-rings`
- `--preset energetic`: `clock-hand, fire, rotating-plane, radar, aurora, fireflies`

Use `--playlist` or `--effects` for a comma-separated explicit playlist. `--interval` defaults to 30 seconds and `--crossfade`/`--transition` defaults to 2 seconds; crossfade must be shorter than interval.

```bash
thunderdome effect auto \
  --controllers config/controllers.json \
  --preset calm \
  --interval 30 \
  --crossfade 2 \
  --brightness 24 \
  --prepare-ddp \
  --hold

thunderdome effect auto \
  --controllers config/controllers.example.json \
  --playlist fire,aurora,fireflies \
  --loops 1 \
  --dry-run
```

Recommended operational example:

```bash
thunderdome effect height-wave \
  --controllers config/controllers.json \
  --direction bounce \
  --brightness 24 \
  --prepare-ddp \
  --hold
```
