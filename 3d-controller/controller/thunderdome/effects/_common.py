"""Shared immutable spatial data and rendering math for dome effects."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, isfinite, sqrt
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from ..config import LOGICAL_LED_COUNT
from ..geometry import load_geometry
from ..led_positions import load_led_positions


@dataclass(frozen=True)
class SpatialContext:
    """Precomputed, index-aligned coordinates for a full logical LED frame."""

    positions: tuple[Mapping[str, object], ...]
    center: tuple[float, float, float]
    apex: tuple[float, float, float]
    xyz: tuple[tuple[float, float, float], ...]
    tails: tuple[bool, ...]
    radius_xy: tuple[float, ...]
    angle_xy: tuple[float, ...]
    z_bounds: tuple[float, float]

    @classmethod
    def from_rows(
        cls,
        positions: Sequence[Mapping[str, object]],
        *,
        center: tuple[float, float, float],
        apex: tuple[float, float, float] | None = None,
    ) -> "SpatialContext":
        """Build validated immutable effect inputs from ordered LED records."""
        rows = tuple(MappingProxyType(dict(row)) for row in positions)
        if len(rows) != LOGICAL_LED_COUNT:
            raise ValueError(f"expected {LOGICAL_LED_COUNT} positions")
        if [row.get("global_index") for row in rows] != list(range(LOGICAL_LED_COUNT)):
            raise ValueError("positions must be ordered by global_index 0..4999")
        try:
            xyz = tuple((float(row["x"]), float(row["y"]), float(row["z"])) for row in rows)
            origin = tuple(float(value) for value in center)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("positions and center must contain finite XYZ coordinates") from exc
        if len(origin) != 3:
            raise ValueError("center must be an XYZ tuple")
        if not all(isfinite(value) for point in (*xyz, origin) for value in point):
            raise ValueError("positions and center must contain finite XYZ coordinates")
        radii = tuple(sqrt((x - origin[0]) ** 2 + (y - origin[1]) ** 2) for x, y, _ in xyz)
        angles = tuple(atan2(y - origin[1], x - origin[0]) for x, y, _ in xyz)
        zs = tuple(z for _, _, z in xyz)
        return cls(
            positions=rows,
            center=origin,
            apex=origin if apex is None else tuple(float(value) for value in apex),
            xyz=xyz,
            tails=tuple(row.get("location_type") == "tail" for row in rows),
            radius_xy=radii,
            angle_xy=angles,
            z_bounds=(min(zs), max(zs)),
        )

    @classmethod
    def load(cls, positions_path: str | Path, geometry_path: str | Path) -> "SpatialContext":
        """Load positions and use authoritative apex hub H061 as the origin."""
        geometry = load_geometry(geometry_path)
        if "H061" not in geometry.hubs:
            raise ValueError("geometry is missing apex hub H061")
        apex = geometry.hubs["H061"]
        return cls.from_rows(load_led_positions(positions_path), center=apex.xyz, apex=apex.xyz)


def selected_xyz(context: SpatialContext, *, exclude_tail: bool) -> tuple[tuple[float, float, float], ...]:
    """Return physical coordinates participating in an effect invocation."""
    points = tuple(point for point, tail in zip(context.xyz, context.tails) if not (exclude_tail and tail))
    if not points:
        raise ValueError("selected position set is empty")
    return points


def parse_spatial_origin(value: str, context: SpatialContext) -> tuple[float, float, float]:
    """Resolve a shared shell origin selector without putting parsing in renderers."""
    normalized = value.strip().lower()
    if normalized == "apex":
        return context.apex
    dome_points = tuple(point for point, tail in zip(context.xyz, context.tails) if not tail)
    if normalized in {"centre", "base"}:
        if not dome_points:
            raise ValueError(f"invalid origin {value!r}: dome-only position set is empty")
        minimum_z = min(z for _, _, z in dome_points)
        if normalized == "base":
            return (context.apex[0], context.apex[1], minimum_z)
        return (context.apex[0], context.apex[1], (minimum_z + context.apex[2]) / 2)
    parts = value.split(",")
    if len(parts) != 3:
        raise ValueError(f"invalid origin {value!r}: expected apex, centre, base, or X,Y,Z")
    try:
        origin = tuple(float(part.strip()) for part in parts)
    except ValueError as exc:
        raise ValueError(f"invalid origin {value!r}: X,Y,Z must be numeric") from exc
    if not all(isfinite(component) for component in origin):
        raise ValueError(f"invalid origin {value!r}: X,Y,Z must be finite")
    return origin


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def distance3(a: Sequence[float], b: Sequence[float]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
