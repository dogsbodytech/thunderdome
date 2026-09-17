# WLED and DDP reference

## Responsibilities

```text
Python geometry + routes + XYZ positions
                  |
                  v
       Python effect renderer (5,000 RGB pixels)
                  |
         split global ranges 0..999 ... 4000..4999
            |          |                  |
            v          v                  v
       WLED 1       WLED 2       ...     WLED 5
            |          |                  |
        physical string 1 ... physical string 5
```

**WLED** owns hardware-facing concerns: GPIO/output, pixel chipset and colour order, LED count, network, power/current configuration, realtime state, and DDP reception.

**Python** owns spatial animation: the dome geometry, authoritative routes, generated XYZ positions, effects, and which RGB value belongs at every global LED index.

**DDP** is the transport. It carries the already-rendered RGB8 pixel bytes from Python to WLED over UDP/4048.

When this command is used:

```bash
thunderdome effect Fire --output ddp --controllers config/controllers.json --brightness 255
```

Python renders `Fire`. WLED is not running its native Fire effect; it receives pixel values. The explicit `--output ddp` is a physical-output boundary.

## Brightness layers

```text
Python effect brightness (0..255)
              |
              v
       DDP RGB8 frame
              |
              v
WLED master brightness (0..255)
              |
              v
             LEDs
```

Normal operating brightness is **255**. There are 256 valid 8-bit values, `0..255`; `256` is invalid. Live application DDP prepares each enabled WLED controller's master brightness at `255` before opening the DDP session. That HTTP call may affect WLED power/on state. It does not change current-limit settings, so physical readiness remains an operator responsibility.

## Direct fan-out

The current controller configuration maps each 1,000-pixel slice to one host:

| Controller | Host | `string_id` | Global slice | Local slice |
| ---: | --- | ---: | --- | --- |
| 1 | `192.168.12.10` | 0 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | 4000..4999 | 0..999 |

Controller 1 is not a master for the Python/DDP path. The public Lighting export records an older WLED configuration in which controller 1 has 5,000 LEDs and remote virtual outputs. Treat that as WLED-installation background only; current code/config direct fan-out wins for Python operation.

## One-shot versus held output

`ddp clear`, `solid`, `pixel`, and `range` send one frame and exit unless a loop mode is selected. `--hold`, `--duration`, and `--loops` are mutually exclusive; `--fps` is 1–60 and defaults to 20 for static loops. WLED may restore its prior state/effect after its realtime timeout when a one-shot frame ends.

Use [first light and DDP](../runbooks/03-first-light-and-ddp.md) for physical tests. Use [effects](../technical/effects.md) for renderer-specific options.

## Dry-run and output modes

- `--output simulator`: local WebSocket preview; no WLED traffic.
- `--output null`: render and discard; no network output.
- `--dry-run`: compatibility alias for null for effects; `ddp-all --dry-run` performs a one-shot packet/allocation simulation.
- `--output ddp`: physical DDP.
- `--output both`: identical rendered frame to simulator and physical DDP.

The simulator never silently falls back to DDP. A physical effect must state `--output ddp` or `--output both` explicitly.
