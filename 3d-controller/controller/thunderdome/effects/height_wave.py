"""Horizontal height bands that move through selected physical Z bounds."""
from __future__ import annotations

from ..frame import RGBFrame, validate_rgb
from ..transport.ddp import scale_color
from ._common import SpatialContext, selected_xyz


def render_height_wave(
    context: SpatialContext,
    *,
    elapsed_seconds: float,
    speed_m_per_s: float,
    height_m: float,
    direction: str = "up",
    color: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
    brightness: int = 32,
    exclude_tail: bool = False,
) -> RGBFrame:
    """Render one full-thickness band moving up, down, or out-and-back in Z."""
    if speed_m_per_s <= 0:
        raise ValueError("speed_m_per_s must be greater than zero")
    if height_m <= 0:
        raise ValueError("height_m must be greater than zero")
    if direction not in {"up", "down", "bounce"}:
        raise ValueError(f"invalid direction {direction!r}")
    foreground = scale_color(validate_rgb(color), brightness)
    frame = RGBFrame.allocate(len(context.xyz), scale_color(validate_rgb(background), brightness))
    selected = selected_xyz(context, exclude_tail=exclude_tail)
    minimum_z = min(z for _, _, z in selected)
    maximum_z = max(z for _, _, z in selected)
    span = maximum_z - minimum_z
    if span <= 0:
        raise ValueError("selected Z bounds must have positive height")
    travelled = elapsed_seconds * speed_m_per_s
    if direction == "up":
        centre = minimum_z + travelled % span
    elif direction == "down":
        centre = maximum_z - travelled % span
    else:
        phase = travelled % (2 * span)
        centre = minimum_z + (phase if phase <= span else 2 * span - phase)
    half_width = height_m / 2
    for index, (_, _, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        if abs(z - centre) <= half_width:
            frame.set_pixel(index, foreground)
    return frame
