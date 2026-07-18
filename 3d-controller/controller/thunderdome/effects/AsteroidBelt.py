"""Asteroid belt: sparse drifting grey rocky debris on black."""
from .SpaceBody import SpaceBody

SPACE_BODY = SpaceBody(
    name="AsteroidBelt",
    label="Asteroid belt",
    description="sparse drifting grey rocky debris",
    style="belt",
    palette=((28, 24, 20), (120, 108, 92), (176, 164, 148)),
    speed=0.12,
    coverage=0.22,
)
