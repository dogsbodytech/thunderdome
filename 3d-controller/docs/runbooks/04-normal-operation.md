# 04 — Normal operation
**Position:** Step 04 of 05
**Previous:** [03 — First light and DDP](03-first-light-and-ddp.md)
**Use this when:** The simulator and physical mapping are already known-good for routine event use.
**Prerequisite:** The required setup gates have passed; use 00–03 first if state is unknown.
**Ends when:** A normal session is running or has been stopped cleanly.
**Next:** [05 — Shutdown](05-shutdown.md)


## Main sequence

`00 Cold Start` → `01 Software + Simulator` → `02 Physical Dome Startup` → `03 First Light + DDP` → `04 Normal Operation` → `05 Shutdown`

## Purpose

Use this short routine once the simulator and physical setup have already passed. Do not repeat first-light checks at every event unless something changed.

> ⚠️ **PHYSICAL OUTPUT IS EXPLICIT**
>
> `--output simulator` is local preview. `--output ddp` sends to the dome. `--output both` sends to both. Choose deliberately.

## Step 1 — enter the checkout

**Why**

The installed command depends on this project's environment and generated positions.

**Run**

```bash
cd 3d-controller
source .venv/bin/activate
test -f geometry/generated/led_positions_3d.json
```

**Expected**

The test exits successfully.

**If it fails**

Run `thunderdome positions generate` and `thunderdome positions validate` before continuing.

## Step 2 — start the local operator service or simulator

**Why**

The browser is useful for preview and control even when physical output is selected separately.

**Run**

Simulator-only, safest:

```bash
thunderdome simulator serve --host 127.0.0.1 --port 8080 --open-browser
```

For the local control API with deliberate physical capability enabled:

```bash
thunderdome control serve \
  --host 127.0.0.1 \
  --port 8080 \
  --controllers config/controllers.json \
  --allow-live-control \
  --open-browser
```

**Expected**

A local URL is printed. The control service remains simulator-only unless a request selects `ddp` or `both`; addresses stay server-owned.

**If it fails**

Use [simulator troubleshooting](../troubleshooting.md) or [control UI unavailable](../troubleshooting.md).

## Step 3 — run the chosen display

**Why**

Every output destination should be visible in the command line.

**Run**

Local preview:

```bash
thunderdome effect auto \
  --output simulator \
  --preset calm \
  --brightness 255
```

Physical dome:

```bash
thunderdome effect auto \
  --output ddp \
  --controllers config/controllers.json \
  --preset calm \
  --brightness 255
```

Mirror preview and physical output:

```bash
thunderdome effect auto \
  --output both \
  --controllers config/controllers.json \
  --preset calm \
  --brightness 255
```

**Expected**

`simulator` prints that no WLED traffic will be sent. `ddp` or `both` prints a physical-output warning and runs until `Ctrl+C` unless a finite option is added.

**If it fails**

For local output use [live movement](../troubleshooting.md). For physical output use [physical troubleshooting](../troubleshooting.md).

## Step 4 — operate the browser control service when used

**Why**

The control service provides the local runtime API and browser surface; it does not itself add MQTT.

**Run**

Open the URL printed by `control serve`. Check the capabilities/status endpoints if diagnosing the service:

```bash
curl -s http://127.0.0.1:8080/api/control/capabilities
curl -s http://127.0.0.1:8080/api/runtime/status
```

**Expected**

The service reports `default_output` as `simulator`. Live output is available only when it was started with both `--controllers` and `--allow-live-control`.

**If it fails**

Use [REST/control troubleshooting](../troubleshooting.md) and [REST API reference](../technical/api-rest.md).

## Step 5 — normal stop

**Why**

The application owns its frame loop and closes its sinks on interruption.

**Run**

Press `Ctrl+C` in the effect or service terminal. Then follow [shutdown](05-shutdown.md).

**Expected**

Held effects stop cleanly and report frames/elapsed time; the service returns to its stopped state.

**If it fails**

Use [shutdown](05-shutdown.md). Physical electrical power-off is outside this component unless the wider installation procedure is available.
