"""Kuiper belt: cold, sparse icy blue-white debris on black."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="kuiper-belt",
    label="Kuiper belt",
    description="cold sparse icy blue-white debris",
    style="belt",
    palette=((14, 22, 34), (70, 104, 140), (168, 200, 224)),
    speed=0.07,
    coverage=0.14,
)
