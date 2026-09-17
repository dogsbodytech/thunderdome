# 02 — Physical dome startup
**Position:** Step 02 of 05
**Previous:** [01 — Software and simulator](01-software-and-simulator.md)
**Use this when:** The software milestone has passed and you are preparing the real dome.
**Prerequisite:** [01 — Software and simulator](01-software-and-simulator.md) ended at ✅ SOFTWARE CONTROLLER PROVEN.
**Ends when:** ✅ FIVE CONTROLLERS READY
**Next:** [03 — First light and DDP](03-first-light-and-ddp.md)


## Main sequence

`00 Cold Start` → `01 Software + Simulator` → `02 Physical Dome Startup` → `03 First Light + DDP` → `04 Normal Operation` → `05 Shutdown`

## Purpose

Use this only after [software and simulator](01-software-and-simulator.md) reaches **SOFTWARE CONTROLLER PROVEN**. It prepares the five real WLED destinations and hands first-light testing to [first light and DDP](03-first-light-and-ddp.md).

> ⚠️ **PHYSICAL HARDWARE FROM THIS POINT**
>
> The checks and commands below may contact WLED controllers and illuminate the dome. Confirm the physical power/current configuration before applying brightness `255`.

## Target and inputs

- Checkout: the cloned `3d-controller` directory
- Runtime config: `config/controllers.json` (local and Git-ignored)
- WLED addresses: [controller network reference](../reference/controller-network.md)
- DDP: UDP/`4048`
- Human controller numbers: 1–5
- Internal `string_id`: 0–4
- Normal Python/WLED brightness policy: `255` (valid range is `0..255`; `256` is invalid)

## Step 1 — create the local controller configuration

**Why**

The physical CLI must know all five direct destinations and their fixed frame ranges.

**Run**

```bash
source .venv/bin/activate
cp config/controllers.example.json config/controllers.json
```

Edit only the five `host` values in `config/controllers.json` to the deployed addresses:

```text
192.168.12.10
192.168.12.20
192.168.12.30
192.168.12.40
192.168.12.50
```

**Expected**

The file contains five enabled controllers, five 1,000-LED local ranges, and no `REPLACE_WITH_...` host values.

**If it fails**

Do not run physical output with placeholders. See [controllers.json](../setup-and-recovery/wled-controller.md#controllersjson) and [invalid controller config](../troubleshooting.md).

## Step 2 — validate allocation without contacting WLED

**Why**

This catches numbering and range mistakes before network checks.

**Run**

```bash
thunderdome controllers validate --controllers config/controllers.json
thunderdome controllers summary --controllers config/controllers.json
```

**Expected**

Validation reports `Validated five direct-DDP controllers`. Summary matches the five-row table in [controller network reference](../reference/controller-network.md).

**If it fails**

Stop. Fix the local JSON from the example template; do not alter geometry/routes to fit a controller mistake.

## Step 3 — verify the recorded network path

**Why**

DDP requires the controller host to be reachable from this computer on the installation network.

**Run**

Use the addresses from the table, one at a time:

```bash
ping -c 1 192.168.12.10
ping -c 1 192.168.12.20
ping -c 1 192.168.12.30
ping -c 1 192.168.12.40
ping -c 1 192.168.12.50
```

**Expected**

Each address responds, or the site's network policy provides another confirmed reachability check.

**If it fails**

Stop and use [one WLED controller unreachable](../troubleshooting.md). Do not substitute a different address based on guesswork. Gateway, subnet, router, DHCP range, Wi-Fi SSID, and controller-host address are recorded in [controller network reference](../reference/controller-network.md) only where evidence exists.

## Step 4 — read WLED state before lighting

**Why**

This confirms that the address is a WLED HTTP endpoint and lets you inspect its current power and realtime state.

**Run**

```bash
thunderdome controller info --host 192.168.12.10
thunderdome controller state --host 192.168.12.10
```

Repeat for controllers 2–5 if needed. These are real HTTP reads.

**Expected**

The response identifies a WLED device and returns JSON state. Do not require a particular current state after a rebuild; compare relevant settings with [WLED Controller recovery](../setup-and-recovery/wled-controller.md).

**If it fails**

Use [one WLED controller unreachable](../troubleshooting.md) or [WLED reachable but DDP ignored](../troubleshooting.md).

## Step 5 — confirm physical readiness

**Why**

Brightness `255` is the normal operating value, but software cannot prove wiring, injection, fuse, PSU, or current-limit safety.

**Run**

Review [physical installation](../reference/physical-installation.md) and [WLED Controller recovery](../setup-and-recovery/wled-controller.md). Confirm the recorded power/current configuration on each WLED device before continuing.

**Expected**

The operator can identify the PSU, string, data start, LED count, WLED output settings, and current/power configuration for each device. If a controller was reset, use [WLED Controller recovery](../setup-and-recovery/wled-controller.md) first.

**If it fails**

Stop. Physical power switching and any unrecorded electrical procedure are **NOT CURRENTLY CAPTURED** in this component; do not invent a power-down or fuse procedure.

## Step 6 — hand off to first light

Use [first light and DDP](03-first-light-and-ddp.md). Its first physical command is deliberately one controller and finite-duration. Every spatial physical effect there explicitly uses `--output ddp`.


> ✅ **FIVE CONTROLLERS READY**
>
> The local configuration is valid, the five recorded WLED addresses are reachable, and the recorded power/current settings have been checked.

**Next:** [03 — First light and DDP](03-first-light-and-ddp.md)
