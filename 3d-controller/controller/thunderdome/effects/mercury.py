"""Mercury: scorched grey cratered rock."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="mercury",
    label="Mercury",
    description="scorched grey cratered rock",
    style="mottled",
    palette=((40, 36, 32), (120, 112, 100), (176, 150, 120)),
    speed=0.1,
)
