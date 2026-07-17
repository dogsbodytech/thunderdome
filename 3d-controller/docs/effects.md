# Spatial effects

Thunderdome renders effects in Python from `geometry/generated/led_positions_3d.json`, then fans one exact 5,000-pixel (15,000-byte RGB) frame out as five local DDP frames. Generate positions before use:

```bash
thunderdome positions generate
thunderdome positions validate
```

Built-in default geometry, positions, and controller paths are anchored at the project root, so they work from the repository root, `3d-controller/`, or another working directory. Explicit relative paths remain relative to the process working directory.

| Effect | Spatial basis | Important options | Default finite behaviour | Example |
| --- | --- | --- | --- | --- |
| `clock-hand` | Forward XY half-ray from H061 XY | `--width-mm`, `--rotation-seconds`, `--direction`, `--rotations` | One rotation | `thunderdome effect clock-hand --brightness 24 --rotations 1` |
| `expanding-rings` | True XYZ Euclidean spherical shell | `--origin`, `--speed-mps`, `--thickness-mm`, `--loops` | One complete shell expansion | `thunderdome effect expanding-rings --origin apex --loops 1 --brightness 24` |
| `height-wave` | Horizontal band over selected physical Z bounds | `--direction`, `--speed-mps`, `--height-mm`, `--loops` | One complete movement cycle | `thunderdome effect height-wave --direction bounce --loops 1 --brightness 24` |

## Expanding spherical shell

`expanding-rings` is a true 3D spherical shell, not a flat XY ring. Each LED uses `sqrt((x-origin_x)^2 + (y-origin_y)^2 + (z-origin_z)^2)`. LEDs within half `--thickness-mm` of the elapsed-time shell radius are illuminated. The radius increases at `--speed-mps` and wraps after the maximum selected LED distance from the origin.

`--origin` defaults to `apex`:

- `apex`: authoritative H061 XYZ from `geometry/thunderdome_geometry.json`.
- `centre`: H061 X/Y and the midpoint between H061 Z and the **dome-only** minimum Z.
- `base`: H061 X/Y and the **dome-only** minimum Z.
- `X,Y,Z`: three floating-point coordinates in metres, for example `0.0,0.0,1.5`.

Tails use their real XYZ coordinates by default. Use `--exclude-tail` only when they should not participate.

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

## Height wave

`height-wave` selects a full-thickness `--height-mm` horizontal band from actual selected Z coordinates. Tails are included by default, so their Z coordinates contribute to the range unless `--exclude-tail` is given.

- `--direction up` (default) travels minimum Z to maximum Z, then wraps.
- `--direction down` travels maximum Z to minimum Z, then wraps.
- `--direction bounce` travels to the far bound and reverses cleanly. One `--loops 1` is a full out-and-back cycle; for `up` or `down`, one loop is one traversal and wrap.

```bash
thunderdome effect height-wave \
  --controllers config/controllers.json \
  --direction bounce \
  --height-mm 300 \
  --brightness 24 \
  --hold
```

## Running safely

For spatial effects, `--loops COUNT`, `--duration SECONDS`, and `--hold` are mutually exclusive. `--loops` is a positive integer; finite defaults are one complete effect cycle. `--fps` controls frame rate (1..60, default 30). Ctrl+C ends a held stream cleanly, closes DDP sockets, and reports frame statistics. Start at low brightness such as `--brightness 24`.

`--dry-run` renders and validates one frame without opening UDP sockets. It also performs no HTTP requests. With `--dry-run --prepare-ddp`, the command reports that preparation would occur and skips it.

`--prepare-ddp` performs the existing multi-controller WLED preparation exactly once, before DDP streaming: it posts `{"on": false, "bri": 255, "live": false}` to every enabled controller. This makes persistent WLED fallback off while retaining WLED master brightness 255; Python `--brightness` controls the streamed frame. The operation continues through enabled controllers to report every failure, but aborts before DDP and returns non-zero if any preparation fails.

```bash
thunderdome effect height-wave \
  --controllers config/controllers.json \
  --direction bounce \
  --brightness 24 \
  --prepare-ddp \
  --hold
```
