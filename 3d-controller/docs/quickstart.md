# Quickstart

Run these commands from the controller directory after cloning the repository and activating its virtual environment:

```bash
cd thunderdome/3d-controller
python3 -m pip install -e .
python3 -m unittest discover -s controller/tests -v
thunderdome geometry validate
```

## Open the offline simulator

Stage A of the simulator is a local static geometry viewer. It shows the authoritative hubs, spars, H061 apex, optional real hub-ID labels, tails, and all 5,000 generated XYZ LEDs with five diagnostic string colours. Enable **Hub labels** to display each hub ID; H061 has distinct apex styling. It does not stream effects, contact WLED, send DDP, or change output defaults.

```bash
thunderdome positions validate
thunderdome simulator serve --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`. The viewer is fully offline at runtime; Three.js r160 / 0.160.0, OrbitControls, and the Three.js licence are vendored under `simulator/static/vendor/`. Use `--open-browser` to ask Python to open the browser automatically, or `--no-open-browser` for terminal-only startup. See [simulator.md](simulator.md) for API endpoints, controls, LED lookup, and binding notes for `0.0.0.0`.

To inspect a matched custom data set, provide all three compatible paths. Defaults are project-root-safe; explicit relative paths remain relative to the current shell directory.

```bash
thunderdome simulator serve \
  --geometry geometry/thunderdome_geometry.json \
  --routes geometry/reference_string_route.md \
  --positions geometry/generated/led_positions_3d.json \
  --open-browser
```

## Realtime live mode

WLED's HTTP live-mode setting is separate from DDP frame transmission. Use it to explicitly enable or disable realtime live mode on one controller or every enabled controller in the local configuration:

```bash
thunderdome controller live --host 192.168.12.10 on
thunderdome controller live --host 192.168.12.10 off

thunderdome controllers live --controllers config/controllers.json on
thunderdome controllers live --controllers config/controllers.json off
```

The multi-controller command continues through all enabled controllers, reports each result, and returns a non-zero status if any controller fails.

## Send, hold, or repeat DDP frames

Single-controller `ddp clear`, `solid`, `pixel`, and `range` commands default to **1,000 LEDs**. With no loop option, they send one DDP frame and exit. A one-shot frame may be replaced when WLED's realtime timeout expires and WLED restores its previous state or effect.

For output that must remain active, use one of the mutually exclusive loop controls:

- `--hold` — resend until Ctrl+C.
- `--duration SECONDS` — resend for approximately the requested positive duration.
- `--loops COUNT` — resend exactly the requested positive number of frames.
- `--fps FPS` — loop rate from 1 to 60 FPS; the default loop rate is 20 FPS.

Ctrl+C is a normal stop condition: the command closes its UDP socket(s) cleanly and reports frames sent and elapsed time.

```bash
# Hold a red pixel on a single 1,000-pixel controller until Ctrl+C.
thunderdome ddp pixel \
  --host 192.168.12.10 \
  --led-count 1000 \
  20 --color FF0000 --brightness 255 \
  --hold --fps 20
```

`ddp-all` instead constructs one logical **5,000-pixel** RGB frame, splits it into five local 1,000-pixel controller frames, and sends them directly to the five enabled WLED controllers.

```bash
# Hold distinct identification colours on all five controllers until Ctrl+C.
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 \
  --hold --fps 20
```

Use `--dry-run` only for one simulated `ddp-all` frame. It sends no UDP traffic and cannot be combined with `--hold`, `--duration`, or `--loops`.

HTTP/native effects and favorites are optional support functions, not the animation renderer.

## Prepare and run spatial effects

Generate and validate nominal positions, then manually power controllers and set WLED master brightness before application DDP:

```bash
thunderdome positions generate
thunderdome positions validate
thunderdome controllers power on --controllers config/controllers.json
thunderdome controllers brightness 255 --controllers config/controllers.json
thunderdome effect clock-hand --controllers config/controllers.json --geometry geometry/thunderdome_geometry.json --positions geometry/generated/led_positions_3d.json --brightness 32 --color FFFFFF --background 000000 --width-mm 300 --rotation-seconds 3 --fps 30 --hold
```

Effect commands do not modify persistent WLED state before streaming. Controllers must already be powered on with suitable WLED master brightness. The earlier `--prepare-ddp` option was removed because setting WLED off before realtime streaming caused animations to disappear. The hand centre is H061's authoritative XY coordinate; zero degrees is world `+X` and clockwise is viewed from above. All 5,000 generated XYZ records, including tails, participate by default. Tails share H061 XY and normally light the centre continuously; use `--exclude-tail` when that is not desired.

`expanding-rings` and `height-wave` use the same generated 5,000-record XYZ context and direct multi-controller DDP output. `expanding-rings` is a true XYZ spherical shell with `--origin apex|centre|base|X,Y,Z`, `--speed-mps`, and full `--thickness-mm`. `height-wave` uses actual selected Z bounds with `--direction up|down|bounce`, `--speed-mps`, and full `--height-mm`. Tails participate by default; use `--exclude-tail` to remove them. Spatial `--loops`, `--duration`, and `--hold` are mutually exclusive; a bounce loop is a complete out-and-back. See [effects.md](effects.md) for origin definitions and all options.

Additional implemented effects are `fire`, `rotating-plane`, `radar`, `aurora`, and `fireflies`. They all use the generated XYZ data rather than LED index order. Fire, aurora, and fireflies use `--duration`/`--hold`; rotating-plane and radar also expose meaningful `--loops`. `rotating-plane --axis` is a real 3D rotation axis (`vertical=(0,0,1)`, `horizontal=(1,0,0)`, `tilted=normalize(1,1,1)`, or explicit `X,Y,Z`). Its plane/trail samples are precomputed once per frame, `--trail-degrees 0` disables the directional fading trail, and the accepted trail range is `0..180` with values above 180 rejected. `thunderdome effect auto` cycles continuously by default and supports `--interval`, `--crossfade`/`--transition`, `--playlist`/`--effects`, `--preset calm|energetic`, finite `--cycles` or `--duration`, and linear RGB crossfade with brightness applied once after blending while preserving incoming effect time across transition boundaries.

```bash
thunderdome effect expanding-rings \
  --controllers config/controllers.json --origin apex --speed-mps 1.0 \
  --thickness-mm 250 --brightness 24 --loops 1 --dry-run

thunderdome effect auto \
  --controllers config/controllers.example.json \
  --preset calm \
  --loops 1 \
  --dry-run

thunderdome effect height-wave \
  --controllers config/controllers.json --direction bounce --height-mm 300 \
  --brightness 24 --hold
```

Run `thunderdome controllers power on --controllers config/controllers.json` and `thunderdome controllers brightness 255 --controllers config/controllers.json` when manual readiness is needed. Effects no longer prepare WLED automatically; `--dry-run` exercises rendering/scheduling without HTTP or UDP traffic. Start at low brightness; Ctrl+C cleanly ends a held or continuous stream.