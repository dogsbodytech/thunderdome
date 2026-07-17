# Architecture

The authoritative flow is **geometry -> routes -> generated XYZ -> effects -> RGB frame -> DDP -> WLED**. `geometry/` holds structural facts and manually confirmed routes. A future generator creates `geometry/generated/led_positions_3d.json`; it is not generated in this refactor. Effects render a 5,000-pixel linear `RGBFrame`. DDP sends that complete physical order to WLED.

WLED HTTP support is secondary controller management/fallback functionality. Old 2D ledmaps and SVG coordinate experiments are archived and never imported by active code.
