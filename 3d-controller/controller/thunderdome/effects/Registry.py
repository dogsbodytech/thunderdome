"""Authoritative effect catalogue for CLI and automatic showcase mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .Common import SpatialContext
from .Procedural import SPACE_BODIES, create_renderer


@dataclass(frozen=True)
class EffectRegistration:
    name: str
    description: str
    auto_options: Mapping[str, object]
    category: str
    supports_auto: bool = True

    def create_renderer(self, context: SpatialContext, *, brightness: int = 255, exclude_tail: bool = False, seed: int = 1, **overrides):
        options = dict(self.auto_options)
        options.update(overrides)
        if self.category == "procedural":
            return create_renderer(self.name, context, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)
        raise ValueError(f"registry renderer factory for {self.name!r} is provided by the CLI adapter")


REGISTRY = (
    EffectRegistration("ClockHand", "rotating radial XY hand", {"rotation_seconds": 12, "width_mm": 300}, "clock"),
    EffectRegistration("ExpandingRings", "true XYZ spherical shell", {"origin": "centre", "speed_mps": 1.0, "thickness_mm": 250}, "spatial"),
    EffectRegistration("HeightWave", "moving horizontal Z band", {"direction": "bounce", "speed_mps": 0.8, "height_mm": 300}, "spatial"),
    EffectRegistration("Fire", "rising turbulent flame field", {"speed": 1.0, "flame_height_m": 2.5, "turbulence": 0.65, "cooling": 0.35, "scale": 1.0, "palette": "fire"}, "procedural"),
    EffectRegistration("RotatingPlane", "soft signed-distance rotating plane", {"axis": "tilted", "rotation_seconds": 10, "thickness_mm": 220, "trail_degrees": 20, "direction": "clockwise"}, "procedural"),
    EffectRegistration("Radar", "angular XY sweep", {"rotation_seconds": 8, "beam_width_degrees": 12, "trail_degrees": 35, "direction": "clockwise"}, "procedural"),
    EffectRegistration("Aurora", "flowing multi-frequency luminous bands", {"speed": 0.25, "scale": 1.2, "band_width": 0.45, "intensity": 1.0, "palette": "mixed", "direction": "1,0,0"}, "procedural"),
    EffectRegistration("Fireflies", "deterministic moving 3D glow particles", {"count": 25, "speed": 0.35, "glow_radius_mm": 300, "lifetime_seconds": 8, "color": "FFFFB0", "color_variation": 0.25}, "procedural"),
    EffectRegistration("Twinkle", "stateful per-LED fade-in hold fade-out sparkles", {"density": 0.08, "spawn_rate": 12.0, "fade_in": 0.25, "hold": 0.25, "fade_out": 0.7, "minimum_brightness": 0.05, "maximum_brightness": 1.0, "color": "FFFFFF", "mode": "fixed", "background": "000000", "color_change_speed": 0.0}, "procedural"),
    *(EffectRegistration(name, space_body.description, {"speed": space_body.speed}, "procedural") for name, space_body in SPACE_BODIES.items()),
)

BY_NAME = {registration.name: registration for registration in REGISTRY}
LEGACY_NAMES = {"clock-hand": "ClockHand", "expanding-rings": "ExpandingRings", "height-wave": "HeightWave", "fire": "Fire", "rotating-plane": "RotatingPlane", "radar": "Radar", "aurora": "Aurora", "fireflies": "Fireflies", "twinkle": "Twinkle", "auto": "Auto"}
DEFAULT_PLAYLIST = tuple(registration.name for registration in REGISTRY if registration.supports_auto)
PRESETS = {
    "calm": ("HeightWave", "Aurora", "Fireflies", "ExpandingRings"),
    "energetic": ("ClockHand", "Fire", "RotatingPlane", "Radar", "Aurora", "Fireflies"),
    "solar-system": tuple(SPACE_BODIES),
}


def get(name: str) -> EffectRegistration:
    name = LEGACY_NAMES.get(name, name)
    if name not in BY_NAME:
        raise ValueError(f"unknown effect {name!r}; valid choices: {', '.join(BY_NAME)}")
    return BY_NAME[name]
