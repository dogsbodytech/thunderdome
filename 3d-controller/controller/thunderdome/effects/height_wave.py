"""Horizontal height bands that travel upward through the dome."""
from __future__ import annotations

from ..frame import RGBFrame, validate_rgb
from ..transport.ddp import scale_color
from .common import SpatialContext


def render_height_wave(
    context: SpatialContext,
    *,
    elapsed_seconds: float,
    speed_m_per_s: float,
    wave_spacing_m: float,
    wave_width_m: float,
    color: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
    brightness: int = 32,
    exclude_tail: bool = False,
) -> RGBFrame:
    """Render periodic horizontal bands whose centres move toward increasing Z.

    Width and spacing are in metres.  The band repeats at the configured
    spacing, making the output continuous as it crosses the physical bounds.
    """
    if speed_m_per_s <= 0:
        raise ValueError("speed_m_per_s must be greater than zero")
    if wave_spacing_m <= 0:
        raise ValueError("wave_spacing_m must be greater than zero")
    if not 0 < wave_width_m <= wave_spacing_m:
        raise ValueError("wave_width_m must be greater than zero and no larger than wave_spacing_m")
    foreground = scale_color(validate_rgb(color), brightness)
    frame = RGBFrame.allocate(len(context.xyz), scale_color(validate_rgb(background), brightness))
    half_width = wave_width_m / 2
    travelled = elapsed_seconds * speed_m_per_s
    for index, (_, _, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        phase = (z - travelled) % wave_spacing_m
        if min(phase, wave_spacing_m - phase) <= half_width:
            frame.set_pixel(index, foreground)
    return frame
