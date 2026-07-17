# Thunderdome WLED 2D map - top-centre tail corrected v4 - 300 grid

Generated from `lighting/layout/Layout.drawio` plus the repo dimensions and the corrected physical routing assumption:

- each LED string starts at the centre of the side/pentagon shown in the layout;
- each string follows the descending labelled sequence `24, 23, 22, ... 1`;
- each on-dome route ends at the top-centre pentagon;
- the final ~2m of each 30m string hangs down from that top-centre point.

This is a calculated first pass, not a camera/LiDAR calibrated map.

## Files

- `ledmap_on_dome.json`: WLED-compatible 300x300 map for the 4665 LEDs expected to sit on dome spars. The 335 hanging-tail LEDs are omitted.
- `ledmap_all_5000_tail_top_centre_cluster.json`: WLED-compatible 300x300 map including all 5000 LEDs. The hanging-tail LEDs have raw physical top-down coordinates at the dome centre, but the exported WLED cells are nudged into a small centre cluster because WLED cannot store multiple LED indices in one grid cell.
- `led_positions_2d.json`: per-LED coordinate data and metadata. This preserves the raw top-down centre overlap for hanging-tail LEDs.
- `led_positions_2d.csv`: same position data in CSV form.
- `mapping_summary.json`: summary, collision/nudge handling, and omitted LED list.
- `preview.svg`: visual sanity-check of the five generated paths and central tail cluster.

## Summary

```json
{
  "name": "thunderdome-top-centre-tail-300-v4",
  "status": "calculated_first_pass_not_camera_calibrated",
  "correction": "LED paths start at side/pentagon centre, follow labels 24..1, end at the top-centre pentagon; remaining 2m tail hangs from that top centre.",
  "grid_width": 300,
  "grid_height": 300,
  "cell_size_mm_nominal": 20.0,
  "dome_diameter_mm": 6000.0,
  "strings": 5,
  "leds_per_string": 1000,
  "total_leds": 5000,
  "led_pitch_mm": 30.0,
  "on_dome_length_mm": 28000.0,
  "tail_length_mm": 2000.0,
  "on_dome_leds_per_string": 933,
  "tail_extra_leds_per_string": 67,
  "on_dome_leds_total": 4665,
  "tail_extra_leds_total": 335,
  "path_sequence_per_string": "24,23,22,...,1",
  "route_model": "red SVG/draw.io 24..1 path converted to a local route ending at top-centre, then rotated five-fold",
  "segment_length_model": "uniform per half using README totals: 24-13 = 13.8m, 12-1 = 14.2m",
  "top_centre_raw_grid": [
    150,
    150
  ],
  "top_centre_raw_mm": [
    0.0,
    0.0
  ],
  "svg_route_start_px": {
    "x": 411.0,
    "y": 402.0
  },
  "svg_route_end_top_centre_px": {
    "x": 418.0,
    "y": 109.0
  },
  "svg_max_vector_radius_px": 423.34489149318244,
  "svg_to_topdown_scale_mm_per_px": 7.086420694528003,
  "on_dome_map_placed_leds": 4665,
  "on_dome_map_omitted_tail_leds": 335,
  "on_dome_map_nudged_leds": 359,
  "all_led_map_placed_leds": 5000,
  "all_led_map_nudged_leds": 713,
  "tail_policy_on_dome_map": "tail/extra 67 LEDs per string omitted",
  "tail_policy_all_led_map": "tail/extra 67 LEDs per string have raw top-down x/y at centre and are nudged around centre only for WLED uniqueness",
  "important_caveat": "The all-LED map cannot represent the physical top-down overlap of the hanging tail exactly because WLED ledmap cells hold a single LED index. Raw positions preserve the true overlap; exported all-LED map uses nearest-empty-cell nudging around centre."
}
```

## Important caveats

The route model uses the complete red `24..1` labelled SVG path as the shape basis, transforms its final point to the top-centre of the dome, scales the path into the 6m circular footprint, and rotates it five-fold for the five strings.

The segment length model still uses the README totals rather than confirmed A/B/C strut type per label: labels 24-13 share 13.8m and labels 12-1 share 14.2m.

The physically correct top-down position of the hanging 2m section is an overlap at the centre. `led_positions_2d.json` records that raw overlap. The all-LED WLED export must nudge those LEDs around the centre because a WLED 2D ledmap cell can only hold one LED index. For clean top-down dome effects, `ledmap_on_dome.json` is still the safer test map.
