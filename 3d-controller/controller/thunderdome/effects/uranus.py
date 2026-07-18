"""Uranus: featureless pale cyan ice giant."""
from ._space_body import SpaceBody

SPACE_BODY = SpaceBody(
    name="uranus",
    label="Uranus",
    description="featureless pale cyan ice giant",
    style="soft",
    palette=((150, 224, 224), (196, 240, 236)),
    speed=0.12,
)
