# Cold start: remember nothing

## Purpose

Use this as the main recovery path when returning to Thunderdome after a long gap. It proves the software first, then hands off to a separate physical procedure.

## Safety boundary

Steps 1–8 are offline/local software work. They do not require WLED, physical power, or DDP. Do not continue to physical output until the software checkpoint passes.

## Step 1 — enter the controller directory

**Why**

All commands below are for this checkout, not the wider repository root.

**Run**

```bash
cd /workspace/3d-controller
```

**Expected**

`pwd` would show `/workspace/3d-controller`.

**If it fails**

Use the [rebuild controller host](../commissioning/rebuild-controller-host.md) path to retrieve the repository.

## Step 2 — prove the Python prerequisite

**Why**

The package requires Python 3.11 or later.

**Run**

```bash
python3 --version
```

**Expected**

Python `3.11` or later.

**If it fails**

Install the distribution's Python 3.11+ and `python3-venv`, or use [rebuild controller host](../commissioning/rebuild-controller-host.md). Do not continue with an older interpreter.

## Step 3 — install the isolated package

**Why**

The CLI and its `aiohttp` simulator dependency must be installed into this checkout's virtual environment.

**Run**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
thunderdome --help
```

**Expected**

The help lists `geometry`, `route`, `positions`, `simulator`, `controllers`, `effect`, `control`, and `ddp-all`.

**If it fails**

Check the Python version and [troubleshooting](../troubleshooting.md). Do not work around a failed package install by running source files directly.

## Step 4 — validate the tracked geometry

**Why**

Geometry is the structural input for positions and effects.

**Run**

```bash
thunderdome geometry validate
```

**Expected**

The command reports `61 hubs, 165 spars, connected graph`.

**If it fails**

Stop and use [troubleshooting](../troubleshooting.md).

## Step 5 — validate the authoritative routes

**Why**

Routes define the physical LED traversal and global allocation.

**Run**

```bash
thunderdome route validate
thunderdome route summary
```

**Expected**

Validation reports `5 routes, 120 unique spars, 0 shared spars`. Summary lists controllers 1–5, strings 0–4, starts H032/H033/H034/H035/H031, and global ranges `0..999` through `4000..4999`.

**If it fails**

Stop. Do not repair routes by symmetry or by editing Markdown; see [source of truth](../reference/source-of-truth.md) and [route troubleshooting](../troubleshooting.md).

## Step 6 — generate and validate derived LED positions

**Why**

Effects and the simulator consume the generated 5,000-record XYZ file. It is ignored derived data, so a fresh checkout may not have it.

**Run**

```bash
thunderdome positions generate
thunderdome positions validate
```

**Expected**

Generation reports the output path. Validation reports `Validated 5,000 nominal LED positions`.

**If it fails**

Use [troubleshooting](../troubleshooting.md) or [position validation](../troubleshooting.md). Do not edit the generated JSON by hand.

## Step 7 — prove a moving local simulator

**Why**

This verifies the server, browser stream, effect renderer, and live frame delivery without hardware.

**Run**

In terminal 1:

```bash
thunderdome simulator serve --host 127.0.0.1 --port 8080 --no-open-browser
```

Open `http://127.0.0.1:8080/` in a browser. In terminal 2, from the same activated environment:

```bash
thunderdome effect fire \
  --output simulator \
  --duration 10 \
  --brightness 255 \
  --fps 20
```

**Expected**

The browser shows the dome and its LED points change colour while the effect runs. The effect exits after about 10 seconds. The simulator terminal reports a local server URL and says it will send no HTTP requests to WLED and no UDP/DDP packets.

**If it fails**

Check [simulator troubleshooting](../troubleshooting.md) and [live-movement troubleshooting](../troubleshooting.md).

## Step 8 — stop the local software

**Why**

A clean stop closes the local producer and server.

**Run**

Press `Ctrl+C` in terminal 1 after the finite effect has completed. If an effect is held, press `Ctrl+C` in its terminal first.

**Expected**

The effect reports completion or interruption; the simulator server stops.

**If it fails**

Use [shutdown](shutdown.md). No physical power action is part of this software-only phase.

> ✅ **SOFTWARE CONTROLLER PROVEN**
>
> Do not proceed if this checkpoint did not pass. It proves the Python/software path only; it says nothing about physical power, WLED configuration, network reachability, DDP delivery to hardware, or string identity.

## Step 9 — hand off to physical operation

Use [physical dome startup](physical-dome-startup.md), then [first light and DDP](first-light-and-ddp.md). Every physical effect command in those runbooks states `--output ddp` or `--output both` explicitly.
