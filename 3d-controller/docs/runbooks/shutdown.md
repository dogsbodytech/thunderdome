# Shutdown

## Purpose

Stop the controller software, frame loop, simulator, or control service without leaving a worker or socket running.

## Step 1 — stop the active effect

**Why**

Held and continuous effects own the rendering loop and output sink.

**Run**

Press `Ctrl+C` in the terminal running `thunderdome effect ...`.

**Expected**

The command reports `Interrupted: ... frames sent in ...s` or a finite command reports `Completed: ...`. DDP sockets and simulator connections close.

**If it fails**

Retry only the normal `Ctrl+C` stop once. If the process remains, identify it with the host's normal process tools; do not start another physical effect over it.

## Step 2 — stop the control service

**Why**

The control service owns the runtime worker and its selected sink set.

**Run**

Press `Ctrl+C` in the terminal running `thunderdome control serve ...`.

**Expected**

The service exits. Its worker is cancelled and sinks are closed.

**If it fails**

Use [control service troubleshooting](../troubleshooting.md). Do not bypass the service by starting a second live worker without first confirming the first process stopped.

## Step 3 — stop the simulator

**Why**

The local HTTP/WebSocket server is no longer needed after the effect/control service has stopped.

**Run**

Press `Ctrl+C` in the terminal running `thunderdome simulator serve ...`.

**Expected**

The terminal reports that the simulator stopped.

**If it fails**

Use [simulator troubleshooting](../troubleshooting.md) and the host's process inspection tools.

## What happens at WLED after DDP stops?

A one-shot or repeated DDP command does not provide a permanent WLED effect. WLED may leave realtime mode when its configured realtime timeout expires and restore its previous WLED state/effect. The exact visible result depends on each device's current WLED state.

The Python controller does not document an electrical power-off sequence here. Physical PSU isolation, mains safety, and event-site shutdown are **NOT CURRENTLY CAPTURED** in this component. Use the wider project's physical documentation and the site's competent-person procedure; do not infer a safe electrical action from a software stop.

Related: [physical installation](../reference/physical-installation.md) and [WLED commissioning](../commissioning/wled-controller.md).
