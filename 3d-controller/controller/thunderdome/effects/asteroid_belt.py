"""Asteroid belt: sparse drifting grey rocky debris on black."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="asteroid-belt",
    label="Asteroid belt",
    description="sparse drifting grey rocky debris",
    style="belt",
    palette=((28, 24, 20), (120, 108, 92), (176, 164, 148)),
    speed=0.12,
    coverage=0.22,
)
