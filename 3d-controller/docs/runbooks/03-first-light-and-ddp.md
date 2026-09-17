# 03 — First light and DDP
**Position:** Step 03 of 05
**Previous:** [02 — Physical dome startup](02-physical-dome-startup.md)
**Use this when:** Five WLED devices are prepared and you need to prove physical output and mapping.
**Prerequisite:** [02 — Physical dome startup](02-physical-dome-startup.md) ended at ✅ FIVE CONTROLLERS READY; power/current settings are checked.
**Ends when:** ✅ PHYSICAL MAPPING PROVEN
**Next:** [04 — Normal operation](04-normal-operation.md)


## Main sequence

`00 Cold Start` → `01 Software + Simulator` → `02 Physical Dome Startup` → `03 First Light + DDP` → `04 Normal Operation` → `05 Shutdown`

## Purpose

Commission the physical path in layers: local configuration, five reachable WLED devices, one controller, all string identities, then one whole-dome Python effect.

> ⚠️ **REAL OUTPUT**
>
> This document sends HTTP requests and DDP frames to the physical installation. Do not use it until [physical dome startup](02-physical-dome-startup.md) has passed and power/current settings have been checked.

## DDP model

Python renders the logical 5,000-pixel frame and sends five direct 1,000-pixel slices:

| Human controller | WLED host | Internal string | Logical slice |
| ---: | --- | ---: | --- |
| 1 | `192.168.12.10` | `string_id 0` | 0..999 |
| 2 | `192.168.12.20` | `string_id 1` | 1000..1999 |
| 3 | `192.168.12.30` | `string_id 2` | 2000..2999 |
| 4 | `192.168.12.40` | `string_id 3` | 3000..3999 |
| 5 | `192.168.12.50` | `string_id 4` | 4000..4999 |

## Step 1 — recheck the local file

**Why**

First light must use the same fixed mapping that was validated during physical startup.

**Run**

```bash
cd 3d-controller
source .venv/bin/activate
thunderdome controllers validate --controllers config/controllers.json
```

**Expected**

`Validated five direct-DDP controllers`.

**If it fails**

Stop. Do not send any frame. Repair `config/controllers.json` and repeat physical startup.

## Step 2 — check all five WLED HTTP endpoints

**Why**

A reachable host is a prerequisite for controller management and live-output preparation.

**Run**

```bash
thunderdome controllers state --controllers config/controllers.json
```

**Expected**

One result per configured controller. Each successful result ends with `state ok` and includes JSON state; failures identify the controller and host.

**If it fails**

Stop for the failed device. Use [one WLED controller unreachable](../troubleshooting.md). Do not ignore a missing controller and call it a complete-dome test.

## Step 3 — identify one controller with a finite solid frame

**Why**

A single local frame distinguishes WLED output from the Python spatial renderer and limits the test to one 1,000-LED destination.

**Run**

Test controller 1 first:

```bash
thunderdome ddp solid \
  --host 192.168.12.10 \
  --led-count 1000 \
  --color FF0000 \
  --brightness 255 \
  --duration 2 \
  --fps 10
```

**Expected**

The string driven by controller 1 is red for about two seconds. The CLI reports a DDP start and completion statistics. This direct `ddp` command is physical output; it has no simulator mode.

**If it fails**

Use [physical dome dark](../troubleshooting.md), [wrong colours](../troubleshooting.md), or [one LED string dark](../troubleshooting.md).

## Step 4 — identify all five strings

**Why**

The controller table must match physical string identity, not merely five responding IP addresses.

**Run**

```bash
thunderdome ddp-all controller-colors \
  --controllers config/controllers.json \
  --brightness 255 \
  --duration 5 \
  --fps 10
```

**Expected**

For approximately five seconds the five logical slices show distinct colours: controller 1 red, 2 green, 3 blue, 4 yellow, and 5 magenta. Each physical string must match its table row.

**If it fails**

Record which physical string showed each colour. Compare the observation with [controller network reference](../reference/controller-network.md). A responding device with the wrong string is a mapping/wiring problem; do not swap `string_id` or route data to hide it.

## Step 5 — run one known-good whole-dome spatial effect

**Why**

This proves Python positions, effect rendering, five-way slicing, and physical DDP together.

**Run**

```bash
thunderdome effect height-wave \
  --output ddp \
  --controllers config/controllers.json \
  --direction bounce \
  --duration 20 \
  --brightness 255 \
  --fps 20
```

**Expected**

The height band moves across the dome for approximately 20 seconds. The CLI prints `Output mode: live DDP` and warns that frames are sent to physical controllers. Before the DDP session opens, the controller prepares enabled WLED master brightness at `255`; it does not change WLED current-limit settings.

**If it fails**

Use [WLED reachable but DDP ignored](../troubleshooting.md), [geometry looks wrong](../troubleshooting.md), or [effect stops](../troubleshooting.md).

## Step 6 — stop and confirm the result

**Why**

A finite test must leave the operator with a known stopping point and a mapping decision.

**Run**

No command is needed if Step 5 completed. For a held physical effect, press `Ctrl+C` in its terminal.

**Expected**

The effect reports completion/interruption and frame statistics. The five controller/string rows have been visually confirmed or the unresolved row is recorded as a fault.

**If it fails**

Use [shutdown](05-shutdown.md). Do not improvise a physical power-off procedure; see [scope gaps](../reference/source-of-truth.md#facts-not-currently-captured).

Next: [normal operation](04-normal-operation.md).


> ✅ **PHYSICAL MAPPING PROVEN**
>
> Each responding WLED device matches the expected controller/string row and the whole-dome physical effect has completed or been stopped cleanly.

**Next:** [04 — Normal operation](04-normal-operation.md)
