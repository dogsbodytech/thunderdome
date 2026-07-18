"""Voyager 1: near-black with a lonely faint gold glint in the dark."""
from .SpaceBody import SpaceBody

SPACE_BODY = SpaceBody(
    name="Voyager1",
    label="Voyager 1",
    description="lonely faint gold glint in the dark",
    style="belt",
    palette=((10, 10, 14), (120, 96, 40), (220, 200, 140)),
    speed=0.05,
    coverage=0.05,
)
