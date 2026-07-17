"""Deterministic XYZ procedural spatial effects and shared frame blending."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from ..config import LOGICAL_LED_COUNT
from ..frame import RGBFrame, validate_rgb
from .common import SpatialContext, distance3, selected_xyz, smoothstep

TAU = math.tau
Vector = tuple[float, float, float]


def finite_vector(value: str | Sequence[float], *, option: str = "vector", allow_named_axis: bool = False) -> Vector:
    """Parse and normalize a finite non-zero XYZ vector."""
    if isinstance(value, str):
        named = {"vertical": (0.0, 0.0, 1.0), "horizontal": (1.0, 0.0, 0.0), "tilted": (1.0, 1.0, 0.55)}
        if allow_named_axis and value in named:
            raw = named[value]
        else:
            parts = value.split(",")
            if len(parts) != 3:
                raise ValueError(f"{option} must be a finite non-zero X,Y,Z vector, got {value!r}")
            try:
                raw = tuple(float(part.strip()) for part in parts)
            except ValueError as exc:
                raise ValueError(f"{option} must contain numeric X,Y,Z values, got {value!r}") from exc
    else:
        raw = tuple(float(part) for part in value)
    if len(raw) != 3 or not all(math.isfinite(part) for part in raw):
        raise ValueError(f"{option} must be finite X,Y,Z, got {value!r}")
    length = math.sqrt(sum(part * part for part in raw))
    if length <= 0:
        raise ValueError(f"{option} must be non-zero, got {value!r}")
    return (raw[0] / length, raw[1] / length, raw[2] / length)


def parse_rgb(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, tuple):
        return validate_rgb(value)
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"color must be RRGGBB, got {value!r}")
    try:
        return validate_rgb(tuple(int(text[i : i + 2], 16) for i in (0, 2, 4)))
    except ValueError as exc:
        raise ValueError(f"color must be RRGGBB, got {value!r}") from exc


def _scale(rgb: tuple[int, int, int], brightness: int) -> tuple[int, int, int]:
    if not 0 <= brightness <= 255:
        raise ValueError(f"brightness must be in range 0..255, got {brightness!r}")
    return tuple(channel * brightness // 255 for channel in rgb)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def angular_delta(a: float, b: float) -> float:
    """Signed smallest angular delta, wrapping across -pi/+pi."""
    return (a - b + math.pi) % TAU - math.pi


def signed_plane_distance(point: Vector, centre: Vector, normal: Vector) -> float:
    return sum((point[i] - centre[i]) * normal[i] for i in range(3))


def _noise(x: float, y: float, z: float, t: float, seed: int) -> float:
    # Smooth deterministic value-like noise without calling random per LED.
    return 0.5 + 0.25 * math.sin(x * 1.73 + y * 2.17 + z * 1.31 + t + seed * 12.9898) + 0.25 * math.sin(
        x * 0.71 - y * 1.19 + z * 2.41 + t * 0.63 + seed * 3.17
    )


def palette_color(name: str, value: float) -> tuple[int, int, int]:
    palettes = {
        "fire": ((12, 0, 0), (180, 30, 0), (255, 180, 35)),
        "inferno": ((8, 0, 16), (180, 25, 70), (255, 245, 90)),
        "amber": ((12, 3, 0), (220, 92, 0), (255, 190, 32)),
        "green": ((0, 8, 0), (0, 180, 70), (180, 255, 210)),
        "blue": ((0, 0, 12), (20, 100, 220), (180, 240, 255)),
        "violet": ((8, 0, 18), (120, 30, 190), (230, 150, 255)),
        "mixed": ((0, 12, 20), (40, 210, 120), (210, 120, 255)),
    }
    if name not in palettes:
        raise ValueError(f"unknown palette {name!r}; valid choices: {', '.join(sorted(palettes))}")
    low, mid, high = palettes[name]
    value = _clamp(value)
    if value < 0.5:
        t = value * 2
        a, b = low, mid
    else:
        t = (value - 0.5) * 2
        a, b = mid, high
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def blend(a: RGBFrame, b: RGBFrame, t: float) -> RGBFrame:
    """Blend two logical frames into one frame using smoothstep."""
    if len(a.data) != len(b.data):
        raise ValueError("cannot blend frames of different lengths")
    factor = smoothstep(t)
    out = RGBFrame.allocate(a.led_count)
    out.data[:] = bytes(int(x * (1.0 - factor) + y * factor) for x, y in zip(a.data, b.data))
    return out


def _selected_bounds(context: SpatialContext, exclude_tail: bool) -> tuple[Vector, Vector]:
    points = selected_xyz(context, exclude_tail=exclude_tail)
    return tuple(min(p[i] for p in points) for i in range(3)), tuple(max(p[i] for p in points) for i in range(3))


@dataclass(frozen=True)
class ParticleTemplate:
    position: Vector
    velocity: Vector
    phase: float
    brightness_phase: float
    color_jitter: float


@dataclass(frozen=True)
class FireflyParticle:
    position: Vector
    brightness: float
    color: tuple[int, int, int]


@lru_cache(maxsize=128)
def particle_templates(count: int, seed: int) -> tuple[ParticleTemplate, ...]:
    if count <= 0:
        raise ValueError(f"count must be positive, got {count!r}")
    rng = random.Random(seed)
    templates = []
    for _ in range(count):
        direction = finite_vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)), option="particle velocity")
        speed = rng.uniform(0.3, 1.0)
        templates.append(
            ParticleTemplate(
                (rng.random(), rng.random(), rng.random()),
                tuple(component * speed for component in direction),
                rng.random(),
                rng.random() * TAU,
                rng.uniform(-1, 1),
            )
        )
    return tuple(templates)


class ParticleSystem:
    """Reusable deterministic 3D particle support for fireflies and later effects."""

    def __init__(self, count: int, seed: int, bounds: tuple[Vector, Vector], *, color=(255, 255, 180), color_variation=0.25):
        if count <= 0:
            raise ValueError(f"count must be positive, got {count!r}")
        self.count = count
        self.seed = seed
        self.bounds = bounds
        self.base_color = parse_rgb(color)
        self.color_variation = max(0.0, float(color_variation))
        self.templates = particle_templates(count, seed)

    def particles(self, elapsed: float, *, speed: float, lifetime_seconds: float) -> tuple[FireflyParticle, ...]:
        if speed <= 0:
            raise ValueError(f"speed must be positive, got {speed!r}")
        if lifetime_seconds <= 0:
            raise ValueError(f"lifetime_seconds must be positive, got {lifetime_seconds!r}")
        lo, hi = self.bounds
        spans = tuple(max(hi[i] - lo[i], 1e-9) for i in range(3))
        output = []
        for template in self.templates:
            position = tuple(
                lo[i] + ((template.position[i] + template.velocity[i] * elapsed * speed / spans[i]) % 1.0) * spans[i]
                for i in range(3)
            )
            phase = ((elapsed / lifetime_seconds) + template.phase) % 1.0
            fade = smoothstep(min(phase * 2, (1 - phase) * 2))
            pulse = 0.65 + 0.35 * math.sin(elapsed * 2.0 + template.brightness_phase)
            jitter = 1.0 + template.color_jitter * self.color_variation
            color = tuple(max(0, min(255, int(channel * jitter))) for channel in self.base_color)
            output.append(FireflyParticle(position, fade * pulse, color))
        return tuple(output)


def _frame(background: tuple[int, int, int] = (0, 0, 0), brightness: int = 32) -> RGBFrame:
    return RGBFrame.allocate(LOGICAL_LED_COUNT, _scale(background, brightness))


def render_fire(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, flame_height_m=2.5, turbulence=0.65, cooling=0.35, scale=1.0, palette="fire", speed=1.0, **_) -> RGBFrame:
    if min(flame_height_m, speed, scale) <= 0:
        raise ValueError("speed, flame-height-m, and scale must be positive")
    if turbulence < 0 or cooling < 0:
        raise ValueError("turbulence and cooling must be non-negative")
    lo, hi = _selected_bounds(context, exclude_tail)
    frame = _frame(brightness=brightness)
    for index, (x, y, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        height = (z - lo[2]) / flame_height_m
        n1 = _noise(x * scale, y * scale, z * scale, elapsed * speed, seed)
        n2 = _noise(x * scale * 2.3, y * scale * 1.7, z * 0.8, elapsed * speed * 1.7, seed + 17)
        heat = (1.0 - height) * (0.45 + turbulence * (0.55 * n1 + 0.35 * n2)) - cooling * max(height, 0.0)
        frame.set_pixel(index, _scale(palette_color(palette, heat), brightness))
    return frame


def render_aurora(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, direction="1,0,0", speed=0.25, scale=1.2, band_width=0.45, intensity=1.0, palette="mixed", **_) -> RGBFrame:
    if min(speed, scale, band_width, intensity) <= 0:
        raise ValueError("speed, scale, band-width, and intensity must be positive")
    flow = finite_vector(direction, option="direction")
    frame = _frame(brightness=brightness)
    for index, (x, y, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        q = (x * flow[0] + y * flow[1] + z * flow[2]) * scale + elapsed * speed
        n = _noise(x * 0.8, y * 0.8, z * 0.8, elapsed * 0.25, seed)
        wave1 = 0.5 + 0.5 * math.sin(q + n * TAU)
        wave2 = 0.5 + 0.5 * math.sin(q * 2.17 - elapsed * speed * 0.7 + n * math.pi)
        band = smoothstep(max(0.0, (wave1 * wave2 - (1 - band_width)) / max(band_width, 1e-9))) * intensity
        frame.set_pixel(index, _scale(palette_color(palette, band), brightness))
    return frame


def render_radar(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, color="00FF80", background="000000", rotation_seconds=8.0, beam_width_degrees=12.0, trail_degrees=35.0, range_m=9999.0, vertical_falloff=0.0, direction="clockwise", **_) -> RGBFrame:
    if min(rotation_seconds, beam_width_degrees, range_m) <= 0 or trail_degrees < 0 or vertical_falloff < 0:
        raise ValueError("radar dimensions must be positive and falloffs non-negative")
    sign = -1.0 if direction == "clockwise" else 1.0 if direction == "counterclockwise" else None
    if sign is None:
        raise ValueError(f"direction must be clockwise or counterclockwise, got {direction!r}")
    fg = parse_rgb(color)
    frame = _frame(parse_rgb(background), brightness)
    head = sign * elapsed * TAU / rotation_seconds
    width = math.radians(beam_width_degrees)
    trail = math.radians(trail_degrees)
    zmin, zmax = context.z_bounds
    zspan = max(zmax - zmin, 1e-9)
    for index, (x, y, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        dx, dy = x - context.center[0], y - context.center[1]
        radius = math.hypot(dx, dy)
        if radius > range_m:
            continue
        delta = angular_delta(math.atan2(dy, dx), head)
        behind = -delta if sign < 0 else delta
        if abs(delta) <= width / 2:
            level = 1 - abs(delta) / (width / 2)
        elif 0 < behind <= trail:
            level = (1 - behind / trail) * 0.45
        else:
            level = 0
        level *= 1 - vertical_falloff * ((z - zmin) / zspan)
        if level > 0:
            frame.set_pixel(index, _scale(tuple(int(channel * _clamp(level)) for channel in fg), brightness))
    return frame


def render_rotating_plane(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, axis="vertical", color="FFFFFF", background="000000", rotation_seconds=10.0, thickness_mm=220.0, trail_degrees=20.0, direction="clockwise", **_) -> RGBFrame:
    if rotation_seconds <= 0 or thickness_mm <= 0 or trail_degrees < 0:
        raise ValueError("rotation-seconds and thickness-mm must be positive; trail-degrees must be non-negative")
    axis_vector = finite_vector(axis, option="axis", allow_named_axis=True)
    sign = -1.0 if direction == "clockwise" else 1.0 if direction == "counterclockwise" else None
    if sign is None:
        raise ValueError(f"direction must be clockwise or counterclockwise, got {direction!r}")
    angle = sign * elapsed * TAU / rotation_seconds
    normal = finite_vector((math.cos(angle), math.sin(angle), axis_vector[2] * 0.6), option="plane normal")
    fg = parse_rgb(color)
    frame = _frame(parse_rgb(background), brightness)
    half = thickness_mm / 2000.0
    for index, point in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        dist = abs(signed_plane_distance(point, context.center, normal))
        level = 1 - smoothstep(dist / half) if dist <= half else 0
        if level > 0:
            frame.set_pixel(index, _scale(tuple(int(channel * level) for channel in fg), brightness))
    return frame


def render_fireflies(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, count=25, speed=0.35, glow_radius_mm=300.0, lifetime_seconds=8.0, color="FFFFB0", color_variation=0.25, **_) -> RGBFrame:
    if count <= 0 or min(speed, glow_radius_mm, lifetime_seconds) <= 0:
        raise ValueError("count, speed, glow-radius-mm, and lifetime-seconds must be positive")
    bounds = _selected_bounds(context, exclude_tail)
    particles = ParticleSystem(count, seed, bounds, color=color, color_variation=color_variation).particles(elapsed, speed=speed, lifetime_seconds=lifetime_seconds)
    radius = glow_radius_mm / 1000.0
    accum = [[0.0, 0.0, 0.0] for _ in range(LOGICAL_LED_COUNT)]
    for particle in particles:
        for index, point in enumerate(context.xyz):
            if exclude_tail and context.tails[index]:
                continue
            falloff = max(0.0, 1.0 - distance3(point, particle.position) / radius)
            glow = falloff * falloff * particle.brightness
            if glow <= 0:
                continue
            for channel in range(3):
                accum[index][channel] += particle.color[channel] * glow
    frame = _frame(brightness=brightness)
    for index, rgb in enumerate(accum):
        if any(rgb):
            frame.set_pixel(index, _scale(tuple(min(255, int(channel)) for channel in rgb), brightness))
    return frame


def render(kind: str, context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, **options) -> RGBFrame:
    renderers = {
        "fire": render_fire,
        "rotating-plane": render_rotating_plane,
        "radar": render_radar,
        "aurora": render_aurora,
        "fireflies": render_fireflies,
    }
    if kind not in renderers:
        raise ValueError(f"unknown procedural effect {kind!r}")
    return renderers[kind](context, elapsed, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)
