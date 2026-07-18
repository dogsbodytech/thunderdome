# Thunderdome 3D Controller

Thunderdome is a 3V 5/8 geodesic LED dome: **61 hubs**, **165 spars** (30 A, 55 B, 80 C), and five physical strings of 1,000 LEDs. LEDs follow spars; H061 is the apex.

## Active architecture

```text
validated geometry
-> confirmed physical string routes
-> generated XYZ LED positions
-> Python effects
-> one logical 5,000-pixel RGB frame
-> five 1,000-pixel controller frames
-> DDP over UDP
-> five WLED controllers
```

Python owns spatial rendering and converts effects into the one logical 5,000-pixel RGB frame. The controller splits that frame into five local 1,000-pixel frames, then sends each frame directly to its WLED controller using DDP over UDP (default port 4048). WLED is the network LED output/controller; it does not own the XYZ mapping, and its native 2D ledmap is not an active mapping authority.

- Geometry: `geometry/thunderdome_geometry.json`
- Editable Blender source: `assets/blender/thunderdome_3v_5_8_scaled.blend`
- Confirmed reference route: `geometry/reference_string_route.md`
- Generated positions: `geometry/generated/led_positions_3d.json`
- Active Python package: `controller/thunderdome/`
- Offline Stage A simulator: `simulator/static/` and `docs/simulator.md`
- Tests: `controller/tests/`
- Historical experiments: `archive/`

All five manually captured routes are authoritative. Their generated XYZ positions are nominal mathematical coordinates through exact hub centres, with no hub correction or symmetry inference. The first tail LED is the next 30 mm nominal position after the route endpoint, so it is offset below H061 by the residual pitch distance. Future calibration may adjust pitch, first offset, and tail geometry.

## Clone and install

From a new machine, clone the repository and install the controller in an isolated virtual environment:

```bash
git clone https://github.com/dogsbodytech/thunderdome.git
cd thunderdome/3d-controller

sudo apt update
sudo apt install python3-venv

python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install --upgrade pip
python3 -m pip install -e .

thunderdome --help
```

The package requires Python 3.11 or later. Reactivate the environment with `source .venv/bin/activate` in each new shell before using `thunderdome`.

## Configure the five controllers

Create a local configuration file before using the multi-controller commands:

```bash
cp config/controllers.example.json config/controllers.json
```

`config/controllers.json` is intentionally ignored by Git so each installation can keep its local controller addresses. Update its five `host` values to match the deployed controller addresses below, then validate the file:

```bash
thunderdome controllers validate --controllers config/controllers.json
thunderdome controllers summary --controllers config/controllers.json
```

| Controller | Address | String | Start hub | Global LEDs | Local LEDs |
| --- | --- | ---: | --- | --- | --- |
| 1 | `192.168.12.10` | 0 | H032 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | H033 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | H034 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | H035 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | H031 | 4000..4999 | 0..999 |

The global ranges form the one logical frame. Each controller receives only its corresponding 1,000-pixel slice as local LEDs `0..999`; frames are sent directly to all enabled controllers, never relayed through controller 1.

## Test the controller

Run the automated tests and validate the data pipeline before connecting to hardware:

```bash
python3 -m unittest discover -s controller/tests -v
thunderdome geometry validate
thunderdome route validate
thunderdome positions generate
thunderdome positions validate
```

## Offline static simulator

Stage A of the simulator is a local browser viewer for authoritative dome geometry, routes, and generated LED positions. It renders hubs, spars, H061, optional real hub-ID labels, tails, and all 5,000 generated XYZ LED records with diagnostic string/controller colours. It does **not** stream live effect frames, change default output, contact WLED, or send DDP packets.

```bash
thunderdome simulator serve
# then open http://127.0.0.1:8080/
```

The simulator is fully offline at runtime. Three.js r160 / 0.160.0, OrbitControls, and the Three.js licence notice are vendored under `simulator/static/vendor/`; no npm install or remote CDN is required. Use `--host`, `--port`, `--geometry`, `--routes`, `--positions`, and `--open-browser`/`--no-open-browser` to customize serving. Defaults are project-root-safe; explicit relative paths remain relative to the calling directory. Geometry, routes, and positions must describe the same dome. See `docs/simulator.md` for API endpoints, controls, path rules, and the implications of binding to `0.0.0.0`.

