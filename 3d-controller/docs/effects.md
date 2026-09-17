# Effects reference

Effects render from `geometry/generated/led_positions_3d.json` into one logical 5,000-pixel RGB frame. The default preview destination is the local simulator. Physical output is never implied in the operational examples below: use `--output ddp --controllers config/controllers.json` deliberately.

Prepare positions first:

```bash
thunderdome positions generate
thunderdome positions validate
```

## Output and brightness

| Output | Meaning |
| --- | --- |
| `--output simulator` | Local browser WebSocket; no WLED traffic. |
| `--output null` | Render/schedule but discard; no network traffic. |
| `--output ddp --controllers config/controllers.json` | Direct physical DDP. |
| `--output both --controllers config/controllers.json` | Same rendered frame to simulator and physical DDP. |

Normal operational brightness is `255`. Valid 8-bit values are `0..255`; `256` is invalid. Live DDP prepares WLED master brightness at `255`, but does not change WLED current-limit settings. Confirm physical power/current configuration before first light.

## Effect table

| Effect | Spatial basis | Cycle/duration controls | Safe simulator example |
| --- | --- | --- | --- |
| `clock-hand` | Forward XY half-ray from H061 XY | `--rotations`, `--duration`, `--hold` | `thunderdome effect clock-hand --output simulator --brightness 255 --rotations 1` |
| `expanding-rings` | True XYZ spherical shell | `--loops`, `--duration`, `--hold` | `thunderdome effect expanding-rings --output simulator --origin apex --brightness 255 --loops 1` |
| `height-wave` | Horizontal band over selected Z bounds | `--loops`, `--duration`, `--hold` | `thunderdome effect height-wave --output simulator --direction bounce --brightness 255 --duration 10` |
| `fire` | XYZ height/radius/turbulence | `--duration`, `--hold` | `thunderdome effect fire --output simulator --brightness 255 --duration 10` |
| `rotating-plane` | Signed distance to a 3D plane | `--loops`, `--duration`, `--hold` | `thunderdome effect rotating-plane --output simulator --axis tilted --brightness 255 --loops 1` |
| `radar` | Angular sweep around dome centre | `--loops`, `--duration`, `--hold` | `thunderdome effect radar --output simulator --brightness 255 --duration 10` |
| `aurora` | Layered XYZ waves | `--duration`, `--hold` | `thunderdome effect aurora --output simulator --brightness 255 --duration 10` |
| `fireflies` | Moving 3D particles and glow | `--duration`, `--hold` | `thunderdome effect fireflies --output simulator --brightness 255 --duration 10` |
| `twinkle` | Stateful per-LED sparkles | `--duration`, `--hold` | `thunderdome effect twinkle --output simulator --brightness 255 --duration 10` |
| solar-system bodies | Fixed palette over XYZ positions | `--duration`, `--hold` | `thunderdome effect Mars --output simulator --brightness 255 --duration 10` |
| `auto` | Registry playlist and crossfade | `--cycles`, `--duration` or Ctrl+C | `thunderdome effect auto --output simulator --preset calm --brightness 255 --duration 30` |

`--fps` is 1–60 and defaults to 30 for effects. `--output null` is useful for a no-network renderer smoke test. `--dry-run` is an alias for null for effects; Auto dry runs require a finite `--cycles` or `--duration`.

## Spatial details

### Clock hand

`clock-hand` is centred on the authoritative XY coordinate of H061. Zero degrees points along world `+X`; clockwise is viewed from above. `--width-mm` is the full visible width. Tails are included by default; `--exclude-tail` omits them.

### Expanding rings

`expanding-rings` is a spherical XYZ shell, not a flat XY ring. `--origin` accepts:

- `apex` — H061 XYZ;
- `centre` — H061 X/Y and the midpoint between H061 Z and the dome-only minimum Z;
- `base` — H061 X/Y and dome-only minimum Z;
- `X,Y,Z` — explicit metres.

`--thickness-mm` is the full luminous shell thickness and `--speed-mps` controls travel. One `--loops` value is one shell expansion.

### Height wave

`height-wave` moves a full `--height-mm` horizontal band across the selected actual Z range. `up` and `down` wrap at the bound; `bounce` reverses and one loop is out-and-back. Tails are included unless `--exclude-tail` is used.

### Procedural effects

- `fire` uses height, radius, deterministic turbulence, cooling, scale, palette, and seed.
- `rotating-plane` rotates a plane around `vertical=(0,0,1)`, `horizontal=(1,0,0)`, `tilted=normalize(1,1,1)`, or finite non-zero `X,Y,Z`. `--trail-degrees` accepts `0..180`; zero disables the trail and values above 180 are rejected.
- `radar` sweeps an angular beam with configurable width, trail, range, and vertical falloff.
- `aurora` uses layered deterministic waves and `--direction X,Y,Z`.
- `fireflies` uses deterministic seeded moving 3D particles and true distance falloff.
- `twinkle` uses stateful per-LED fade-in/hold/fade-out sparkles.

### Solar-system effects

`Sol`, `Mercury`, `Venus`, `Earth`, `Mars`, `Jupiter`, `Saturn`, `Uranus`, `Neptune`, `AsteroidBelt`, `KuiperBelt`, and `Voyager1` use fixed palettes/styles. Only speed and seed are tunable.

## Auto

The default playlist is:

```text
clock-hand, expanding-rings, height-wave, fire, rotating-plane, radar, aurora, fireflies
```

Presets are `calm`, `energetic`, and `solar-system`. Use `--playlist` or `--effects` with a comma-separated list. Empty, duplicate, unknown, or non-auto-capable entries are rejected. `--shuffle --seed N` shuffles once deterministically.

`--interval` must be positive. `--transition`/`--crossfade` must satisfy `0 <= transition < interval`. Crossfade blends full-brightness source frames, then applies the requested brightness once. Incoming effect time continues across the interval boundary rather than rewinding.

## Physical example

After [physical startup](runbooks/physical-dome-startup.md) and [first light](runbooks/first-light-and-ddp.md), a deliberate physical preview is:

```bash
thunderdome effect height-wave \
  --output ddp \
  --controllers config/controllers.json \
  --direction bounce \
  --brightness 255 \
  --duration 20
```

Stop a held/continuous physical effect with `Ctrl+C`; see [shutdown](runbooks/shutdown.md).
