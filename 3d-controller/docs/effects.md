# Spatial effects

> Stage B preview output defaults to `--output simulator`. Use explicit `--output ddp --controllers config/controllers.json` only to send physical DDP; `--output both` sends the same rendered frame to both destinations, and `--output null` renders without network output.

Thunderdome renders application effects from `geometry/generated/led_positions_3d.json` into one logical 5,000-pixel / 15,000-byte RGB frame. The selected sink then delivers that same final frame to the local simulator, the five direct-DDP WLED controllers, both, or neither. XYZ mapping remains in Python.

The Stage A geometry/LED-layout viewer remains available with no producer connected. Stage B streams local binary WebSocket frames into that same viewer; see [simulator.md](simulator.md).

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
| `twinkle` | Stateful per-LED fade-in/hold/fade-out sparkles | `--density`, `--spawn-rate`, `--fade-in`, `--hold-time`, `--fade-out`, `--minimum-brightness`, `--maximum-brightness`, `--color`, `--mode`, `--background`, `--color-change-speed`, `--seed` | 10 seconds | `thunderdome effect twinkle --duration 15 --brightness 24` |
| solar-system bodies | XYZ colour wash; palette and style fixed per body | `--speed`, `--seed` | 12 seconds | `thunderdome effect Sol --brightness 24` |
| `auto` | Registry playlist of production effects | `--playlist`/`--effects`, `--preset`, `--interval`, `--crossfade`/`--transition`, `--cycles`, `--duration`, `--shuffle`, `--seed` | Continuous until Ctrl+C | `thunderdome effect auto --preset calm` |

## Shared controls

All effects produce exactly 5,000 RGB pixels / 15,000 bytes. Tails are included by default and use their real generated XYZ coordinates. Add `--exclude-tail` to remove tail LEDs from selection and bounds.

Common individual-effect runtime controls are `--output simulator|ddp|both|null`, `--simulator-url`, `--controllers`, `--positions`, `--geometry`, `--brightness`, `--fps`, `--duration`, `--hold`, `--exclude-tail`, and `--dry-run`. Controller configuration is loaded only for `ddp` and `both`; simulator and null output do not inspect it. Only effects with meaningful cycles expose cycle options: `clock-hand --rotations`; `expanding-rings --loops`; `height-wave --loops`; `rotating-plane --loops`; `radar --loops`.

`fire`, `aurora`, `fireflies`, `twinkle`, and the solar-system bodies use `--duration` or `--hold`; they do not expose `--loops` because their procedural motion does not naturally return to a guaranteed starting visual state.

`--fps` controls frame rate, 1..60, default 30. Ctrl+C cleanly stops held or continuous streams, closes DDP sessions, and reports frame statistics. Start at safe low Python brightness such as `--brightness 24`.

`--output null` runs the real renderer and scheduler, validates frames, and discards them without network output. `--dry-run` is a compatibility alias for null output; it cannot be combined with `--output ddp` or `--output both`. Simulator connection failures are errors and never fall back to DDP.

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

`fire` renders a volumetric plume using Z height, radial position, and deterministic turbulence. `--cooling` controls height falloff; `--turbulence` and `--speed` control flicker. `--turbulence 0` and `--cooling 0` are valid ways to disable those modifiers; values are bounded to `0..1`.

`rotating-plane` lights LEDs near a signed-distance plane rotating through the generated XYZ volume. `--axis` is the true 3D rotation axis, not the plane normal. Named axes are exactly: `vertical=(0,0,1)`, `horizontal=(1,0,0)`, and `tilted=normalize(1,1,1)`. Explicit `--axis X,Y,Z` values must be finite and nonzero; they are normalized internally. The renderer chooses a deterministic initial normal perpendicular to the axis and rotates it with Rodrigues' formula. Axis parsing, current plane normal, and trail plane normals are precomputed once per rendered frame; the per-LED loop only performs signed-distance/intensity/blending work against those samples. `--thickness-mm` is the full luminous band thickness; `--loops N` means N complete plane rotations.

