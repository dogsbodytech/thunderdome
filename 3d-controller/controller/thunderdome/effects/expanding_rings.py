"""True XYZ spherical shells expanding outward from a selected origin."""
from __future__ import annotations

from ..frame import RGBFrame, validate_rgb
from ..transport.ddp import scale_color
from ._common import SpatialContext, distance3, selected_xyz


def render_expanding_rings(
    context: SpatialContext,
    *,
    elapsed_seconds: float,
    speed_m_per_s: float,
    thickness_m: float,
    origin: tuple[float, float, float] | None = None,
    color: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
    brightness: int = 32,
    exclude_tail: bool = False,
) -> RGBFrame:
    """Render one expanding spherical shell using true Euclidean XYZ distance.

    The shell radius advances with elapsed time and wraps after it reaches the
    maximum selected LED distance from the selected origin. ``thickness_m`` is
    the full shell thickness.
    """
    if speed_m_per_s <= 0:
        raise ValueError("speed_m_per_s must be greater than zero")
    if thickness_m <= 0:
        raise ValueError("thickness_m must be greater than zero")
    foreground = scale_color(validate_rgb(color), brightness)
    frame = RGBFrame.allocate(len(context.xyz), scale_color(validate_rgb(background), brightness))
    selected_origin = context.center if origin is None else origin
    selected = selected_xyz(context, exclude_tail=exclude_tail)
    maximum_distance = max(distance3(point, selected_origin) for point in selected)
    if maximum_distance <= 0:
        raise ValueError("maximum shell distance must be greater than zero")
    radius = (elapsed_seconds * speed_m_per_s) % maximum_distance
    half_width = thickness_m / 2
    for index, point in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        if abs(distance3(point, selected_origin) - radius) <= half_width:
            frame.set_pixel(index, foreground)
    return frame
