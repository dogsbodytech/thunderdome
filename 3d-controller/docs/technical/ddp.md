# DDP reference

Python chooses the RGB value for every physical LED and sends RGB8 frames to WLED over UDP DDP. Current destination port is **4048**. WLED does not know XYZ coordinates.

## Direct five-way fan-out

`ddp-all` builds one logical 5,000-pixel frame, then sends five local 1,000-pixel slices directly:

| Human controller | Address | Internal `string_id` | Global slice | Local slice |
| ---: | --- | ---: | --- | --- |
| 1 | `192.168.12.10` | 0 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | 4000..4999 | 0..999 |

Controller 1 is not a DDP master or relay for the Python path. The default packet chunk is 480 LEDs; the local controller configuration records this value.

## One-shot, held, and repeated frames

`ddp clear`, `solid`, `pixel`, and `range` send one frame and exit unless a loop mode is selected. `--hold`, `--duration`, and `--loops` are mutually exclusive. `--fps` is 1–60 and defaults to 20 for static loop modes. A one-shot can disappear when WLED's realtime timeout restores its prior state/effect.

Safe local preview uses the effect sink, not direct `ddp`:

```bash
thunderdome effect Fire \
  --output simulator \
  --duration 10 \
  --brightness 255
```

Physical single-controller test:

```bash
thunderdome ddp solid \
  --host 192.168.12.10 \
  --led-count 1000 \
  --color FF0000 \
  --brightness 255 \
  --duration 2 \
  --fps 10
```

Direct `ddp` commands always target WLED; they have no simulator output mode. Use them only in [first light and DDP](../runbooks/03-first-light-and-ddp.md).

## Live mode and WLED state

The CLI can read/set WLED state separately from DDP:

```bash
thunderdome controller live --host 192.168.12.10 on
thunderdome controller live --host 192.168.12.10 off
thunderdome controllers live --controllers config/controllers.json on
thunderdome controllers live --controllers config/controllers.json off
```

The multi-controller command attempts every enabled device and returns non-zero if any update fails. Live application effect output also sets WLED master brightness to `255` before opening the DDP session. It does not change WLED current-limit settings. The removed effect option `--prepare-ddp` must not be added to current effect examples.

## Output safety

- `--output simulator`: local preview; no WLED HTTP/UDP.
- `--output null` or effect `--dry-run`: render and discard; no network output.
- `ddp-all --dry-run`: one allocation/packet simulation; no UDP sockets or packets.
- `--output ddp`: physical DDP; explicit.
- `--output both`: simulator plus physical DDP; explicit.

`ddp-all --dry-run` cannot be combined with `--hold`, `--duration`, or `--loops`. Simulator failures never fall back to DDP.

## Spatial effects

`ClockHand`, `ExpandingRings`, `HeightWave`, `Fire`, `RotatingPlane`, `Radar`, `Aurora`, `Fireflies`, `Twinkle`, and the solar-system effects are Python-rendered. They produce the same logical 5,000-pixel shape and use the selected sink. Physical examples must specify `--output ddp`; renderer options are in [effects](effects.md).