`rotating-plane --trail-degrees 0` disables the trail. Accepted values are `0..180`; 180 degrees covers all unique signed-distance plane orientations because normals `n` and `-n` describe the same plane when distance is absolute. Values above 180 are rejected rather than clamped. Positive trail values sample a bounded set of previous plane orientations behind the moving plane, combine them with a smooth fading weight, and keep the current plane brightest. The sample count is bounded to the main plane plus at most 12 trail samples for Raspberry Pi performance. Clockwise and counterclockwise place the trail on opposite sides of the plane.

`radar` sweeps an angular beam around the dome centre. `--beam-width-degrees` controls the bright beam, `--trail-degrees` controls the fading tail, and `--loops N` means N complete beam rotations.

`aurora` creates slow layered luminous curtains using deterministic multi-frequency waves in XYZ. `--direction X,Y,Z` controls wave flow; `--scale`, `--speed`, `--band-width`, and `--intensity` shape the curtains.

`fireflies` uses a deterministic reusable particle system. Particles have stable seeded position/velocity/lifecycle templates retained for the whole effect run; each frame computes moving 3D particle positions and lights nearby LEDs by true 3D distance.

## Solar system bodies

Twelve ambient effects, one per body, so someone standing in the dome and looking around sees the colours of that object. Each is the same colour-wash renderer with a fixed palette and rendering style; only `--speed` (animation rate) and `--seed` are tunable. All are auto-capable; the `solar-system` auto preset tours them in order.

| Effect | Style | Colours the viewer sees |
| --- | --- | --- |
| `AsteroidBelt` | belt | sparse drifting grey/brown rocks on black |
| `Jupiter` | bands | cream, tan, rust and orange horizontal bands |
| `Saturn` | bands | soft pale-gold and butterscotch bands |
| `Uranus` | soft | featureless pale cyan |
| `Neptune` | soft | deep vivid blue with lighter azure streaks |
| `KuiperBelt` | belt | cold, sparse icy blue-white debris on black |
| `Voyager1` | belt | near-black with a lonely faint gold glint |
| `Sol` | sun | full roiling yellow, orange-to-white shimmer |
| `Mercury` | mottled | scorched grey rock with faint warm patches |
| `Venus` | soft | thick creamy pale-yellow cloud |
| `Earth` | mottled | blue oceans, green land, white cloud |
| `Mars` | mottled | rusty red dust, all reds and orange |

Styles: `bands` maps the palette repeatedly up the dome's Z height with slow drift; `mottled` mixes palette colours by 3D noise blobs; `soft` is a near-uniform wash with gentle cloud movement; `sun` is a bright turbulent warm field; `belt` lights only a sparse, drifting fraction of LEDs and leaves the rest dark.

```bash
thunderdome effect Mars --brightness 24 --duration 20
thunderdome effect auto --preset solar-system --interval 20 --brightness 24
```

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
- `--preset solar-system`: `AsteroidBelt, Jupiter, Saturn, Uranus, Neptune, KuiperBelt, Voyager1, Sol, Mercury, Venus, Earth, Mars`

Use `--playlist` or `--effects` for a comma-separated explicit playlist. Supplied order is preserved. Empty playlists, unknown names, duplicates, and non-auto-capable entries are rejected. `--shuffle --seed N` shuffles once at startup; the same seed produces the same playlist order.

Finite controls are mutually exclusive:

- `--cycles N`: N complete playlist passes.
- `--duration S`: run the scheduler for S seconds.
- neither: continue until Ctrl+C.

Crossfade timing for interval `I` and transition `T` uses one interval per effect. The first `I - T` seconds show only the current effect. The last `T` seconds render outgoing elapsed time and incoming elapsed time starting at zero at transition start, blend them, apply brightness once, then send one logical frame. At the interval boundary, the incoming effect becomes primary with elapsed time continuing from `T` rather than resetting to zero. Playlist wrap starts a fresh first-effect instance at the wrap transition. `T` may be zero and must satisfy `0 <= T < I`.

```bash
thunderdome effect auto \
  --preset calm \
  --interval 30 \
  --crossfade 2 \
  --brightness 24

thunderdome effect auto \
  --playlist fire,aurora,fireflies \
  --cycles 1 \
  --interval 0.4 \
  --transition 0.1 \
  --fps 5 \
  --output null

thunderdome effect radar \
  --output both \
  --controllers config/controllers.json \
  --duration 20
```