## Safe DDP dry run

Perform a dry run first. It validates the local controller configuration, creates a logical 5,000-pixel frame, splits it into five 1,000-pixel frames, and reports the DDP packet counts. `--dry-run` does **not** open network sockets or send UDP packets.

```bash
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 \
  --dry-run
```

`controller-colors` gives each controller's local frame a distinct colour in the generated frame. After confirming the dry-run output and only when the hardware/network is ready, remove `--dry-run` to transmit it. Start at low brightness. Other multi-controller commands are `ddp-all clear` and `ddp-all solid --color FF0000 --brightness 16`.

For a single-controller diagnostic, use `thunderdome ddp clear --host WLED_HOST` or `thunderdome ddp pixel --host WLED_HOST 0 --color FF0000 --brightness 16`; these commands transmit immediately, so do not use them as a dry-run substitute.

## Application-rendered spatial effects

The `thunderdome effect` commands render from generated 5,000-LED XYZ positions and then reuse the existing multi-controller DDP fan-out. Implemented effects are `clock-hand`, `expanding-rings`, `height-wave`, `fire`, `rotating-plane`, `radar`, `aurora`, `fireflies`, and `auto` showcase mode.

Generate positions first, use dry-run before hardware, and start at safe brightness:

```bash
thunderdome positions generate
thunderdome effect auto \
  --controllers config/controllers.example.json \
  --playlist fire,aurora,fireflies \
  --loops 1 \
  --dry-run

thunderdome effect auto \
  --controllers config/controllers.json \
  --preset calm \
  --brightness 24
```

Effect commands do not modify persistent WLED state before streaming. Controllers must already be powered on with suitable WLED master brightness. The earlier `--prepare-ddp` option was removed because setting WLED off before realtime streaming caused animations to disappear. `rotating-plane` uses true 3D axis rotation (`vertical=(0,0,1)`, `horizontal=(1,0,0)`, `tilted=normalize(1,1,1)`, or explicit `X,Y,Z`) and precomputes its plane/trail samples once per frame; LEDs then only do signed-distance work against the bounded samples. `--trail-degrees` accepts `0..180`, where zero disables the trail and values above 180 are rejected. Auto crossfades preserve incoming effect time across interval boundaries. See `docs/effects.md` for all options, playlist syntax, origin definitions, height-wave directions, tails, and Ctrl+C behavior.

## Realtime live mode and DDP streaming

A normal `ddp clear`, `solid`, `pixel`, or `range` command sends **one** DDP frame and exits. WLED may leave realtime mode when its configured realtime timeout expires, then restore its previous WLED effect. Use a held frame or animation loop when output must remain active.

### Set WLED realtime live mode

Use the WLED JSON state API through the controller CLI to explicitly enable or disable WLED live mode:

```bash
thunderdome controller live --host 192.168.12.10 on
thunderdome controller live --host 192.168.12.10 off

thunderdome controllers live --controllers config/controllers.json on
thunderdome controllers live --controllers config/controllers.json off
```

The multi-controller form attempts every enabled controller and reports each result; it returns a non-zero status if any controller cannot be updated.

### Hold or repeat a static frame

`--hold`, `--duration`, and `--loops` use the same Python frame-loop engine as future animations. They are mutually exclusive. `--fps` defaults to 20 when a loop mode is used and must be in the range 1..60. Each session reuses its UDP socket(s), rather than creating a socket per frame. Ctrl+C stops cleanly and reports frames sent and elapsed time.

```bash
# Keep one red pixel active until Ctrl+C.
thunderdome ddp pixel \
  --host 192.168.12.10 \
  --led-count 1000 \
  20 --color FF0000 --brightness 255 \
  --hold --fps 20

# Keep a low-brightness blue frame active for 10 seconds.
thunderdome ddp solid \
  --host 192.168.12.10 \
  --led-count 1000 \
  --color 0000FF --brightness 32 \
  --duration 10 --fps 20

# Send exactly 100 copies of a static frame.
thunderdome ddp pixel \
  --host 192.168.12.10 \
  --led-count 1000 \
  20 --color FF0000 --brightness 255 \
  --loops 100 --fps 20
```

