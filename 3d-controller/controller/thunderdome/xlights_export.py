"""Export canonical Thunderdome geometry and routes as xLights layout models."""
from __future__ import annotations

import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .geometry import DomeGeometry
from .led_positions import generate_positions
from .routes import RouteDefinition


def dome_to_xlights(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert Z-up dome metres to Y-up xLights units."""
    return x * 100.0, z * 100.0, y * 100.0


def _format_points(points: list[tuple[float, float, float]]) -> str:
    return ",".join(repr(value) for point in points for value in point)


def _model(route: RouteDefinition, geometry: DomeGeometry, rows: list[dict]) -> ET.Element:
    route_rows = [row for row in rows if row["string_id"] == route.string_id]
    spar_rows = [row for row in route_rows if row["location_type"] == "spar"]
    counts = [sum(row["spar_id"] == segment.spar_id for row in spar_rows) for segment in route.segments]
    tail_rows = [row for row in route_rows if row["location_type"] == "tail"]
    counts.append(len(tail_rows))
    if len(route_rows) != 1000 or len(counts) != 25 or sum(counts) != 1000:
        raise ValueError(f"string {route.string_id}: generated positions do not form a 1,000-node polyline")
    points = [dome_to_xlights(*geometry.hubs[hub].xyz) for hub in route.hubs]
    last = route_rows[-1]
    points.append(dome_to_xlights(last["x"], last["y"], last["z"]))
    return ET.Element("model", {
        "name": f"Thunderdome String {route.controller_number}",
        "DisplayAs": "Poly Line", "LayoutGroup": "Default", "PolyStrings": "1",
        "NodesPerString": "1000", "LightsPerNode": "1", "NumPoints": str(len(points)),
        "StartChannel": str(route.global_index_start * 3 + 1),
        "PointData": _format_points(points), "SegmentCounts": ",".join(map(str, counts)),
    })


def _ensure_child(root: ET.Element, tag: str) -> ET.Element:
    child = root.find(tag)
    return child if child is not None else ET.SubElement(root, tag)


def _load_or_create(path: Path) -> ET.ElementTree:
    if not path.exists():
        return ET.ElementTree(ET.Element("xrgb"))
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        return ET.parse(path, parser=parser)
    except ET.ParseError as exc:
        raise ValueError(f"cannot update malformed xLights XML: {path}: {exc}") from exc


def export_xlights(output: str | Path, geometry: DomeGeometry, routes: list[RouteDefinition]) -> None:
    """Create/update the generated models atomically, preserving unrelated XML."""
    output = Path(output)
    tree = _load_or_create(output)
    root = tree.getroot()
    rows = generate_positions(routes, geometry)["leds"]
    models = _ensure_child(root, "models")
    groups = _ensure_child(root, "modelGroups")
    generated_names = {f"Thunderdome String {route.controller_number}" for route in routes}
    for model in list(models):
        if model.get("name") in generated_names:
            models.remove(model)
    for group in list(groups):
        if group.get("name") == "Thunderdome":
            groups.remove(group)
    for route in sorted(routes, key=lambda item: item.controller_number):
        models.append(_model(route, geometry, rows))
    ET.SubElement(groups, "modelGroup", {"name": "Thunderdome", "models": ",".join(sorted(generated_names)), "LayoutGroup": "Default"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=output.parent, prefix=f".{output.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        tree.write(handle, encoding="utf-8", xml_declaration=True)
    try:
        if output.exists():
            shutil.copy2(output, Path(str(output) + ".thunderdome.bak"))
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
