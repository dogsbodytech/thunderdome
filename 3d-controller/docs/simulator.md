# Thunderdome simulator

Stage A is a local, fully offline static geometry and LED-layout viewer. It does **not** stream live effect frames, does not change the default DDP output path, and does not contact WLED controllers.

## Scope

Included in Stage A:

- local HTTP server: `thunderdome simulator serve`;
- browser viewer served from local repository files;
- all 61 hubs, 165 spars, and all 5,000 generated LED XYZ records;
- H061 apex marker and distinct H061 hub-ID label styling;
- tail visibility and highlighting;
- five diagnostic string/controller colours;
- LED and hub inspection;
- camera presets, orbit/pan/zoom, reset, perspective/orthographic switch;
- optional canvas-texture labels that display every real hub ID;
- metadata, geometry, and LED JSON APIs.

Not included in Stage A:

- live effect frame streaming;
- WebSocket input;
- simulator frame sink/output selection;
- recording or replay;
- changes to DDP defaults;
- MQTT or asynchronous effect overrides.

Existing effects still use their current output behavior. `simulator serve` sends no DDP packets and makes no WLED HTTP requests.

## Offline assets

The viewer uses plain HTML, CSS, and JavaScript ES modules. No npm install or build step is required at runtime.

Bundled vendor files:

- Three.js module: `simulator/static/vendor/three.module.js`
- OrbitControls: `simulator/static/vendor/OrbitControls.js`
- Licence notice: `simulator/static/vendor/LICENSE.threejs`

Recorded Three.js version: **0.160.0 / r160**.

The frontend must not load `unpkg`, `jsdelivr`, `cdnjs`, Google Fonts, remote source maps, textures, APIs, or analytics. Licence text may contain upstream project names, but runtime frontend files should reference only local paths.

## Start command

From `3d-controller/`:

```bash
thunderdome simulator serve
```

Defaults:

- `--host 127.0.0.1`
- `--port 8080`
- project-root-safe `geometry/thunderdome_geometry.json`
- project-root-safe `geometry/reference_string_route.md`
- project-root-safe `geometry/generated/led_positions_3d.json`
- browser is not opened automatically

The command prints:

```text
Simulator mode: static viewer
No HTTP requests will be sent to WLED controllers.
No UDP/DDP packets will be sent.

Geometry:
  /resolved/path/to/thunderdome_geometry.json

Routes:
  /resolved/path/to/reference_string_route.md

Positions:
  /resolved/path/to/led_positions_3d.json

Simulator available at:
http://127.0.0.1:8080/
```

Options:

```bash
thunderdome simulator serve \
  --host 127.0.0.1 \
  --port 18080 \
  --geometry geometry/thunderdome_geometry.json \
  --routes geometry/reference_string_route.md \
  --positions geometry/generated/led_positions_3d.json \
  --open-browser
```

`--routes FILE` defines string traversal and spar association. Geometry, routes, and positions must describe the same dome. The built-in route document is `geometry/reference_string_route.md`; an explicit generated route document such as `geometry/routes/string_routes.json` is also supported. Use `--no-open-browser` to force no browser launch. `--open-browser` uses Python's standard `webbrowser` module; failure to open a browser does not invalidate the server.

## Binding and security

With the default `127.0.0.1`, the simulator is local to the machine. Binding to `0.0.0.0` exposes the development server to other reachable machines on the network. Stage A does not implement authentication.

The server serves only intended simulator static files and fixed JSON endpoints. It rejects directory traversal and unknown API paths; it does not expose arbitrary repository files or execute user code.

## API endpoints

### `/`

Serves `simulator/static/index.html`.

### `/api/simulator/metadata`

Returns:

- simulator schema version;
- simulator mode;
- Three.js version;
- geometry, routes, and positions source filenames/paths;
- route count and string count;
- total LED count;
- tail count;
- controller/string count;
- hub and spar count;
- H061 apex coordinates;
- XYZ bounds;
- five string/controller global-index ranges.

### `/api/simulator/geometry`

Returns normalized structure data:

- hubs with IDs, XYZ, and H061 apex flag;
- spars with IDs, type, endpoint hub IDs, endpoint coordinates, and length;
- apex identity;
- dome bounds.

### `/api/simulator/leds`

Returns all 5,000 generated LED records in global-index order. Each record includes:

- global index;
- controller number;
- string ID;
- local/string index;
- XYZ coordinates;
- tail status;
- spar route metadata where applicable;
- tail metadata where applicable.

Controller IP addresses are not exposed because Stage A does not require live controller access.

## Geometry and validation

The simulator loads a compatible geometry/routes/positions set through Python. Built-in defaults are:

- `geometry/thunderdome_geometry.json`
- `geometry/reference_string_route.md`
- `geometry/generated/led_positions_3d.json`

