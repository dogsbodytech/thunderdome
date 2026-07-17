"""Shared immutable spatial data and rendering math for dome effects."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, sqrt
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
        if not all(value == value and abs(value) != float("inf") for point in (*xyz, origin) for value in point):
            raise ValueError("positions and center must contain finite XYZ coordinates")
        radii = tuple(sqrt((x - origin[0]) ** 2 + (y - origin[1]) ** 2) for x, y, _ in xyz)
        angles = tuple(atan2(y - origin[1], x - origin[0]) for x, y, _ in xyz)
        zs = tuple(z for _, _, z in xyz)
        return cls(
            positions=rows,
            center=origin,
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
        return cls.from_rows(load_led_positions(positions_path), center=apex.xyz)


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def distance3(a: Sequence[float], b: Sequence[float]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
