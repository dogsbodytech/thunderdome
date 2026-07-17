"""Concentric XY-plane rings expanding outward from the apex."""
from __future__ import annotations

from ..frame import RGBFrame, validate_rgb
from ..transport.ddp import scale_color
from .common import SpatialContext


def render_expanding_rings(
    context: SpatialContext,
    *,
    elapsed_seconds: float,
    speed_m_per_s: float,
    ring_spacing_m: float,
    ring_width_m: float,
    color: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
    brightness: int = 32,
    exclude_tail: bool = False,
) -> RGBFrame:
    """Render periodic radial bands whose centres move away from ``context.center``.

    Width and spacing are in metres.  The modulo phase gives a seamless,
    bounded repeat while retaining an outward physical direction.
    """
    if speed_m_per_s <= 0:
        raise ValueError("speed_m_per_s must be greater than zero")
    if ring_spacing_m <= 0:
        raise ValueError("ring_spacing_m must be greater than zero")
    if not 0 < ring_width_m <= ring_spacing_m:
        raise ValueError("ring_width_m must be greater than zero and no larger than ring_spacing_m")
    foreground = scale_color(validate_rgb(color), brightness)
    frame = RGBFrame.allocate(len(context.xyz), scale_color(validate_rgb(background), brightness))
    half_width = ring_width_m / 2
    travelled = elapsed_seconds * speed_m_per_s
    for index, radius in enumerate(context.radius_xy):
        if exclude_tail and context.tails[index]:
            continue
        phase = (radius - travelled) % ring_spacing_m
        if min(phase, ring_spacing_m - phase) <= half_width:
            frame.set_pixel(index, foreground)
    return frame
