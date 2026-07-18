"""Mars: rusty red dust world."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="mars",
    label="Mars",
    description="rusty red dust world",
    style="mottled",
    palette=((80, 20, 10), (170, 58, 24), (210, 96, 48)),
    speed=0.1,
)
