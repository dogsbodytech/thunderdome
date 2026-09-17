"""Single authoritative catalogue of space-body effect presets."""
from . import AsteroidBelt, Earth, Jupiter, KuiperBelt, Mars, Mercury, Neptune, Saturn, Sol, Uranus, Venus, Voyager1
from .SpaceBody import SpaceBody

_SPACE_BODY_MODULES = (AsteroidBelt, Jupiter, Saturn, Uranus, Neptune, KuiperBelt, Voyager1, Sol, Mercury, Venus, Earth, Mars)
SPACE_BODIES: dict[str, SpaceBody] = {module.SPACE_BODY.name: module.SPACE_BODY for module in _SPACE_BODY_MODULES}
