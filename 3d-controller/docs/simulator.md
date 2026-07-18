# Thunderdome simulator

Stage A is a local, fully offline static geometry and LED-layout viewer. It does **not** stream live effect frames, does not change the default DDP output path, and does not contact WLED controllers.

## Scope

Included in Stage A:

- local HTTP server: `thunderdome simulator serve`;
- browser viewer served from local repository files;
- all 61 hubs, 165 spars, and all 5,000 generated LED XYZ records;
- H061 apex marker;
- tail visibility and highlighting;
- five diagnostic string/controller colours;
- LED and hub inspection;
- camera presets, orbit/pan/zoom, reset, perspective/orthographic switch;
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
- project-root-safe `geometry/generated/led_positions_3d.json`
- browser is not opened automatically

The command prints:

```text
Simulator mode: static viewer
No HTTP requests will be sent to WLED controllers.
No UDP/DDP packets will be sent.

Simulator available at:
http://127.0.0.1:8080/
```

Options:

```bash
thunderdome simulator serve \
  --host 127.0.0.1 \
  --port 18080 \
  --geometry geometry/thunderdome_geometry.json \
  --positions geometry/generated/led_positions_3d.json \
  --open-browser
```

Use `--no-open-browser` to force no browser launch. `--open-browser` uses Python's standard `webbrowser` module; failure to open a browser does not invalidate the server.

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
- geometry and positions source filenames;
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

The simulator loads authoritative project data through Python:

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

If generated positions are missing or invalid, regenerate them with:

```bash
thunderdome positions generate
thunderdome positions validate
```

Default paths are anchored to the installed project root. Explicit relative paths remain relative to the user's current working directory.

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

Hub inspection displays hub ID and coordinates. H061 is visually distinct.

## Limitations

- Stage A is static geometry only; live effect frames are not streamed to the viewer.
- No WebSocket API is provided.
- No simulator frame sink or output-selection CLI exists yet.
- No browser automation test framework is introduced; frontend logic is kept in small exported functions for future testing.
- Cylindrical spars and physically calibrated hub offsets are future enhancements.
