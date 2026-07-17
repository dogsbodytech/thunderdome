# Quickstart

Run these commands from the controller directory after cloning the repository and activating its virtual environment:

```bash
cd thunderdome/3d-controller
python3 -m pip install -e .
python3 -m unittest discover -s controller/tests -v
thunderdome geometry validate
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

Generate and validate nominal positions, then establish the persistent off fallback before application DDP:

```bash
thunderdome positions generate
thunderdome positions validate
thunderdome controllers prepare-ddp --controllers config/controllers.json
thunderdome effect clock-hand --controllers config/controllers.json --geometry geometry/thunderdome_geometry.json --positions geometry/generated/led_positions_3d.json --brightness 32 --color FFFFFF --background 000000 --width-mm 300 --rotation-seconds 3 --fps 30 --hold
```

`prepare-ddp` posts `{"on":false,"bri":255,"live":false}` in one JSON update to each enabled controller, so a DDP timeout falls back to off rather than a bright native effect. The hand centre is H061's authoritative XY coordinate; zero degrees is world `+X` and clockwise is viewed from above. All 5,000 generated XYZ records, including tails, participate by default. Tails share H061 XY and normally light the centre continuously; use `--exclude-tail` when that is not desired.

`expanding-rings` and `height-wave` use the same generated 5,000-record XYZ context and direct multi-controller DDP output. `expanding-rings` is a true XYZ spherical shell with `--origin apex|centre|base|X,Y,Z`, `--speed-mps`, and full `--thickness-mm`. `height-wave` uses actual selected Z bounds with `--direction up|down|bounce`, `--speed-mps`, and full `--height-mm`. Tails participate by default; use `--exclude-tail` to remove them. Spatial `--loops`, `--duration`, and `--hold` are mutually exclusive; a bounce loop is a complete out-and-back. See [effects.md](effects.md) for origin definitions and all options.

```bash
thunderdome effect expanding-rings \
  --controllers config/controllers.json --origin apex --speed-mps 1.0 \
  --thickness-mm 250 --brightness 24 --loops 1 --dry-run

thunderdome effect height-wave \
  --controllers config/controllers.json --direction bounce --height-mm 300 \
  --brightness 24 --prepare-ddp --hold
```

`--prepare-ddp` sends the persistent WLED fallback `{"on":false,"bri":255,"live":false}` once per enabled controller before Python streams DDP; it aborts before DDP on a preparation failure. With `--dry-run`, preparation is only reported and no HTTP or UDP traffic is made. Start at low brightness; Ctrl+C cleanly ends a held stream.