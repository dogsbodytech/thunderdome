# Existing 2D Mapping Analysis

## Inputs inspected

- `thunderdome_geometry.json`: schema v1, **61 hubs** and **165 spars**. Hubs have `id`, layer metadata and metre `x/y/z`; spars have stable `id`, `type`, `start_hub`, `end_hub`, and `length_m`.
- `led_positions_2d.json`: top-level `summary` and `positions`. `positions` contains **5000** per-LED objects with `physical_index` (global 0-based index), one-based `string`, 0-based `string_led_index`, raw grid and millimetre XY coordinates, `on_dome_path`, a route distance, and WLED collision/nudge coordinates.
- `led_positions_2d_app_compatible.json`: same positions with a duplicate `led_index` field for application compatibility.
- `led_positions_2d.csv`: serialisation of the same position schema; booleans are text.
- `ledmap_on_dome.json` / `ledmap_all_5000_tail_top_centre_cluster.json`: WLED maps with `n`, `width`, `height`, `map`; they do not contain physical route geometry.
- `mapping_summary.json`, README and preview: explanatory/generated metadata, not surveyed geometry.

## Indexes, strings, and tail

`physical_index` is a complete ordered 0..4999 global index. Each one-based string 1..5 has `string_led_index` 0..999; the converter normalises string IDs to 0..4. There are 4665 on-dome records and 335 tail records. Tail records have `on_dome_path: false`, note `tail_hangs_down_from_top_centre_raw_xy_overlap`, and the same raw XY centre position. The all-LED WLED map deliberately nudges those coincident points into cells; those nudges are not physical coordinates.

## What is and is not inferable

The source is explicitly `calculated_first_pass_not_camera_calibrated`. It says each string follows an SVG/draw.io label sequence `24..1`, but it does **not** give spar IDs, hub IDs, segment-to-spar correspondence, calibrated hub fiducials, or a structural transition list. A continuous ordered LED sequence alone cannot distinguish projected spar crossings or select a unique five-fold orientation/reflection.

The pipeline therefore normalises declared common-centre coordinates by metres-to-millimetres only. Rotation and reflection remain unresolved and are recorded as a provisional model convention, not fitted facts. It computes nearest-spar candidates and only emits XYZ for candidates within 45 mm that are separated from the next candidate by 12 mm and survive the shared-hub transition gate. All other records remain explicit unresolved records. Current generated result: 1510 confident spar LEDs, 3155 unresolved LEDs, and 335 unresolved-model tail LEDs.

## Conflicts and required manual decisions

1. The claimed per-string on-dome length is 28 m while the 2D route is a generated SVG shape; neither provides a spar-level route. It cannot validate physical wiring against the 3D graph.
2. `grid_x/y` use screen-like grid coordinates while `x_mm/y_mm` are raw physical top-down coordinates. Use `x_mm/y_mm`; do not infer geometry from collision-nudged WLED cells.
3. A reflected or rotated projection cannot be selected without at least one (preferably several) measured hub/LED correspondences. Supply those fiducials and a measured spar sequence per string to resolve routes safely.
4. Tail XY overlap provides no 3D curve or order beyond string order. It is represented as `tail_model: unresolved` until measured vertical-line, Blender-curve, or control-point data is supplied.
