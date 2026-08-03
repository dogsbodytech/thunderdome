"""xLights model export for the Thunderdome geodesic dome.

Generates 5 PolyLine models (one per string/controller) and a Thunderdome
model group, then writes or updates xlights_rgbeffects.xml in the show folder.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

from .geometry import DomeGeometry
from .routes import RouteDefinition

PITCH = 0.03
EPS = 1e-9

# 1000 LEDs × 3 channels (RGB) per string
_CHANNELS_PER_STRING = 1000 * 3
# controller_number -> absolute StartChannel (1-indexed)
_START_CHANNELS = {n: 1 + (n - 1) * _CHANNELS_PER_STRING for n in range(1, 6)}


def dome_to_xlights(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert dome XYZ (Z-up, metres) to xLights XYZ (Y-up, 100 units/m).

    Dome axes:  X=east/west,  Y=north/south,  Z=vertical
    xLights:    X=east/west,  Y=vertical,      Z=north/south (depth)
    Scale:      1 m  →  100 xLights units
    """
    return (x * 100.0, z * 100.0, y * 100.0)


def segment_led_counts(segments: list, route_length_m: float) -> list[int]:
    """Return per-segment LED counts using the same walking algorithm as led_positions.py.

    Returns a list of length len(segments) whose sum equals the number of spar
    LEDs (n_spar).  n_tail = 1000 - n_spar gives the tail LED count.
    """
    seg_lengths = [seg.length_m for seg in segments]
    counts = [0] * len(segments)
    for i in range(1000):
        d = i * PITCH
        if d > route_length_m + EPS:
            break  # remaining LEDs are tail LEDs
        remaining = d
        for k, length in enumerate(seg_lengths):
            if remaining <= length + EPS:
                counts[k] += 1
                break
            remaining -= length
    return counts


def generate_polyline_model(
    route: RouteDefinition,
    geometry: DomeGeometry,
    start_channel: int,
) -> ET.Element:
    """Build an xLights 'Poly Line' model Element for one string.

    Waypoints: 25 ordered hub positions + 1 tail point (1 xLights unit below apex).
    Segments:  24 spar segments + 1 near-invisible tail segment.
    """
    model_name = f"Thunderdome String {route.controller_number}"

    # 25 hub waypoints (ordered along the route)
    waypoints = [dome_to_xlights(*geometry.hubs[h].xyz) for h in route.hubs]

    # Extra tail waypoint: 0.01 m (= 1 xLights unit) below apex in dome Z
    apex = geometry.hubs["H061"]
    tail_pt = dome_to_xlights(apex.x, apex.y, apex.z - 0.01)
    waypoints.append(tail_pt)  # now 26 waypoints, 25 segments

    num_points = len(waypoints)  # 26

    # Per-segment LED counts for the 24 spar segments
    spar_counts = segment_led_counts(route.segments, route.total_length_m)
    n_tail = 1000 - sum(spar_counts)

    # 25 segment counts: 24 spar + 1 tail
    all_seg_counts = list(spar_counts) + [n_tail]

    # PointData: flat comma-separated x,y,z for every waypoint
    point_data = ",".join(f"{v:.6f}" for pt in waypoints for v in pt)

    attrs: dict[str, str] = {
        "name": model_name,
        "DisplayAs": "Poly Line",
        "LayoutGroup": "Default",
        "PolyStrings": "1",
        "NodesPerString": "1000",
        "LightsPerNode": "1",
        "NumPoints": str(num_points),
        "WorldPosX": "0.000000",
        "WorldPosY": "0.000000",
        "WorldPosZ": "0.000000",
        "ScaleX": "1.000000",
        "ScaleY": "1.000000",
        "ScaleZ": "1.000000",
        "RotateX": "0.000000",
        "RotateY": "0.000000",
        "RotateZ": "0.000000",
        "StartChannel": str(start_channel),
        "PixelSize": "2",
        "Transparency": "0",
        "BlackTransparency": "0",
        "Antialias": "1",
        "PointData": point_data,
    }

    # Seg1..Seg25 and Corner1..Corner25 (1-indexed)
    for i, count in enumerate(all_seg_counts, 1):
        attrs[f"Seg{i}"] = str(count)
        attrs[f"Corner{i}"] = "Neither"

    return ET.Element("model", attrs)


def generate_model_group(model_names: list[str]) -> ET.Element:
    """Build an xLights modelGroup Element wrapping all string models."""
    return ET.Element("modelGroup", {
        "name": "Thunderdome",
        "models": ",".join(model_names),
        "layout": "minimalGrid",
        "GridSize": "400",
        "selected": "0",
        "LayoutGroup": "Default",
    })


_TEMPLATE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<xrgb>\n"
    '  <models type="rgb_effects">\n'
    "  </models>\n"
    '  <modelGroups type="rgb_effects">\n'
    "  </modelGroups>\n"
    "</xrgb>\n"
)


def update_xlights_rgbeffects(
    output_path: str | Path,
    geometry: DomeGeometry,
    routes: list[RouteDefinition],
) -> None:
    """Write or update xlights_rgbeffects.xml with 5 PolyLine models + Thunderdome group.

    If the file already exists it is parsed and the Thunderdome models/group are
    replaced in-place; any other models already in the file are preserved.
    """
    output_path = Path(output_path)

    # Prefer reading the existing file; fall back to the .xbkp xLights backup
    # (which carries the full settings/perspectives structure), then our minimal
    # template as a last resort.
    xbkp_path = output_path.with_suffix(".xbkp")
    if output_path.exists():
        tree = ET.parse(output_path)
        root = tree.getroot()
    elif xbkp_path.exists():
        tree = ET.parse(xbkp_path)
        root = tree.getroot()
    else:
        root = ET.fromstring(_TEMPLATE_XML.encode())

    # Locate or create the <models> and <modelGroups> container elements
    models_elem = root.find("models")
    if models_elem is None:
        models_elem = ET.SubElement(root, "models", {"type": "rgb_effects"})

    groups_elem = root.find("modelGroups")
    if groups_elem is None:
        groups_elem = ET.SubElement(root, "modelGroups", {"type": "rgb_effects"})

    # Remove any existing Thunderdome entries so we can replace them cleanly
    for child in list(models_elem):
        if child.get("name", "").startswith("Thunderdome String "):
            models_elem.remove(child)
    for child in list(groups_elem):
        if child.get("name") == "Thunderdome":
            groups_elem.remove(child)

    # Generate and insert new model elements (sorted by controller_number)
    sorted_routes = sorted(routes, key=lambda r: r.controller_number)
    model_names: list[str] = []
    for route in sorted_routes:
        start_ch = _START_CHANNELS[route.controller_number]
        model_elem = generate_polyline_model(route, geometry, start_ch)
        models_elem.append(model_elem)
        model_names.append(model_elem.get("name", ""))

    # Insert model group
    groups_elem.append(generate_model_group(model_names))

    # Serialise with readable indentation via minidom
    rough = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(rough)
    pretty = dom.toprettyxml(indent="  ")
    # Strip blank lines and the extra XML declaration minidom inserts
    lines = [ln for ln in pretty.splitlines() if ln.strip()]
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines) + "\n"
    )
