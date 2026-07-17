# DDP

Python chooses RGB values for each physical LED and sends linear RGB frames to WLED over UDP DDP on default port **4048**. WLED does not know XYZ coordinates. DDP packets use RGB8 payloads, byte offsets, and configurable chunks (default 480 LEDs).

## One-shot frames and realtime timeout

`thunderdome ddp clear`, `solid`, `pixel`, and `range` normally send one frame and exit. A one-shot frame is useful for a brief diagnostic, but WLED can exit realtime mode after its realtime timeout and restore the previous WLED state or effect. Use the application frame loop when a frame must stay visible.

Single-controller commands default to **1,000 LEDs**. `ddp-all` builds one logical **5,000-pixel** frame, splits it into five local 1,000-pixel frames, and sends each frame directly to its enabled controller.

## WLED live mode

The controller can explicitly update WLED's JSON state `live` flag:

```bash
thunderdome controller live --host 192.168.12.10 on
thunderdome controller live --host 192.168.12.10 off

thunderdome controllers live --controllers config/controllers.json on
thunderdome controllers live --controllers config/controllers.json off
```

The multi-controller form attempts every enabled controller and returns a non-zero status if any HTTP update fails.

## Held and repeated frames

All static `ddp` and `ddp-all` commands support these mutually exclusive controls:

| Option | Behaviour |
| --- | --- |
| `--hold` | Resend until Ctrl+C. |
| `--duration SECONDS` | Resend for a positive duration. |
| `--loops COUNT` | Resend exactly a positive number of frames. |
| `--fps FPS` | Frame rate from 1 to 60; 20 FPS is the loop default. |

The Python controller uses a monotonic scheduler and reuses its UDP socket for a single controller, or one socket per controller for `ddp-all`. Ctrl+C stops a normal held stream cleanly, closes those sockets, and reports frame and elapsed-time statistics.

```bash
# Hold one red pixel on a 1,000-pixel controller until Ctrl+C.
thunderdome ddp pixel \
  --host 192.168.12.10 \
  --led-count 1000 \
  20 --color FF0000 --brightness 255 \
  --hold --fps 20

# Hold distinct colours across the logical five-controller frame until Ctrl+C.
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 16 \
  --hold --fps 20
```

`ddp-all --dry-run` simulates one frame allocation and packet report without opening UDP sockets or sending traffic. To preserve that safety guarantee, it rejects `--hold`, `--duration`, and `--loops`.

## Exit status

A successful one-shot send or stream returns exit status `0`. `ddp-all` returns a non-zero status if any enabled controller reports a send failure. For a stream, the controller records failures for the entire session: an earlier failed frame still makes the final status non-zero even if that controller succeeds on a later frame. Successful controllers continue to receive frames where practical, and failure output identifies the controller number, host, and error.

Start at low brightness and validate controller mapping before a live stream.