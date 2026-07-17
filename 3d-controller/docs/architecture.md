# Architecture

The authoritative flow is **geometry -> routes -> generated XYZ -> effects -> RGB frame -> DDP -> WLED**. `geometry/` holds authoritative structural facts and manually confirmed physical routes. The active `thunderdome positions generate` command deterministically derives `geometry/generated/led_positions_3d.json`, and `thunderdome positions validate` validates it. Generated positions are derived artefacts that may be ignored by Git, so users can regenerate them locally. They are nominal mathematical positions through the modelled geometry, not a replacement for future physical calibration.

Effects render a logical 5,000-pixel linear `RGBFrame`, which DDP sends in physical order after fan-out to the five controllers. WLED HTTP support is secondary controller management/fallback functionality. WLED 2D ledmaps, old SVG coordinate experiments, and related archives are not the active mapping authority.

## Animation scheduling

`thunderdome.animation.run_frame_loop` is the generic scheduling layer between a frame producer and either single-controller or multi-controller DDP transport. It uses a monotonic clock and can repeatedly send a static frame, invoke a callback with the frame number and elapsed time, or consume a frame generator. The same layer implements held static DDP frames today and consumes frames derived from the generated positional data for future spatial effects.

A clock-hand sweep, for example, can render a different 5,000-pixel `RGBFrame` for each iteration from the current angle and generated XYZ positions, then pass those frames through `run_frame_loop` to the existing five-controller fan-out. The loop, timing, socket reuse, interruption handling, and transport behavior do not need to be reimplemented for that effect.

WLED JSON/HTTP remains a separate persistent-state path. The reusable multi-controller helper explicitly addresses every enabled controller for power, brightness, colour, native effects, palettes, presets, live state, and `prepare-ddp`; controller 1 is never a JSON or DDP master. `prepare-ddp` sends `{on:false,bri:255,live:false}` atomically so application DDP frames use Python brightness while timeout fallback is off.
