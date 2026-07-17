# Repository inventory before 3D/DDP refactor

**Recorded before moves or renames.** This workspace is not a Git repository in the
current environment, so `git mv` and commits cannot be used here; file moves will
preserve contents and are documented below.

## Top-level items

| Path | Current purpose / dependencies | Classification | Proposed destination |
|---|---|---|---|
| `IDEA.md` | One-word scratch note; no references | unclear | `archive/repository-notes/IDEA.md` |
| `thunderdome_geometry.json` | Exported 61-hub/165-spar model; read by `dome-mapping/thunderdome_mapping.py` | **authoritative** | `geometry/thunderdome_geometry.json` |
| `thunderdome_3v_5_8_scaled.blend` | Validated physical-scale editable Blender model | **authoritative** | `assets/blender/thunderdome_3v_5_8_scaled.blend` |
| `thunderdome_3v_5_8_base.blend` | Original generated topology model | authoritative historical source | `assets/blender/thunderdome_3v_5_8_base.blend` |
| `thunderdome_3v_5_8_scaled.blend1` | Blender automatic backup | clutter / user data | leave in place; add `*.blend1` to `.gitignore` |
| `thunderdome_3v_5_8_base.blend1` | Blender automatic backup | clutter / user data | leave in place; add `*.blend1` to `.gitignore` |
| `json-controller.zip` | Nested historical archive of the controller; no code imports | duplicate bundle / clutter | leave in place; add `*.zip` to `.gitignore` |
| `json-controller/` | Current WLED HTTP/DDP application and 2D-map experiment package | active mixed with superseded work | split into `controller/` and `archive/` |
| `dome-mapping/` | 2D-to-3D inference experiment and authoritative manual single-string route | mixed experimental / authoritative route | archive experiment; move reference route to `geometry/` |

## `json-controller/`

| Path | Current purpose / dependencies | Classification | Proposed destination |
|---|---|---|---|
| `wled_ddp.py` | Tested DDP UDP packets, chunking, RGB frames; imported by `wledctl.py`, `wled_mapping.py`, and DDP tests | active reusable | `controller/thunderdome/transport/ddp.py` |
| `wled_client.py` | Tested standard-library WLED JSON API client; imported by CLI, favorites, explorer, mapping tests | active secondary management support | `controller/thunderdome/wled/client.py` |
| `wled_favorites.py` | Tested native-effect favorites storage/cycle; imports `wled_client` | active optional WLED support | `controller/thunderdome/wled/favorites.py` |
| `wledctl.py` | Current mixed CLI: WLED HTTP, DDP, favorites, and 2D mapping | active but needs split | replace with `controller/thunderdome/cli.py`; preserve a deprecated wrapper |
| `explore_wled.py` | HTTP endpoint exploration helper; imports `wled_client` | useful optional support | `controller/thunderdome/wled/explore.py` |
| `wled_mapping.py` | WLED ledmap validation/upload, 2D coordinates, clock tests/sweeps; imports client + DDP | superseded 2D experiment | `archive/wled-2d-map-experiment/code/wled_mapping.py` |
| `wled_map_top_centre_tail_300_v4/` | 300×300 SVG-derived 2D map JSON/CSV/SVG/README/prompt | superseded historical experiment | `archive/wled-2d-map-experiment/data/` |
| `tests/test_wled_ddp.py` | 10 DDP transport tests | active | `controller/tests/test_ddp.py` |
| `tests/test_wled_client.py` | HTTP client, favorites, CLI parsing tests | split active/legacy | active assertions adapted to `controller/tests/`; old mapping assertions archived |
| `tests/test_wled_mapping.py` | 2D mapping/clock test tests | superseded experiment | `archive/wled-2d-map-experiment/tests/test_wled_mapping.py` |
| `FEATURES.md`, `QUICKSTART.md`, `example_payloads.md`, `WLED_JSON_API_FINDINGS.md` | Mixed application and WLED HTTP documentation | historical/support documentation | `archive/json-controller-docs/` (active docs replaced) |
| `REVIEW_BUNDLE.md` | Historical review notes | historical | `archive/json-controller-docs/` |

## `dome-mapping/`

| Path | Current purpose / dependencies | Classification | Proposed destination |
|---|---|---|---|
| `thunderdome_single_string_dome_route.md` | User-confirmed manual reference hub route ending at H061 | **authoritative route input** | `geometry/reference_string_route.md` |
| `thunderdome_mapping.py` | Conservative old-2D projected-spar inference | superseded experiment | `archive/2d-to-3d-inference-experiment/thunderdome_mapping.py` |
| `ANALYSIS.md`, `README.md` | Analysis/docs for inference experiment | historical experiment docs | `archive/2d-to-3d-inference-experiment/` |
| `output/` | Generated inferred 3D candidates, ambiguity report, preview | experimental generated output | `archive/2d-to-3d-inference-experiment/output/` |
| `routes/inferred_routes.json` | Generated 2D-inference result, not authoritative route | experimental generated output | `archive/2d-to-3d-inference-experiment/routes/` |
| `tests/test_pipeline.py` | Eight inference experiment tests | archived test suite | `archive/2d-to-3d-inference-experiment/tests/` |

## Dependency summary

- `wledctl.py` owns the old application command surface and imports all four WLED modules.
- `wled_mapping.py` is the only consumer of old 2D position/ledmap data at runtime.
- `wled_ddp.py` is independent of 2D mapping and is the reusable tested transport.
- `wled_client.py` and `wled_favorites.py` are independent of 2D mapping and remain secondary management support.
- The old inference script reads `thunderdome_geometry.json` and archived 2D positions; no active code will consume its results after the refactor.

## Baseline test results

Run before changes:

```text
python3 -m unittest discover -s dome-mapping/tests -v
Ran 8 tests ... OK

cd json-controller && python3 -m unittest discover -s tests -v
Ran 61 tests ... OK
```