The same controls apply to the one logical 5,000-pixel multi-controller frame:

```bash
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 --hold --fps 20

thunderdome ddp-all clear \
  --controllers config/controllers.json \
  --duration 5 --fps 10

thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 --loops 200 --fps 20
```

`ddp-all --dry-run` remains deliberately one-shot and never opens UDP sockets or sends UDP packets. It cannot be combined with `--hold`, `--duration`, or `--loops`.

### Future spatial animations

The reusable `thunderdome.animation.run_frame_loop` accepts either a static-frame callback, a callback that receives `(frame_number, elapsed_seconds)`, or a frame generator. This lets an effect render a different 5,000-pixel `RGBFrame` for each iteration while retaining the same scheduler and direct-DDP transports. A future clock-face or clock-hand sweep can therefore generate a frame from its current angle on each tick, then use the normal single- or multi-controller sender.

See `docs/architecture.md` and `docs/ddp.md` for supporting detail.

## Persistent WLED control and spatial effects

WLED JSON commands address each enabled controller explicitly; controller 1 is not a master for JSON or application DDP output. Use `controller power|brightness|color|effect|palette|preset|live|prepare-ddp` for one host, and the matching `controllers` commands for every enabled host. Effect commands do not invoke those persistent-state operations automatically; power on controllers and set suitable WLED master brightness manually before streaming.

```bash
thunderdome positions generate
thunderdome positions validate
thunderdome controllers power on --controllers config/controllers.json
thunderdome controllers brightness 255 --controllers config/controllers.json
thunderdome effect clock-hand --controllers config/controllers.json \
  --positions geometry/generated/led_positions_3d.json --brightness 32 \
  --color FFFFFF --background 000000 --width-mm 300 \
  --rotation-seconds 3 --fps 30 --hold
```

`clock-hand` renders all 5,000 LED records from generated XYZ data and fans them out over DDP. Its centre is authoritative geometry hub H061's XY coordinate, never an LED-derived bound or average. Width is the full visible width in millimetres; zero degrees points along world `+X`; clockwise is viewed from above; and `--angle-offset-degrees` aligns the installation. Tails are included by default; use `--exclude-tail` to omit them. Because tails descend from H061 and share its XY location, they normally form a continuously lit centre at every angle.

The implemented spatial effects are `clock-hand`, `expanding-rings`, `height-wave`, `fire`, `rotating-plane`, `radar`, `aurora`, `fireflies`, and `auto`; see [`docs/effects.md`](docs/effects.md) for the complete command table and operational guidance. `expanding-rings` is a true XYZ spherical shell rather than a flat XY ring. Its `--origin` accepts `apex` (H061 XYZ), `centre` (H061 X/Y plus the midpoint of dome-only Z bounds), `base` (H061 X/Y plus dome-only minimum Z), or explicit `X,Y,Z` metres. Tails use real XYZ positions by default; `--exclude-tail` explicitly removes them.

```bash
# True XYZ spherical shell expands from H061.
thunderdome effect expanding-rings \
  --controllers config/controllers.json \
  --origin apex --speed-mps 1.0 --thickness-mm 250 \
  --brightness 24 --loops 2

# A full-height bouncing band reverses at the selected Z bounds.
thunderdome effect height-wave \
  --controllers config/controllers.json \
  --direction bounce --height-mm 300 --brightness 24 --hold
```

For effects that expose `--loops`, loop controls are mutually exclusive with `--duration` and `--hold`. Fire, aurora, and fireflies use `--duration` or `--hold` instead of loops. Use `--dry-run` first to validate local configuration and real scheduler frame generation without UDP or HTTP. Start at low brightness and Ctrl+C cleanly stops held or auto output.

To restore native fallback output, address every controller (for example `controllers power ... on`, `controllers brightness ... 64`, then `controllers effect ... EFFECT_ID`). Native WLED effects run independently and are not guaranteed spatially or phase synchronized; use Pi-rendered DDP for one coherent dome effect.