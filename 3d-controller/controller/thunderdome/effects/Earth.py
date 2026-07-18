"""Earth: blue oceans, green land, white cloud."""
from .SpaceBody import SpaceBody

SPACE_BODY = SpaceBody(
    name="Earth",
    label="Earth",
    description="blue oceans, green land, white cloud",
    style="mottled",
    palette=((16, 52, 140), (24, 96, 200), (34, 150, 70), (230, 240, 245)),
    speed=0.14,
)
