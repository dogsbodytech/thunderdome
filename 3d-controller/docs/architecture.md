# Architecture

## External control contracts

The local REST/browser control path and future MQTT adapters share one coordinator. See [control-architecture.md](control-architecture.md), [runtime-command-contract.md](runtime-command-contract.md), [api-rest.md](api-rest.md), and [mqtt-integration-spec.md](mqtt-integration-spec.md) for contributor-facing contracts.

The authoritative flow is **geometry -> routes -> generated XYZ -> effects -> RGB frame -> DDP -> WLED**. `geometry/` holds authoritative structural facts and manually confirmed physical routes. The active `thunderdome positions generate` command deterministically derives `geometry/generated/led_positions_3d.json`, and `thunderdome positions validate` validates it. Generated positions are derived artefacts that may be ignored by Git, so users can regenerate them locally. They are nominal mathematical positions through the modelled geometry, not a replacement for future physical calibration.

Effects render a logical 5,000-pixel linear `RGBFrame`, which DDP sends in physical order after fan-out to the five controllers. WLED HTTP support is secondary controller management/fallback functionality. WLED 2D ledmaps, old SVG coordinate experiments, and related archives are not the active mapping authority.

## Simulator and frame delivery

`thunderdome simulator serve` is the local aiohttp server for inspecting the same authoritative data and previewing live frames. It loads a compatible geometry/routes/positions set through Python validators, serves the offline browser viewer from `simulator/static/`, and exposes static JSON APIs plus Stage B producer/viewer WebSockets. Its built-in paths are `geometry/thunderdome_geometry.json`, `geometry/reference_string_route.md`, and `geometry/generated/led_positions_3d.json`; `--geometry`, `--routes`, and `--positions` select an explicit compatible set. Built-in defaults are project-root-safe and explicit relative paths are current-working-directory relative.

Before binding, it validates exactly 5,000 ordered LED records, finite XYZ coordinates, H061, controller/string allocation, and tail metadata. The server itself sends no WLED HTTP requests or UDP/DDP packets. The frontend is plain offline HTML/CSS/JavaScript with local Three.js r160 / 0.160.0 and OrbitControls vendor files. It renders hubs, spars, H061, tails, all LED points, optional canvas-texture hub-ID labels, and Stage B live frames using true XYZ coordinates with equal X/Y/Z scale. See [simulator.md](simulator.md).

## Animation scheduling

`thunderdome.animation.run_frame_loop` is the generic scheduling layer between a frame producer and the selected frame sink. It uses a monotonic clock and can repeatedly send a static frame, invoke a callback with the frame number and elapsed time, or consume a frame generator. It implements held static DDP frames and the implemented spatial effects derived from generated positional data.

A clock-hand sweep renders a different 5,000-pixel `RGBFrame` for each iteration from the current angle and generated XYZ positions, then passes those frames through `run_frame_loop` to its selected simulator, DDP, composite, or null sink. The loop, timing, session reuse, interruption handling, and transport behavior are shared across effects.

WLED JSON/HTTP remains a separate persistent-state path. The reusable multi-controller helper explicitly addresses every enabled controller for power, brightness, colour, native effects, palettes, presets, live state, and `prepare-ddp`; controller 1 is never a JSON or DDP master. Live DDP effect output sets enabled controllers' WLED master brightness to `255` before opening the DDP session. That brightness API call can affect WLED's on/off state, so power remains operator-controlled and must be prepared before live output; realtime mode and current-limit settings are not changed.

The clock axis is the authoritative XY coordinate of apex hub H061 loaded from `geometry/thunderdome_geometry.json`, not a position-distribution estimate. All five complete 1,000-LED strings, including generated tail records, are rendered by default; `--exclude-tail` is the explicit opt-out. Tail records share the apex XY and naturally satisfy the radial origin test at all angles.

The other implemented effects share the same immutable, index-aligned XYZ context. `expanding-rings` selects a spherical shell from true XYZ Euclidean distance and wraps its elapsed-time radius at the maximum selected distance. Its origin parser resolves H061 `apex`, dome-only `centre` and `base`, or explicit metre coordinates outside the renderer. `height-wave` derives its selected Z range after tail filtering and moves one full-thickness band up, down, or with a clean triangular-wave bounce. Both produce the same exact 15,000-byte logical RGB frame and use `--loops` for complete physical movement cycles. See [effects.md](effects.md).

## Effect registry and auto mode

`controller/thunderdome/effects/Registry.py` is the small catalogue used by the CLI and `effect auto`. It names production-ready effects, provides per-effect defaults for auto playback, and defines curated presets (`calm`, `energetic`). The registry keeps standalone commands and auto playlists aligned without duplicating effect names in documentation or tests.

`controller/thunderdome/effects/Procedural.py` contains deterministic no-dependency renderers for `fire`, `rotating-plane`, `radar`, `aurora`, and `fireflies`. These renderers use generated XYZ positions, not global LED index order, and each returns the same `RGBFrame` shape as the existing effects. `rotating-plane` uses Rodrigues' formula to rotate a perpendicular plane normal around the configured 3D axis (`vertical=(0,0,1)`, `horizontal=(1,0,0)`, `tilted=normalize(1,1,1)`, or explicit `X,Y,Z`) and precomputes the current normal plus a bounded set of previous trail normals once per frame. Each LED then only does signed-distance/intensity/blending work against those samples. `--trail-degrees` is limited to `0..180`: zero disables the trail, 180 covers all unique absolute-distance plane orientations, and values above 180 are rejected rather than clamped. The trail uses the main plane plus at most 12 previous-orientation samples for Raspberry Pi performance. The firefly renderer uses a reusable deterministic particle template system with seeded position, velocity, lifecycle phase, brightness phase, and true 3D glow falloff.

`effect auto` loads the spatial context and controller mapping once, opens one multi-controller DDP session, and selects frames from the registry playlist over time. During crossfade it blends full-brightness source frames linearly and applies the requested global brightness only once after blending. Incoming effect-local time starts at the beginning of its transition and continues across the interval boundary, so animations do not rewind when the incoming effect becomes primary. Dry-run uses the same scheduler and packet splitting path as live output, but with simulated sends and without HTTP or UDP. Auto is continuous by default until Ctrl+C unless `--cycles` or `--duration` is supplied.

## Stage B frame delivery

Effects produce one 5,000-pixel `RGBFrame` and pass it to a destination-independent sink. `SimulatorFrameSink` sends a versioned binary RGB8 frame to `/ws/producer`; `DDPFrameSink` retains the existing multi-controller fanout; `CompositeFrameSink` delivers the same logical frame to both; and `NullFrameSink` discards validated frames. The aiohttp simulator retains the newest frame and exposes bounded per-viewer queues at `/ws/viewer`, preventing unbounded preview latency.
