# Software and interactive features

This repository's active lighting software is the Python controller in [`3d-controller/`](3d-controller/). It renders the dome spatially in Python and uses five WLED devices only as direct DDP-over-UDP LED outputs.

## Contents

- [Controller architecture](#controller-architecture)
- [Install and configure](#install-and-configure)
- [Controller mapping](#controller-mapping)
- [Test and safely dry run DDP](#test-and-safely-dry-run-ddp)
- [Realtime control and frame streaming](#realtime-control-and-frame-streaming)
- [WLED mapping](#wled-mapping)
- [Audio control](#audio-control)
- [SIP to audio feed](#sip-to-audio-feed)

## Controller architecture

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

Validated structure and confirmed physical routes determine the generated XYZ LED positions. Python effects render one logical 5,000-pixel RGB frame, which the controller divides into five direct, local 1,000-pixel DDP frames. WLED does not calculate spatial positions or receive a relayed frame through controller 1.

The controller's complete operating guide is [`3d-controller/README.md`](3d-controller/README.md).

## Install and configure

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

cp config/controllers.example.json config/controllers.json
```

`config/controllers.json` is intentionally ignored by Git. Set its `host` values to the deployed controller addresses, then run `thunderdome controllers validate --controllers config/controllers.json`.

## Controller mapping

| Controller | Address | String | Start hub | Global LEDs | Local LEDs |
| --- | --- | ---: | --- | --- | --- |
| 1 | `192.168.12.10` | 0 | H032 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | H033 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | H034 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | H035 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | H031 | 4000..4999 | 0..999 |

## Test and safely dry run DDP

With the virtual environment active, run the automated tests and validate the geometry, routes, and positions:

```bash
python3 -m unittest discover -s controller/tests -v
thunderdome geometry validate
thunderdome route validate
thunderdome positions generate
thunderdome positions validate
```

Before sending any lighting data, use a multi-controller dry run:

```bash
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 \
  --dry-run
```

The dry run validates the configuration and frame fan-out but does not open sockets or send UDP packets. Once its reported controller allocation and packet counts are correct, remove `--dry-run` only when the DDP network and hardware are ready. Start at low brightness.

## Realtime control and frame streaming

One-shot DDP commands send one frame and exit. Because WLED can exit realtime mode after its realtime timeout, use a repeated frame when the displayed state must remain active.

Use WLED live mode explicitly when needed:

```bash
thunderdome controller live --host 192.168.12.10 on
thunderdome controller live --host 192.168.12.10 off
thunderdome controllers live --controllers config/controllers.json on
thunderdome controllers live --controllers config/controllers.json off
```

Static `ddp` and `ddp-all` commands support mutually exclusive `--hold`, `--duration SECONDS`, and `--loops COUNT` controls. A loop defaults to 20 FPS; `--fps` accepts 1..60. The Python application, not a shell loop, owns the monotonic frame schedule and keeps one UDP socket per controller open for the whole session.

```bash
# Stream a single controller until Ctrl+C.
thunderdome ddp pixel --host 192.168.12.10 --led-count 1000 \
  20 --color FF0000 --brightness 255 --hold --fps 20

# Stream the logical 5,000-pixel controller-identification frame for five seconds.
thunderdome ddp-all controller-colors --controllers config/controllers.json \
  --brightness 16 --duration 5 --fps 20
```

Ctrl+C stops a held stream cleanly and reports frame and elapsed-time statistics. `--dry-run` remains one-shot and is rejected with `--hold`, `--duration`, or `--loops` so it can never accidentally stream UDP data.

The same reusable frame-loop abstraction accepts static frames, generated frames, and frame generators. Future spatial effects, such as a moving clock hand around the dome, can produce a different 5,000-pixel frame on each iteration and reuse the same scheduler and DDP transports.

## WLED Mapping

WLED has native [2D LED mapping](https://kno.wled.ge/advanced/mapping/), but it is not used as the active mapping authority. Accurately representing 5,000 LEDs at the required spacing would need a grid of at least 600 x 600: 360,000 positions, of which 355,000 are empty. That map is too large for WLED to store and use effectively.

XYZ positions and effects therefore remain in the Python controller; WLED receives only its local RGB DDP frame.

## Audio Control

The WLED controllers do not contain microphones, but audio can be sent from a laptop using [WLED audio sync from a PC](https://kno.wled.ge/advanced/audio-reactive/#audio-sync-from-a-pc). This is separate from the active Python spatial-rendering path.

## SIP to audio feed

A possible future interactive feature is connecting the on-site EMF phone/SIP system to an audio feed, allowing callers to influence dome lighting from their voice or nearby sound.