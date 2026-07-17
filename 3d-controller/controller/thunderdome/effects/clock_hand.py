"""Pure clock-hand spatial renderer for logical Thunderdome frames."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from ..config import LOGICAL_LED_COUNT
from ..frame import RGBFrame, validate_rgb
from ..transport.ddp import scale_color


PositionRow = Mapping[str, object]


def angle_for_elapsed(
    elapsed_seconds: float,
    *,
    rotation_seconds: float,
    direction: str = "clockwise",
    offset_degrees: float = 0.0,
) -> float:
    """Return the XY-plane hand angle measured from world +X.

    Positive angles are counterclockwise when viewed from above.  The default
    clockwise option therefore negates elapsed angular progress; the offset is
    always an alignment offset in that same world-coordinate convention.
    """
    if rotation_seconds <= 0:
        raise ValueError("rotation_seconds must be greater than zero")
    if direction not in {"clockwise", "counterclockwise"}:
        raise ValueError("direction must be clockwise or counterclockwise")
    progress = (elapsed_seconds / rotation_seconds) % 1.0
    direction_sign = -1.0 if direction == "clockwise" else 1.0
    return math.radians(offset_degrees) + direction_sign * progress * math.tau


def _centre_xy(rows: list[PositionRow]) -> tuple[float, float]:
    """Derive the represented dome centre from the non-tail XY extent."""
    dome_rows = [row for row in rows if row.get("location_type") != "tail"]
    if not dome_rows:
        raise ValueError("positions must contain non-tail LEDs")
    xs = [float(row["x"]) for row in dome_rows]
    ys = [float(row["y"]) for row in dome_rows]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def render_clock_hand(
    positions: Iterable[PositionRow],
    *,
    angle_radians: float,
    width_m: float,
    color: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
    brightness: int = 32,
    include_tail: bool = False,
) -> RGBFrame:
    """Render a radial XY half-ray into one 5,000-pixel RGB frame.

    ``width_m`` is the complete visible hand width in metres.  Tails are
    determined from the generated position metadata, not their Z coordinate.
    """
    if width_m <= 0:
        raise ValueError("width_m must be greater than zero")
    rows = list(positions)
    if len(rows) != LOGICAL_LED_COUNT:
        raise ValueError(f"clock-hand requires exactly {LOGICAL_LED_COUNT:,} positions")
    indexes = [row.get("global_index") for row in rows]
    if indexes != list(range(LOGICAL_LED_COUNT)):
        raise ValueError("positions must be ordered by global_index 0..4999")
    center_x, center_y = _centre_xy(rows)
    direction_x = math.cos(angle_radians)
    direction_y = math.sin(angle_radians)
    hand_color = scale_color(validate_rgb(color), brightness)
    background_color = scale_color(validate_rgb(background), brightness)
    frame = RGBFrame.allocate(LOGICAL_LED_COUNT, background_color)
    half_width_m = width_m / 2

    for row in rows:
        if row.get("location_type") == "tail" and not include_tail:
            continue
        dx = float(row["x"]) - center_x
        dy = float(row["y"]) - center_y
        forward_projection = dx * direction_x + dy * direction_y
        perpendicular_distance = abs(-direction_y * dx + direction_x * dy)
        if forward_projection >= 0 and perpendicular_distance <= half_width_m:
            frame.set_pixel(int(row["global_index"]), hand_color)
    return frame
