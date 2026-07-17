# Repository inventory after 3D/DDP refactor

## Final active structure

```text
assets/blender/                         Blender source models
geometry/thunderdome_geometry.json      authoritative structure
geometry/reference_string_route.md      authoritative manually captured route
geometry/routes/                        future validated route documents
geometry/generated/                     future authoritative LED XYZ output
controller/thunderdome/                 active Python package
  geometry.py routes.py led_positions.py frame.py cli.py
  transport/ddp.py                      realtime DDP transport
  wled/client.py favorites.py explore.py secondary controller support
controller/tests/                       active geometry/frame/DDP tests
docs/                                   active project documentation
archive/                                superseded experiments and historical docs
```

## Archived

- `archive/wled-2d-map-experiment/`: old 300×300 WLED ledmaps, SVG coordinates, upload/clock tooling and tests.
- `archive/2d-to-3d-inference-experiment/`: projected-spar inference code, analysis, tests and generated candidates.
- `archive/json-controller-legacy/` and `archive/json-controller-docs/`: former mixed CLI/tests/docs.

## Ignored clutter

`.gitignore` excludes `__pycache__/`, `*.py[cod]`, `*.blend1`, nested ZIP bundles, build products, and future generated LED position data. Existing `.blend1` backups and `json-controller.zip` were retained, not deleted.

## Command migration

| Old | New / status |
|---|---|
| `python wledctl.py ddp ...` | `thunderdome ddp clear|solid|pixel|range ...` |
| `python wledctl.py info/state/brightness` | `thunderdome controller info|state|brightness ...` |
| `wledctl mapping ...` | archived; no active 2D mapping CLI |
| `python wledctl.py favorites ...` | archived legacy support pending a focused active command surface |

## Remaining work

Capture/validate all five routes from the manual reference and rotational symmetry; generate authoritative 5,000 LED XYZ records including a measured tail model; then implement spatial effects/animation scheduling.