Before serving, it validates:

- exactly 5,000 LEDs;
- global indexes are exactly `0..4999`;
- indexes are unique;
- coordinates are finite;
- H061 exists;
- five 1,000-LED controller/string ranges exist;
- local indexes remain `0..999` within each controller;
- tail metadata is present for generated tail records;
- spar endpoints reference known hubs.
- every route hub and declared spar exists in the selected geometry;
- every declared spar connects its selected route endpoints;
- generated spar LED metadata belongs to the selected route.

If generated positions are missing or invalid, regenerate them with:

```bash
thunderdome positions generate
thunderdome positions validate
```

Default paths are anchored to the installed project root. Explicit relative `--geometry`, `--routes`, and `--positions` paths remain relative to the user's current working directory. Invalid or incompatible files report their resolved paths and prevent server startup; the simulator never silently substitutes the built-in routes file for an explicit selection.

## Viewer controls

The viewer renders the true XYZ coordinates with equal scale on X, Y, and Z. It does not reshape the dome into a generic sphere.

Controls include:

- show/hide LEDs;
- show/hide spars;
- show/hide hubs;
- show/hide tails;
- highlight only tails;
- show/hide ground plane;
- show/hide XYZ axes;
- show/hide hub labels;
- highlight a selected controller/string;
- reset and fit view;
- top/front/side/opposite/perspective presets;
- perspective/orthographic camera switch.

## String colours

Diagnostic colours distinguish physical strings/controllers only; they have no production effect meaning.

- global `0..999`: controller 1
- global `1000..1999`: controller 2
- global `2000..2999`: controller 3
- global `3000..3999`: controller 4
- global `4000..4999`: controller 5

Hiding tails does not reindex LEDs. Global index identity remains unchanged.

## Inspection

LED lookup accepts global indexes `0..4999`. Selecting or locating an LED displays:

- global index;
- controller/string number;
- local index;
- XYZ coordinates;
- tail status;
- available route/spar or tail metadata.

Hub inspection displays hub ID and coordinates. Hub labels are hidden by default; enabling **Hub labels** creates no per-frame DOM nodes and displays reusable local canvas-texture sprites that always face the camera. Each sprite shows the real hub ID, and H061 is larger with a gold apex treatment. Label sprites are excluded from picking, so LED and hub selection remains on the underlying point objects.

## Manual browser validation

Run the local viewer from an activated environment:

```bash
cd /approved-repos/thunderdome/3d-controller
source .venv/bin/activate

thunderdome simulator serve \
  --host 127.0.0.1 \
  --port 8080 \
  --open-browser
```

Verify that hub labels show actual IDs, H061 is labelled at the apex, labels remain readable while orbiting and hide immediately, LEDs and hubs remain selectable, camera presets work, tails remain visible, and all five string colours are distinct.

## Stage B binary live frames

Install the Python dependency once with `python3 -m pip install -e .`; it installs the maintained `aiohttp` dependency used by one coherent local HTTP/WebSocket server. Runtime stays offline after installation and does not require Node.js or npm.

Start the local-only server:

```bash
thunderdome simulator serve --host 127.0.0.1 --port 8080 --open-browser
```

The server retains all Stage A HTTP endpoints and static assets. It accepts one producer at `/ws/producer` and any number of browser viewers at `/ws/viewer`; a second producer receives HTTP 409. Frames use network-byte-order `TDFR` protocol version 1: a 32-byte header (magic, version, flags, header length, unsigned 64-bit sequence, float64 timestamp, pixel count, payload length) followed by exactly 15,000 RGB8 bytes for 5,000 LEDs. Invalid frames are rejected. Sequence ordering is enforced only for the active producer connection: its frames must strictly increase, but after it disconnects a later producer may restart at sequence zero. Metadata exposes the protocol version, encoding, expected sizes, and endpoint paths; `/api/simulator/status` exposes non-sensitive connection and frame counters.

Viewers retain the latest complete frame and each has a queue of one: stale preview frames are discarded so latency stays low. The browser keeps the existing Stage A `THREE.Points` geometry, updates only its colour buffer, displays connection state, sequence, FPS, and skipped frames, and reconnects using bounded exponential backoff. Diagnostic string colours remain until the first live frame and can be restored with the button.

## Limitations

- The simulator is a local preview, not a guaranteed-delivery recorder or replay system.
- The producer does not queue frames while disconnected; initial connection failure or streaming loss terminates the active effect or auto run and returns nonzero. There is no fallback from simulator output to DDP.
- No browser authentication, MQTT, recording/replay, timeline controls, or effect-debug overlays are included.
- No browser automation test framework is introduced; source-level asset tests and local protocol integration tests cover the live path.
- Cylindrical spars and physically calibrated hub offsets are future enhancements.
