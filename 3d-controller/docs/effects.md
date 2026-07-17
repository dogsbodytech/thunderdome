# Spatial effects

Thunderdome renders application effects from `geometry/generated/led_positions_3d.json`, builds one logical 5,000-pixel linear RGB frame, and fans that exact 15,000-byte frame out to the five direct-DDP WLED controllers. WLED is the transport endpoint; XYZ mapping lives in Python.

Generate/validate positions before effects:

```bash
thunderdome positions generate
thunderdome positions validate
```

Built-in default geometry, positions, and controller paths are project-root-safe: they work from the repository root, from `3d-controller/`, or from an unrelated CWD such as `/tmp`. Explicit relative paths supplied by the user remain relative to the process CWD.

## Controller readiness

Effect commands do not modify persistent WLED state before streaming. Controllers must already be powered on with suitable WLED master brightness. The earlier `--prepare-ddp` option was removed because setting WLED off before realtime streaming caused animations to disappear.

Recommended manual setup:

```bash
thunderdome controllers power on \
  --controllers config/controllers.json

thunderdome controllers brightness 255 \
  --controllers config/controllers.json
```

Then run an effect directly, without preparation.

## Command table

| Effect | Spatial basis | Relevant options | Default finite behavior | Example |
| --- | --- | --- | --- | --- |
| `clock-hand` | Forward XY half-ray from H061 XY | `--width-mm`, `--rotation-seconds`, `--direction`, `--rotations` | One rotation | `thunderdome effect clock-hand --brightness 24 --rotations 1` |
| `expanding-rings` | True XYZ Euclidean spherical shell | `--origin`, `--speed-mps`, `--thickness-mm`, `--loops` | One shell expansion | `thunderdome effect expanding-rings --origin apex --loops 1 --brightness 24` |
| `height-wave` | Horizontal band over selected physical Z bounds | `--direction`, `--speed-mps`, `--height-mm`, `--loops` | One movement cycle | `thunderdome effect height-wave --direction bounce --loops 1 --brightness 24` |
| `fire` | XYZ height, radial position, deterministic turbulence | `--speed`, `--flame-height-m`, `--turbulence`, `--cooling`, `--scale`, `--palette`, `--seed` | 5 seconds | `thunderdome effect fire --duration 10 --brightness 24` |
| `rotating-plane` | Signed distance to a rotating 3D plane | `--axis`, `--rotation-seconds`, `--thickness-mm`, `--color`, `--background`, `--trail-degrees`, `--direction`, `--loops` | One plane rotation | `thunderdome effect rotating-plane --axis tilted --loops 1` |
| `radar` | Angular XYZ/XY sweep around dome centre | `--rotation-seconds`, `--beam-width-degrees`, `--trail-degrees`, `--range-m`, `--vertical-falloff`, `--color`, `--background`, `--direction`, `--loops` | One beam rotation | `thunderdome effect radar --loops 1 --brightness 24` |
| `aurora` | Height/angle/direction waves in XYZ | `--direction X,Y,Z`, `--speed`, `--scale`, `--band-width`, `--intensity`, `--palette`, `--seed` | 10 seconds | `thunderdome effect aurora --duration 20 --brightness 24` |
| `fireflies` | Deterministic moving 3D particles and distance falloff | `--count`, `--speed`, `--glow-radius-mm`, `--lifetime-seconds`, `--color`, `--color-variation`, `--seed` | 8 seconds | `thunderdome effect fireflies --count 30 --duration 12` |
| `auto` | Registry playlist of production effects | `--playlist`/`--effects`, `--preset`, `--interval`, `--crossfade`/`--transition`, `--cycles`, `--duration`, `--shuffle`, `--seed` | Continuous until Ctrl+C | `thunderdome effect auto --preset calm` |

## Shared controls

All effects produce exactly 5,000 RGB pixels / 15,000 bytes. Tails are included by default and use their real generated XYZ coordinates. Add `--exclude-tail` to remove tail LEDs from selection and bounds.

Common individual-effect runtime controls are `--controllers`, `--positions`, `--geometry`, `--brightness`, `--fps`, `--duration`, `--hold`, `--exclude-tail`, and `--dry-run`. Only effects with meaningful cycles expose cycle options: `clock-hand --rotations`; `expanding-rings --loops`; `height-wave --loops`; `rotating-plane --loops`; `radar --loops`.

`fire`, `aurora`, and `fireflies` use `--duration` or `--hold`; they do not expose `--loops` because their procedural motion does not naturally return to a guaranteed starting visual state.

