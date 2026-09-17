# Rebuild the controller host

## Purpose

Recover the Python controller computer only. This does not deploy the wider Thunderdome project, configure the router, rewire the dome, or perform a DNS cutover.

## Scope and prerequisites

You need a Linux machine, access to the public repository, and the local controller checkout. Physical operation still requires the separately documented WLED/network path.

## Step 1 — retrieve the repository

**Why**

The controller package depends on tracked geometry, routes, simulator assets, and configuration templates.

**Run**

```bash
git clone https://github.com/dogsbodytech/thunderdome.git
cd thunderdome/3d-controller
```

**Expected**

The shell is in the `3d-controller` directory.

**If it fails**

Confirm repository access and disk space, then retry the clone. Do not copy only top-level files into this directory.

## Step 2 — create and install the environment

**Why**

The package requires Python 3.11+ and `aiohttp`.

**Run**

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
thunderdome --help
```

**Expected**

Python is 3.11+, installation completes, and CLI help is available.

**If it fails**

Install the distribution's Python 3.11+ and venv package. See [troubleshooting](../troubleshooting.md).

## Step 3 — recreate runtime controller configuration

**Why**

`controllers.json` is intentionally ignored and must be recreated locally.

**Run**

```bash
cp config/controllers.example.json config/controllers.json
```

Edit its five `host` fields to the deployed addresses in [controller network](../reference/controller-network.md), then run:

```bash
thunderdome controllers validate --controllers config/controllers.json
```

**Expected**

`Validated five direct-DDP controllers`.

**If it fails**

Do not send hardware output. Fix the local file and repeat [WLED commissioning](wled-controller.md#controllersjson).

## Step 4 — regenerate derived positions

**Why**

Generated positions are ignored data and are not recovered by Git.

**Run**

```bash
thunderdome geometry validate
thunderdome route validate
thunderdome positions generate
thunderdome positions validate
```

**Expected**

Geometry and route validation pass, generation reports its output path, and positions validation reports `Validated 5,000 nominal LED positions`.

**If it fails**

Use [missing generated positions](../troubleshooting.md) or the route/geometry authority documents.

## Step 5 — prove the rebuilt host locally

**Why**

A rebuild is not complete until the software milestone passes without hardware.

**Run**

Follow [software and simulator](../runbooks/software-and-simulator.md) through the moving `--output simulator` effect and stop it cleanly.

**Expected**

The browser shows live movement and the **SOFTWARE CONTROLLER PROVEN** checkpoint is reached.

**If it fails**

Stop at the failed software gate. Use [troubleshooting](../troubleshooting.md); do not debug DDP yet.

## Step 6 — proceed only when hardware is required

Use [physical dome startup](../runbooks/physical-dome-startup.md), followed by [first light and DDP](../runbooks/first-light-and-ddp.md). The rebuild procedure itself sends no WLED/DDP traffic.
