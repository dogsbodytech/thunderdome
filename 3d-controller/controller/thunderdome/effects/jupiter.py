"""Jupiter: banded cream, tan and rust gas giant."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="jupiter",
    label="Jupiter",
    description="banded cream, tan and rust gas giant",
    style="bands",
    palette=((230, 208, 170), (196, 150, 96), (150, 88, 52), (206, 120, 80)),
    speed=0.25,
)
