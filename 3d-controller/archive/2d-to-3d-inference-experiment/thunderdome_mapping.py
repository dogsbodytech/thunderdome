#!/usr/bin/env python3
"""Deterministic, conservative conversion of Thunderdome's 2D LED map to 3D.

The input map is treated as evidence, not as a route specification: a LED receives a
spar XYZ position only when its projected point is close to one unambiguous spar and
its neighbours do not make an impossible graph transition.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_GEOMETRY = PROJECT / "thunderdome_geometry.json"
DEFAULT_POSITIONS = PROJECT / "json-controller/wled_map_top_centre_tail_300_v4" / "led_positions_2d.json"
DEFAULT_OUTPUT = PROJECT / "dome-mapping" / "output"
DEFAULT_ROUTES = PROJECT / "dome-mapping" / "routes"

# The 2D source explicitly uses millimetres centred at [0, 0]; geometry uses metres.
# These conservative tolerances deliberately avoid asserting routes from a first-pass,
# uncalibrated SVG map.
MATCH_TOLERANCE_MM = 45.0
AMBIGUITY_GAP_MM = 12.0
HUB_TRANSITION_TOLERANCE_MM = 100.0


class GeometryError(ValueError):
    """Raised when a source document violates its required mapping schema."""


@dataclass(frozen=True)
class Hub:
    id: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Spar:
    id: str
    type: str
    start_hub: str
    end_hub: str
    length_m: float


@dataclass(frozen=True)
class Geometry:
    hubs: dict[str, Hub]
    spars: tuple[Spar, ...]


@dataclass(frozen=True)
class Position:
    global_index: int
    string_id: int
    string_index: int
    x_mm: float
    y_mm: float
    on_dome_path: bool
    note: str


@dataclass(frozen=True)
class SparMatch:
    spar_id: str
    distance: float
    fraction: float
    projected_x: float
    projected_y: float


def _require(value: Any, name: str, expected: type | tuple[type, ...]) -> Any:
    if not isinstance(value, expected):
        raise GeometryError(f"{name} must be {expected}, got {type(value).__name__}")
    return value


def load_geometry(path: Path) -> Geometry:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise GeometryError(f"Cannot read geometry {path}: {exc}") from exc
    hubs_raw = _require(data.get("hubs"), "geometry.hubs", list)
    spars_raw = _require(data.get("spars"), "geometry.spars", list)
    hubs: dict[str, Hub] = {}
    for raw in hubs_raw:
        _require(raw, "hub", dict)
        try:
            hub = Hub(str(raw["id"]), float(raw["x"]), float(raw["y"]), float(raw["z"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GeometryError(f"Invalid hub record: {raw!r}") from exc
        if hub.id in hubs:
            raise GeometryError(f"Duplicate hub ID: {hub.id}")
        hubs[hub.id] = hub
    spars: list[Spar] = []
    spar_ids: set[str] = set()
    for raw in spars_raw:
        _require(raw, "spar", dict)
        try:
            spar = Spar(str(raw["id"]), str(raw["type"]), str(raw["start_hub"]), str(raw["end_hub"]), float(raw["length_m"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GeometryError(f"Invalid spar record: {raw!r}") from exc
        if spar.id in spar_ids or spar.start_hub not in hubs or spar.end_hub not in hubs or spar.type not in {"A", "B", "C"}:
            raise GeometryError(f"Invalid spar references/type: {raw!r}")
        spar_ids.add(spar.id)
        spars.append(spar)
    if len(hubs) != 61 or len(spars) != 165:
        raise GeometryError(f"Expected 61 hubs and 165 spars, got {len(hubs)} and {len(spars)}")
    counts = Counter(s.type for s in spars)
    if counts != Counter({"A": 30, "B": 55, "C": 80}):
        raise GeometryError(f"Unexpected spar type counts: {dict(counts)}")
    return Geometry(hubs, tuple(sorted(spars, key=lambda value: value.id)))


def validate_positions(document: dict[str, Any]) -> list[Position]:
    raw_positions = _require(document.get("positions"), "positions.positions", list)
    if len(raw_positions) != 5000:
        raise GeometryError(f"Expected 5,000 2D positions, got {len(raw_positions)}")
    result: list[Position] = []
    seen: set[int] = set()
    for raw in raw_positions:
        _require(raw, "position", dict)
        required = ("physical_index", "string", "string_led_index", "x_mm", "y_mm", "on_dome_path", "note")
        if any(key not in raw for key in required):
            raise GeometryError(f"Position missing required fields: {raw!r}")
        try:
            item = Position(int(raw["physical_index"]), int(raw["string"]) - 1, int(raw["string_led_index"]), float(raw["x_mm"]), float(raw["y_mm"]), bool(raw["on_dome_path"]), str(raw["note"]))
        except (TypeError, ValueError) as exc:
            raise GeometryError(f"Invalid position record: {raw!r}") from exc
        if item.global_index in seen or item.string_id not in range(5) or item.string_index not in range(1000):
            raise GeometryError(f"Invalid/duplicate position index: {raw!r}")
        seen.add(item.global_index)
        result.append(item)
    result.sort(key=lambda value: value.global_index)
    if [value.global_index for value in result] != list(range(5000)):
        raise GeometryError("physical_index must be a complete, ordered 0..4999 set")
    if Counter((p.string_id, p.string_index) for p in result) != Counter((s, i) for s in range(5) for i in range(1000)):
        raise GeometryError("String IDs or per-string indexes do not form five 0..999 sequences")
    return result


def load_positions(path: Path) -> tuple[dict[str, Any], list[Position]]:
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise GeometryError(f"Cannot read 2D positions {path}: {exc}") from exc
    _require(document, "positions document", dict)
    return _require(document.get("summary"), "positions.summary", dict), validate_positions(document)


def build_graph(geometry: Geometry) -> dict[str, list[tuple[str, str]]]:
    graph = {hub_id: [] for hub_id in geometry.hubs}
    for spar in geometry.spars:
        graph[spar.start_hub].append((spar.end_hub, spar.id))
        graph[spar.end_hub].append((spar.start_hub, spar.id))
    for values in graph.values():
        values.sort()
    return graph


def apply_transform(point: tuple[float, float], *, scale: float, rotation_degrees: float, tx: float, ty: float, reflect_y: bool) -> tuple[float, float]:
    x, y = point
    radians = math.radians(rotation_degrees)
    xr = scale * (math.cos(radians) * x - math.sin(radians) * y)
    yr = scale * (math.sin(radians) * x + math.cos(radians) * y)
    return xr + tx, (-yr if reflect_y else yr) + ty


def match_point_to_spar(point: tuple[float, float], spar: Spar, hubs: dict[str, Hub], *, scale: float = 1000.0, rotation_degrees: float = 0.0, tx: float = 0.0, ty: float = 0.0, reflect_y: bool = False) -> SparMatch:
    ax, ay = apply_transform((hubs[spar.start_hub].x, hubs[spar.start_hub].y), scale=scale, rotation_degrees=rotation_degrees, tx=tx, ty=ty, reflect_y=reflect_y)
    bx, by = apply_transform((hubs[spar.end_hub].x, hubs[spar.end_hub].y), scale=scale, rotation_degrees=rotation_degrees, tx=tx, ty=ty, reflect_y=reflect_y)
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    fraction = 0.0 if denom == 0 else max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / denom))
    px, py = ax + fraction * dx, ay + fraction * dy
    return SparMatch(spar.id, math.hypot(point[0] - px, point[1] - py), fraction, px, py)


def interpolate_xyz(start: Hub, end: Hub, fraction: float) -> tuple[float, float, float]:
    return tuple(a + fraction * (b - a) for a, b in zip((start.x, start.y, start.z), (end.x, end.y, end.z)))


def _candidate_matches(position: Position, geometry: Geometry, transform: dict[str, Any]) -> list[SparMatch]:
    matches = [match_point_to_spar((position.x_mm, position.y_mm), spar, geometry.hubs, **transform) for spar in geometry.spars]
    return sorted(matches, key=lambda value: (value.distance, value.spar_id))


def _shared_hub(one: Spar, two: Spar) -> str | None:
    shared = {one.start_hub, one.end_hub}.intersection((two.start_hub, two.end_hub))
    return min(shared) if shared else None


def _transition_is_valid(previous: dict[str, Any], current: dict[str, Any], spar_by_id: dict[str, Spar], hubs: dict[str, Hub]) -> bool:
    if previous.get("spar_id") == current.get("spar_id"):
        return True
    a, b = spar_by_id[previous["spar_id"]], spar_by_id[current["spar_id"]]
    shared = _shared_hub(a, b)
    if not shared:
        return False
    hub = hubs[shared]
    prev_endpoint = 0.0 if a.start_hub == shared else 1.0
    curr_endpoint = 0.0 if b.start_hub == shared else 1.0
    return (abs(previous["fraction_along_spar"] - prev_endpoint) * a.length_m * 1000 <= HUB_TRANSITION_TOLERANCE_MM and abs(current["fraction_along_spar"] - curr_endpoint) * b.length_m * 1000 <= HUB_TRANSITION_TOLERANCE_MM)


def infer(geometry: Geometry, positions: list[Position], summary: dict[str, Any], transform_override: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    # The default is declared unit conversion. Optional transform parameters make the
    # projection capable of calibrated translation/scale/rotation/reflection once
    # external fiducials exist; they are never estimated from this ambiguous source.
    transform: dict[str, Any] = transform_override or {"scale": 1000.0, "rotation_degrees": 0.0, "tx": 0.0, "ty": 0.0, "reflect_y": False}
    transform_metadata = {**transform, "source_units": "metres", "target_units": "millimetres", "method": "user-supplied calibrated transform" if transform_override else "declared common centre and unit conversion; rotation/reflection held at model convention because source has no fiducials", "orientation_status": "user_supplied" if transform_override else "unresolved_not_fitted"}
    spar_by_id = {spar.id: spar for spar in geometry.spars}
    output: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    by_string: dict[int, list[dict[str, Any]]] = defaultdict(list)
    candidate_cache: dict[int, list[SparMatch]] = {}
    for position in positions:
        base = {"global_index": position.global_index, "string_id": position.string_id, "string_index": position.string_index}
        if not position.on_dome_path:
            item = {**base, "location_type": "tail", "tail_model": "unresolved", "source_note": position.note, "source_x_mm": position.x_mm, "source_y_mm": position.y_mm, "confidence": 0.0}
            output.append(item); by_string[position.string_id].append(item); continue
        candidates = _candidate_matches(position, geometry, transform)
        candidate_cache[position.global_index] = candidates
        best, second = candidates[0], candidates[1]
        close = best.distance <= MATCH_TOLERANCE_MM
        separated = second.distance - best.distance >= AMBIGUITY_GAP_MM
        confidence = max(0.0, min(1.0, (1.0 - best.distance / MATCH_TOLERANCE_MM) * min(1.0, (second.distance - best.distance) / AMBIGUITY_GAP_MM)))
        spar = spar_by_id[best.spar_id]
        xyz = interpolate_xyz(geometry.hubs[spar.start_hub], geometry.hubs[spar.end_hub], best.fraction)
        item: dict[str, Any] = {**base, "location_type": "spar_candidate", "spar_id": spar.id, "from_hub": spar.start_hub, "to_hub": spar.end_hub, "fraction_along_spar": round(best.fraction, 9), "distance_along_spar_m": round(best.fraction * spar.length_m, 9), "x": round(xyz[0], 9), "y": round(xyz[1], 9), "z": round(xyz[2], 9), "match_distance_2d": round(best.distance, 6), "confidence": round(confidence, 6), "candidate_status": "pending_continuity"}
        if not close or not separated:
            item["location_type"] = "unresolved"
            item["reason"] = "too_far_from_projected_spar" if not close else "multiple_nearby_projected_spars"
            item.pop("x"); item.pop("y"); item.pop("z")
            ambiguities.append({"global_index": position.global_index, "string_id": position.string_id, "candidate_spars": [{"spar_id": m.spar_id, "distance_mm": round(m.distance, 3), "fraction": round(m.fraction, 6), "candidate_confidence": round(max(0.0, min(1.0, 1.0 - m.distance / MATCH_TOLERANCE_MM)), 6)} for m in candidates[:5]], "reason": item["reason"], "suggested_manual_decision": "Provide calibrated hub/LED fiducials or a measured spar route."})
        output.append(item); by_string[position.string_id].append(item)
    # Graph continuity gate. A non-structural change between consecutive confident candidates
    # invalidates both point assignments rather than silently forcing either spar.
    for entries in by_string.values():
        for previous, current in zip(entries, entries[1:]):
            if previous["location_type"] != "spar_candidate" or current["location_type"] != "spar_candidate":
                continue
            if not _transition_is_valid(previous, current, spar_by_id, geometry.hubs):
                for item in (previous, current):
                    item["location_type"] = "unresolved"
                    item["reason"] = "impossible_non_structural_spar_jump"
                    item.pop("x", None); item.pop("y", None); item.pop("z", None)
                    ambiguities.append({"global_index": item["global_index"], "string_id": item["string_id"], "candidate_spars": [{"spar_id": m.spar_id, "distance_mm": round(m.distance, 3), "fraction": round(m.fraction, 6), "candidate_confidence": round(max(0.0, min(1.0, 1.0 - m.distance / MATCH_TOLERANCE_MM)), 6)} for m in candidate_cache[item["global_index"]][:5]], "reason": "impossible_non_structural_spar_jump", "suggested_manual_decision": "Specify the structural spar transition or replace the SVG-derived 2D route with calibrated measurements."})
        for item in entries:
            if item["location_type"] == "spar_candidate":
                item["location_type"] = "spar"; item.pop("candidate_status", None)
    routes = {"schema_version": 1, "transform": transform_metadata, "strings": [{"string_id": sid, "segments": _segments(by_string[sid])} for sid in range(5)]}
    output_document = {"schema_version": 1, "source": {"geometry": str(DEFAULT_GEOMETRY.name), "positions_2d": str(DEFAULT_POSITIONS.name)}, "transform": transform_metadata, "leds": output}
    ambiguity_document = {"schema_version": 1, "tolerances_mm": {"match": MATCH_TOLERANCE_MM, "candidate_gap": AMBIGUITY_GAP_MM, "hub_transition": HUB_TRANSITION_TOLERANCE_MM}, "ambiguities": sorted({row["global_index"]: row for row in ambiguities}.values(), key=lambda row: row["global_index"])}
    stats = {"matched_confidently": sum(row["location_type"] == "spar" for row in output), "tail": sum(row["location_type"] == "tail" for row in output), "unresolved": sum(row["location_type"] == "unresolved" for row in output), "ambiguous": len(ambiguity_document["ambiguities"])}
    return routes, output_document, output, {"document": ambiguity_document, "stats": stats}


def _segments(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []
    key: tuple[Any, ...] | None = None
    for item in entries:
        current_key = (item["location_type"], item.get("spar_id"))
        if current_key != key and group:
            result.append(_segment_from_group(group)); group = []
        group.append(item); key = current_key
    if group: result.append(_segment_from_group(group))
    return result


def _segment_from_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    first, last = group[0], group[-1]
    base = {"location_type": first["location_type"], "first_global_index": first["global_index"], "last_global_index": last["global_index"], "first_string_index": first["string_index"], "last_string_index": last["string_index"]}
    if first["location_type"] == "spar":
        return {"spar_id": first["spar_id"], "from_hub": first["from_hub"], "to_hub": first["to_hub"], **base}
    if first["location_type"] == "tail": return {"tail_model": "unresolved", **base}
    return {"reason": first.get("reason", "unresolved"), **base}


def make_preview(path: Path, geometry: Geometry, rows: list[dict[str, Any]], positions: list[Position], transform: dict[str, Any]) -> None:
    """Write a self-contained diagnostic SVG; raw points are never replaced by WLED nudges."""
    colours = ["#e53935", "#1e88e5", "#43a047", "#fb8c00", "#8e24aa"]
    def xy(point: tuple[float, float]) -> tuple[float, float]: return (500 + point[0] * .14, 500 - point[1] * .14)
    lines, labels, source_points, matched_points, ambiguous_marks, arrows = [], [], [], [], [], []
    for s in geometry.spars:
        a = apply_transform((geometry.hubs[s.start_hub].x, geometry.hubs[s.start_hub].y), **transform); b = apply_transform((geometry.hubs[s.end_hub].x, geometry.hubs[s.end_hub].y), **transform); ax, ay = xy(a); bx, by = xy(b)
        lines.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}"/>')
    for h in geometry.hubs.values():
        x, y = xy(apply_transform((h.x, h.y), **transform)); labels.append(f'<text x="{x+3:.1f}" y="{y-3:.1f}">{h.id}</text>')
    by_index = {p.global_index: p for p in positions}
    for row in rows:
        source = by_index[row["global_index"]]
        if source.on_dome_path:
            x, y = xy((source.x_mm, source.y_mm))
            source_points.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.9" fill="{colours[row["string_id"]]}" opacity=".36"/>')
            if row["location_type"] == "unresolved":
                ambiguous_marks.append(f'<path d="M{x-2:.1f},{y-2:.1f} L{x+2:.1f},{y+2:.1f} M{x+2:.1f},{y-2:.1f} L{x-2:.1f},{y+2:.1f}" stroke="#ffeb3b" stroke-width=".7"/>')
        if row["location_type"] == "spar":
            s = next(s for s in geometry.spars if s.id == row["spar_id"]); a, b = geometry.hubs[s.start_hub], geometry.hubs[s.end_hub]
            q = apply_transform((a.x + row["fraction_along_spar"] * (b.x-a.x), a.y + row["fraction_along_spar"] * (b.y-a.y)), **transform); x, y = xy(q)
            matched_points.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.55" fill="{colours[row["string_id"]]}" stroke="#fff" stroke-width=".25"/>')
    for sid in range(5):
        seq = [p for p in positions if p.string_id == sid and p.on_dome_path]
        if seq:
            a, b = xy((seq[0].x_mm, seq[0].y_mm)), xy((seq[-1].x_mm, seq[-1].y_mm))
            arrows.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{colours[sid]}" opacity=".55" stroke-width="1.5" marker-end="url(#arrow{sid})"/>')
    unresolved = [r for r in rows if r["location_type"] == "unresolved"]
    markers = ''.join(f'<marker id="arrow{i}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6z" fill="{c}"/></marker>' for i, c in enumerate(colours))
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><defs>{markers}</defs><rect width="1000" height="1000" fill="#101218"/><g stroke="#53606d" stroke-width="1">{''.join(lines)}</g><g>{''.join(source_points)}</g><g>{''.join(arrows)}</g><g>{''.join(ambiguous_marks)}</g><g>{''.join(matched_points)}</g><g font-family="monospace" font-size="7" fill="#b9c4d0">{''.join(labels)}</g><text x="20" y="30" fill="white" font-family="sans-serif" font-size="16">Thunderdome: projected spars, raw 2D points, and conservative matches</text><text x="20" y="52" fill="#ffeb3b" font-family="sans-serif" font-size="13">yellow X = unresolved/ambiguous ({len(unresolved)}); coloured arrows = raw string direction; tail XY overlap omitted</text></svg>''')


def write_analysis(path: Path, summary: dict[str, Any], geometry: Geometry, positions: list[Position], stats: dict[str, int]) -> None:
    path.write_text(f'''# Existing 2D Mapping Analysis

## Inputs inspected

- `thunderdome_geometry.json`: schema v1, **{len(geometry.hubs)} hubs** and **{len(geometry.spars)} spars**. Hubs have `id`, layer metadata and metre `x/y/z`; spars have stable `id`, `type`, `start_hub`, `end_hub`, and `length_m`.
- `led_positions_2d.json`: top-level `summary` and `positions`. `positions` contains **{len(positions)}** per-LED objects with `physical_index` (global 0-based index), one-based `string`, 0-based `string_led_index`, raw grid and millimetre XY coordinates, `on_dome_path`, a route distance, and WLED collision/nudge coordinates.
- `led_positions_2d_app_compatible.json`: same positions with a duplicate `led_index` field for application compatibility.
- `led_positions_2d.csv`: serialisation of the same position schema; booleans are text.
- `ledmap_on_dome.json` / `ledmap_all_5000_tail_top_centre_cluster.json`: WLED maps with `n`, `width`, `height`, `map`; they do not contain physical route geometry.
- `mapping_summary.json`, README and preview: explanatory/generated metadata, not surveyed geometry.

## Indexes, strings, and tail

`physical_index` is a complete ordered 0..4999 global index. Each one-based string 1..5 has `string_led_index` 0..999; the converter normalises string IDs to 0..4. There are {sum(p.on_dome_path for p in positions)} on-dome records and {sum(not p.on_dome_path for p in positions)} tail records. Tail records have `on_dome_path: false`, note `tail_hangs_down_from_top_centre_raw_xy_overlap`, and the same raw XY centre position. The all-LED WLED map deliberately nudges those coincident points into cells; those nudges are not physical coordinates.

## What is and is not inferable

The source is explicitly `calculated_first_pass_not_camera_calibrated`. It says each string follows an SVG/draw.io label sequence `24..1`, but it does **not** give spar IDs, hub IDs, segment-to-spar correspondence, calibrated hub fiducials, or a structural transition list. A continuous ordered LED sequence alone cannot distinguish projected spar crossings or select a unique five-fold orientation/reflection.

The pipeline therefore normalises declared common-centre coordinates by metres-to-millimetres only. Rotation and reflection remain unresolved and are recorded as a provisional model convention, not fitted facts. It computes nearest-spar candidates and only emits XYZ for candidates within {MATCH_TOLERANCE_MM:g} mm that are separated from the next candidate by {AMBIGUITY_GAP_MM:g} mm and survive the shared-hub transition gate. All other records remain explicit unresolved records. Current generated result: {stats['matched_confidently']} confident spar LEDs, {stats['unresolved']} unresolved LEDs, and {stats['tail']} unresolved-model tail LEDs.

## Conflicts and required manual decisions

1. The claimed per-string on-dome length is 28 m while the 2D route is a generated SVG shape; neither provides a spar-level route. It cannot validate physical wiring against the 3D graph.
2. `grid_x/y` use screen-like grid coordinates while `x_mm/y_mm` are raw physical top-down coordinates. Use `x_mm/y_mm`; do not infer geometry from collision-nudged WLED cells.
3. A reflected or rotated projection cannot be selected without at least one (preferably several) measured hub/LED correspondences. Supply those fiducials and a measured spar sequence per string to resolve routes safely.
4. Tail XY overlap provides no 3D curve or order beyond string order. It is represented as `tail_model: unresolved` until measured vertical-line, Blender-curve, or control-point data is supplied.
''')


def run(args: argparse.Namespace) -> int:
    geometry = load_geometry(Path(args.geometry))
    summary, positions = load_positions(Path(args.positions))
    override = None
    if args.scale != 1000.0 or args.rotation_degrees != 0.0 or args.tx != 0.0 or args.ty != 0.0 or args.reflect_y:
        override = {"scale": args.scale, "rotation_degrees": args.rotation_degrees, "tx": args.tx, "ty": args.ty, "reflect_y": args.reflect_y}
    routes, output_document, rows, extra = infer(geometry, positions, summary, override)
    output_dir, routes_dir = Path(args.output_dir), Path(args.routes_dir)
    output_dir.mkdir(parents=True, exist_ok=True); routes_dir.mkdir(parents=True, exist_ok=True)
    (routes_dir / "inferred_routes.json").write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n")
    (output_dir / "led_positions_3d.json").write_text(json.dumps(output_document, indent=2, sort_keys=True) + "\n")
    (output_dir / "mapping_ambiguities.json").write_text(json.dumps(extra["document"], indent=2, sort_keys=True) + "\n")
    make_preview(output_dir / "mapping_preview.svg", geometry, rows, positions, {key: output_document["transform"][key] for key in ("scale", "rotation_degrees", "tx", "ty", "reflect_y")})
    write_analysis(Path(args.analysis), summary, geometry, positions, extra["stats"])
    print(json.dumps(extra["stats"], sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", default=str(DEFAULT_GEOMETRY)); parser.add_argument("--positions", default=str(DEFAULT_POSITIONS)); parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT)); parser.add_argument("--routes-dir", default=str(DEFAULT_ROUTES)); parser.add_argument("--analysis", default=str(PROJECT / "dome-mapping" / "ANALYSIS.md"))
    parser.add_argument("--scale", type=float, default=1000.0, help="metres-to-map-unit scale; use only from calibration")
    parser.add_argument("--rotation-degrees", type=float, default=0.0, help="calibrated rotation in degrees")
    parser.add_argument("--tx", type=float, default=0.0, help="calibrated X translation in map units")
    parser.add_argument("--ty", type=float, default=0.0, help="calibrated Y translation in map units")
    parser.add_argument("--reflect-y", action="store_true", help="apply a calibrated Y reflection; recorded explicitly")
    return run(parser.parse_args())

if __name__ == "__main__": raise SystemExit(main())
