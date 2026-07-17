# Thunderdome 2D-to-3D LED mapping

This directory contains a **separate, read-only-input** mapping pipeline. It does not
change WLED/DDP/controller behaviour and does not overwrite source geometry or the
existing WLED 2D maps.

## Safety model

The existing 2D data is an explicitly uncalibrated SVG-derived first pass. It contains
ordered LED records but no spar IDs, hub IDs, calibrated correspondences, or physical
route transitions. The pipeline is deliberately conservative:

- it validates all source schemas and preserves global indices 0–4999;
- it uses declared centre-relative millimetres and converts 3D geometry metres to mm;
- it does **not** silently solve unknown rotation/reflection from non-fiducial data;
- it assigns XYZ only for a uniquely nearby projected spar that also passes a
  shared-hub continuity gate;
- it leaves ambiguous records explicit, without `x/y/z` fields;
- it keeps all tail LEDs as `location_type: tail, tail_model: unresolved`.

To produce a complete calibrated mapping later, provide multiple measured 2D/3D hub
fiducials (to fit rotation/scale/translation/reflection) and a measured ordered spar
sequence for each string. A future tail model may replace the unresolved tail with a
vertical line, Blender curve, or measured control points.

## Requirements / install

Python 3.11+ and the standard library only. No dependency install is required.

```bash
cd /workspace/thunderdome
python3 --version
```

## Commands

All generated files are deterministic and source inputs remain untouched.

### Inspect inputs and generate the analysis

```bash
cd /workspace/thunderdome
python3 dome-mapping/thunderdome_mapping.py
# writes dome-mapping/ANALYSIS.md
```

### Infer routes and generate XYZ coordinates

The same validated run writes all inference products atomically per file:

```bash
python3 dome-mapping/thunderdome_mapping.py \
  --geometry thunderdome_geometry.json \
  --positions json-controller/wled_map_top_centre_tail_300_v4/led_positions_2d.json
```

Outputs:

- `routes/inferred_routes.json` — per-string spar and explicit unresolved/tail segments.
- `output/led_positions_3d.json` — all 5,000 LED records. Only `location_type: spar`
  records have XYZ values.
- `output/mapping_ambiguities.json` — candidate spars, distances, reasons, and manual
  decisions for unresolved matches.
- `output/mapping_preview.svg` — projected spars and hub IDs, raw old 2D points,
  confidently matched projections, five string colours/direction arrows, and yellow
  ambiguity marks.

Custom output locations are supported:

```bash
python3 dome-mapping/thunderdome_mapping.py \
  --output-dir /tmp/thunderdome-output \
  --routes-dir /tmp/thunderdome-routes \
  --analysis /tmp/ANALYSIS.md
```

When measured fiducials establish a calibrated transform, apply it explicitly (it is
recorded in every generated JSON file). The tool never auto-selects a reflection:

```bash
python3 dome-mapping/thunderdome_mapping.py \
  --scale 1000 --rotation-degrees 12.5 --tx 4 --ty -7 --reflect-y
```

### Run tests

```bash
python3 -m unittest discover -s dome-mapping/tests -v
```

The tests cover source geometry counts/types/connectivity, transforms, point-to-spar
projection, shared-hub continuity and impossible jumps, XYZ interpolation, deterministic
inference, complete index preservation, tails, and input-schema failure behaviour.

## Coordinate convention

`thunderdome_geometry.json` uses right-handed metres (`z` up). The input map's
`x_mm/y_mm` is treated as top-down millimetres centered at its documented dome centre.
The current output transform is recorded in JSON metadata:

```json
{
  "scale": 1000.0,
  "rotation_degrees": 0.0,
  "tx": 0.0,
  "ty": 0.0,
  "reflect_y": false,
  "orientation_status": "unresolved_not_fitted"
}
```

This is a declared unit/centre normalisation—not a claim that the uncalibrated SVG
orientation is physically proven.
