"""Shared solar-system body preset type.

Each body lives in its own module (``Jupiter.py``, ``Mars.py`` …) declaring a
``SPACE_BODY = SpaceBody(...)``. The rendering engine (styles, colour ramp) is shared
in ``Procedural.render_space_body`` — the per-file data is the object's identity.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpaceBody:
    name: str
    label: str
    description: str
    style: str  # bands | mottled | sun | soft | belt
    palette: tuple[tuple[int, int, int], ...]
    speed: float = 0.3
    coverage: float = 1.0  # belt styles: lit fraction; ignored by full-cover styles
