# Simulator technical reference

`thunderdome simulator serve` is a local browser viewer for the tracked dome and generated LED positions. With no producer, it shows static geometry; an effect using `--output simulator` can stream live frames into the same viewer. The simulator makes no WLED HTTP requests and sends no UDP/DDP packets.

## Start

```bash
thunderdome simulator serve \
  --host 127.0.0.1 \
  --port 8080 \
  --no-open-browser
```

Open `http://127.0.0.1:8080/`. The server defaults to project-root-safe geometry, routes, and generated positions. Explicit relative paths remain relative to the current working directory:

```bash
thunderdome simulator serve \
  --geometry geometry/thunderdome_geometry.json \
  --routes geometry/routes/string_routes.json \
  --positions geometry/generated/led_positions_3d.json \
  --open-browser
```

The three files must describe the same dome. If positions are missing:

```bash
thunderdome positions generate
thunderdome positions validate
```

The default bind is `127.0.0.1`. Binding to `0.0.0.0` exposes this unauthenticated development server to reachable machines and is not appropriate for a live-enabled service on an untrusted network.

## What the viewer shows

- 61 hubs, 165 spars, H061 apex, tails, and 5,000 LED points;
- true XYZ scale and five diagnostic string/controller colours;
- hub labels, including H061;
- LED/hub lookup, camera presets, orbit/pan/zoom, and projection switch;
- live frame connection state, sequence, FPS, and skipped-frame counters.

Diagnostic colours are layout aids only. Global ranges are controller 1 `0..999`, controller 2 `1000..1999`, controller 3 `2000..2999`, controller 4 `3000..3999`, and controller 5 `4000..4999`.

## JSON and WebSocket endpoints

| Endpoint | Purpose |
| --- | --- |
| `/api/simulator/metadata` | Versions, source paths, counts, bounds, and controller ranges |
| `/api/simulator/status` | Non-sensitive producer/viewer and frame counters |
| `/api/simulator/geometry` | Hubs, spars, apex, and bounds |
| `/api/simulator/leds` | All 5,000 LED records in global order |
| `/ws/producer` | One local effect-frame producer |
| `/ws/viewer` | Browser viewers |

The live binary frame protocol uses a versioned `TDFR` header and exactly 15,000 RGB8 payload bytes for 5,000 LEDs. A producer's sequence must increase; stale viewer frames are discarded so preview latency stays bounded.

## Live simulator check

With the server running in one terminal:

```bash
thunderdome effect Fire \
  --output simulator \
  --duration 10 \
  --brightness 255 \
  --fps 20
```

The CLI must print `Output mode: simulator` and state that no HTTP or DDP traffic will be sent to WLED. The browser should show changing LED colours. Connection failure is an error; the simulator never falls back to DDP.

## Offline assets and limits

Three.js r160 / 0.160.0, OrbitControls, and the licence notice are bundled under `simulator/static/vendor/`. Runtime requires no npm or CDN.

The simulator is a preview, not a recorder or guaranteed-delivery system. It has no browser authentication, MQTT listener, recording/replay, timeline editor, or physical calibration. Static geometry and live frames are local features; physical power and WLED state are outside this server.