`--fps` controls frame rate, 1..60, default 30. Ctrl+C cleanly stops held or continuous streams, closes DDP sessions, and reports frame statistics. Start at safe low Python brightness such as `--brightness 24`.

`--dry-run` uses the same scheduling path as live streaming and splits rendered frames into simulated DDP packets without opening UDP sockets or making HTTP requests.

## Existing spatial effects

### Clock hand

`clock-hand` is a rotating radial hand in the XY plane centred on authoritative H061 XY. It uses `--rotations` because that command is explicitly clock-like.

### Expanding spherical shell

`expanding-rings` is a true 3D spherical shell, not a flat XY ring. LEDs within half the full `--thickness-mm` of the elapsed-time shell radius are illuminated. The shell radius increases with elapsed time using `--speed-mps` and wraps after the maximum selected LED distance from the selected origin.

`--origin` defaults to `apex`:

- `apex`: authoritative H061 XYZ from `geometry/thunderdome_geometry.json`.
- `centre`: H061 X/Y, and Z midpoint between H061 Z and the dome-only minimum Z.
- `base`: H061 X/Y, and the dome-only minimum Z.
- `X,Y,Z`: explicit metre coordinates, for example `0.0,0.0,1.5`.

### Height wave

`height-wave` selects a full-thickness `--height-mm` horizontal band over actual selected Z coordinates.

- `--direction up`: minimum Z to maximum Z, then wraps.
- `--direction down`: maximum Z to minimum Z, then wraps.
- `--direction bounce`: reverses cleanly at bounds; one loop is out-and-back.

## Procedural effects

`fire` renders a volumetric plume using Z height, radial position, and deterministic turbulence. `--cooling` controls height falloff; `--turbulence` and `--speed` control flicker.

`rotating-plane` lights LEDs near a signed-distance plane rotating through the generated XYZ volume. `--axis` accepts named axes such as `vertical`, `horizontal`, `tilted`, or explicit `X,Y,Z` vectors. `--thickness-mm` is the full luminous band thickness; `--loops N` means N complete plane rotations.

`radar` sweeps an angular beam around the dome centre. `--beam-width-degrees` controls the bright beam, `--trail-degrees` controls the fading tail, and `--loops N` means N complete beam rotations.

`aurora` creates slow layered luminous curtains using deterministic multi-frequency waves in XYZ. `--direction X,Y,Z` controls wave flow; `--scale`, `--speed`, `--band-width`, and `--intensity` shape the curtains.

`fireflies` uses a deterministic reusable particle system. Particles have stable seeded position/velocity/lifecycle templates retained for the whole effect run; each frame computes moving 3D particle positions and lights nearby LEDs by true 3D distance.

## Auto showcase

`thunderdome effect auto` cycles through the registry playlist with optional linear RGB crossfade. Crossfade blends full-brightness source frames first and applies global `--brightness` exactly once to the blended frame.

Default settings:

- `--interval 30`
- `--transition 2` / `--crossfade 2`
- `--brightness 32`
- `--fps 30`
- continuous until Ctrl+C when neither `--cycles` nor `--duration` is supplied.

Default playlist:

```text
clock-hand, expanding-rings, height-wave, fire, rotating-plane, radar, aurora, fireflies
```

Presets:

- `--preset calm`: `height-wave, aurora, fireflies, expanding-rings`
- `--preset energetic`: `clock-hand, fire, rotating-plane, radar, aurora, fireflies`

Use `--playlist` or `--effects` for a comma-separated explicit playlist. Supplied order is preserved. Empty playlists, unknown names, duplicates, and non-auto-capable entries are rejected. `--shuffle --seed N` shuffles once at startup; the same seed produces the same playlist order.

Finite controls are mutually exclusive:

- `--cycles N`: N complete playlist passes.
- `--duration S`: run the scheduler for S seconds.
- neither: continue until Ctrl+C.

Crossfade timing for interval `I` and transition `T` uses one interval per effect. The first `I - T` seconds show only the current effect. The last `T` seconds render outgoing elapsed time and incoming elapsed time starting at zero at transition start, blend them, apply brightness once, then send one logical frame. `T` may be zero and must satisfy `0 <= T < I`.

```bash
thunderdome effect auto \
  --controllers config/controllers.json \
  --preset calm \
  --interval 30 \
  --crossfade 2 \
  --brightness 24

thunderdome effect auto \
  --controllers config/controllers.example.json \
  --playlist fire,aurora,fireflies \
  --cycles 1 \
  --interval 0.4 \
  --transition 0.1 \
  --fps 5 \
  --dry-run
```
