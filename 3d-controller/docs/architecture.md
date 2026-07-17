# Architecture

The authoritative flow is **geometry -> routes -> generated XYZ -> effects -> RGB frame -> DDP -> WLED**. `geometry/` holds structural facts and manually confirmed routes. A future generator creates `geometry/generated/led_positions_3d.json`; it is not generated in this refactor. Effects render a 5,000-pixel linear `RGBFrame`. DDP sends that complete physical order to WLED.

WLED HTTP support is secondary controller management/fallback functionality. Old 2D ledmaps and SVG coordinate experiments are archived and never imported by active code.

## Animation scheduling

`thunderdome.animation.run_frame_loop` is the generic scheduling layer between a frame producer and either single-controller or multi-controller DDP transport. It uses a monotonic clock and can repeatedly send a static frame, invoke a callback with the frame number and elapsed time, or consume a frame generator. The same layer implements held static DDP frames today and is intended for future generated spatial effects.

A clock-hand sweep, for example, can render a different 5,000-pixel `RGBFrame` for each iteration from the current angle and generated XYZ positions, then pass those frames through `run_frame_loop` to the existing five-controller fan-out. The loop, timing, socket reuse, interruption handling, and transport behavior do not need to be reimplemented for that effect.
