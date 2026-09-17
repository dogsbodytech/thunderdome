# Software and simulator

## Purpose

Take a blank Linux checkout to a moving browser visualization without touching the physical dome. This is the safe/default operating path.

## Boundary

The commands in this document use local files and `127.0.0.1`. The simulator does not contact WLED and does not send DDP. Do not add `--output ddp` or `--output both` to this runbook.

## Step 1 — create and activate the virtual environment

**Why**

The package requires Python 3.11+ and should not share dependencies with system Python.

**Run**

```bash
cd /workspace/3d-controller
python3 --version
python3 -m venv .venv
source .venv/bin/activate
```

**Expected**

The version is Python 3.11 or later and the shell prompt is using `.venv`.

**If it fails**

Install Python 3.11+ and the venv package for the distribution. See [rebuild controller host](../commissioning/rebuild-controller-host.md).

## Step 2 — install the editable package

**Why**

Editable installation makes the local `thunderdome` command use this checkout and installs the simulator's `aiohttp` dependency.

**Run**

```bash
python -m pip install -e .
thunderdome --help
```

**Expected**

Help is printed and includes `simulator`, `effect`, `controllers`, and `ddp-all`.

**If it fails**

Use [command-not-found](../troubleshooting.md) or [venv troubleshooting](../troubleshooting.md).

## Step 3 — validate structure and routes

**Why**

The simulator must use matching geometry, route, and position data.

**Run**

```bash
thunderdome geometry validate
thunderdome route validate
thunderdome route summary
```

**Expected**

Geometry: `61 hubs, 165 spars, connected graph`. Routes: `5 routes, 120 unique spars, 0 shared spars`. Summary shows five 1,000-LED ranges.

**If it fails**

Stop at the failed authority. See [source of truth](../reference/source-of-truth.md) and [troubleshooting](../troubleshooting.md).

## Step 4 — generate and validate positions

**Why**

Positions are deterministic derived data, not a second geometry authority.

**Run**

```bash
thunderdome positions generate
thunderdome positions validate
thunderdome positions summary
```

**Expected**

Validation reports `Validated 5,000 nominal LED positions`. The summary reports five strings, each with 937 dome LEDs and 63 tail LEDs in the current data.

**If it fails**

Regenerate from the tracked geometry/routes and follow [position troubleshooting](../troubleshooting.md).

## Step 5 — start the local viewer

**Why**

The viewer is the browser endpoint for both static geometry and live effect frames.

**Run**

In terminal 1:

```bash
thunderdome simulator serve \
  --host 127.0.0.1 \
  --port 8080 \
  --no-open-browser
```

**Expected**

The terminal prints `Simulator mode: live viewer`, a local URL `http://127.0.0.1:8080/`, and WebSocket paths for `/ws/producer` and `/ws/viewer`. It also states that no HTTP requests will be sent to WLED controllers and no UDP/DDP packets will be sent by the simulator server.

**If it fails**

See [simulator will not start](../troubleshooting.md). A missing positions file means Step 4 was not completed.

## Step 6 — open and inspect the dome

**Why**

This separates static data loading from live frame streaming.

**Run**

Open:

```text
http://127.0.0.1:8080/
```

Enable hub labels if you need identifiers. Confirm the dome, H061 apex, tails, and five diagnostic string colours are visible.

**Expected**

The browser renders the tracked XYZ geometry and 5,000 LED points. Nothing needs to be powered.

**If it fails**

If the page cannot open, use [browser troubleshooting](../troubleshooting.md). If the geometry is visibly wrong, use [geometry looks wrong](../troubleshooting.md).

## Step 7 — stream a known-good live effect

**Why**

A moving browser view proves the renderer and local WebSocket frame path, not physical output.

**Run**

In terminal 2, with the virtual environment activated:

```bash
thunderdome effect height-wave \
  --output simulator \
  --direction bounce \
  --duration 10 \
  --brightness 255 \
  --fps 20
```

**Expected**

The browser's LED colours move for approximately 10 seconds. The CLI reports `Output mode: simulator`, says no HTTP or DDP traffic will be sent to WLED, and finishes with frame statistics.

**If it fails**

Use [simulator loads but no live movement](../troubleshooting.md). The simulator never falls back to physical DDP.

## Step 8 — stop safely

**Why**

Finite commands stop by themselves; held commands stop with `Ctrl+C`.

**Run**

```text
Press Ctrl+C in the effect terminal if it is still running.
Press Ctrl+C in the simulator terminal.
```

**Expected**

The effect reports an interruption or completion and the server exits. No WLED request or DDP packet was needed.

**If it fails**

See [shutdown](shutdown.md).

> ✅ **SOFTWARE CONTROLLER PROVEN**
>
> Python, installation, geometry, routes, positions, effects, simulator service, browser rendering, and live local frame streaming work. Physical power, WLED, physical networking, DDP-to-hardware, and string identity remain unproven.

Next: [physical dome startup](physical-dome-startup.md).
