"""Deterministic XYZ procedural spatial effects and shared frame blending."""
from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from ..config import LOGICAL_LED_COUNT
from ..frame import RGBFrame, validate_rgb
from .Common import SpatialContext, distance3, selected_xyz, smoothstep
from .effect_names import LEGACY_NAMES
from .space_body_catalogue import SPACE_BODIES

# Fireflies performs count * 5,000 distance checks each frame.
MAX_FIREFLIES = 100
# Enough to replace every logical LED once per second.
MAX_TWINKLE_SPAWN_RATE = LOGICAL_LED_COUNT

from .procedural_math import *  # compatibility re-export
from .procedural_math import _clamp, _noise, _ramp, _scale
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


# At most 1,600 templates retained across runs; keep reuse without frame clears.
@lru_cache(maxsize=16)
def particle_templates(count: int, seed: int) -> tuple[ParticleTemplate, ...]:
    if not 1 <= count <= MAX_FIREFLIES:
        raise ValueError(f"count must be in range 1..{MAX_FIREFLIES}, got {count!r}")
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
        if not 1 <= count <= MAX_FIREFLIES:
            raise ValueError(f"count must be in range 1..{MAX_FIREFLIES}, got {count!r}")
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
    if rotation_seconds <= 0 or thickness_mm <= 0:
        raise ValueError("rotation-seconds and thickness-mm must be positive")
    if trail_degrees < 0 or trail_degrees > MAX_ROTATING_PLANE_TRAIL_DEGREES:
        raise ValueError(f"trail-degrees={trail_degrees!r} must be in range 0..180")
    fg = parse_rgb(color)
    frame = _frame(parse_rgb(background), brightness)
    thickness_m = thickness_mm / 1000.0
    samples = build_rotating_plane_samples(
        axis=axis,
        elapsed=elapsed,
        rotation_seconds=rotation_seconds,
        trail_degrees=trail_degrees,
        direction=direction,
    )
    for index, point in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        level = plane_intensity_from_samples(point, context.center, samples, thickness_m)
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


@dataclass
class Twinkle:
    index: int
    born: float
    color: tuple[int, int, int]
    hue: float | None = None


class TwinkleOverlay:
    """Reusable deterministic per-LED twinkle lifecycle overlay."""

    def __init__(self, context: SpatialContext, *, seed=1, exclude_tail=False, density=.08, spawn_rate=12.0, fade_in=.25, hold=.25, fade_out=.7, minimum_brightness=0.05, maximum_brightness=1.0, color="FFFFFF", mode="fixed", background="000000", color_change_speed=0.0, **_):
        if not 0 <= density <= 1 or not 0 <= spawn_rate <= MAX_TWINKLE_SPAWN_RATE or min(fade_in, hold, fade_out) < 0:
            raise ValueError("twinkle density/rate/timing values are out of range")
        if not 0 <= minimum_brightness <= maximum_brightness <= 1:
            raise ValueError("twinkle brightness bounds must be 0..1 and ordered")
        if mode not in {"fixed", "random"}:
            raise ValueError("twinkle mode must be fixed or random")
        self.context = context
        self.exclude_tail = exclude_tail
        self.density = float(density)
        self.spawn_rate = float(spawn_rate)
        self.fade_in = float(fade_in)
        self.hold = float(hold)
        self.fade_out = float(fade_out)
        self.minimum = float(minimum_brightness)
        self.maximum = float(maximum_brightness)
        self.color = parse_rgb(color)
        self.mode = mode
        self.background = parse_rgb(background)
        self.color_change_speed = float(color_change_speed)
        self.random = random.Random(seed)
        self.last_elapsed = 0.0
        self.carry = 0.0
        self.active: dict[int, Twinkle] = {}
        self.indices = [index for index in range(LOGICAL_LED_COUNT) if not (exclude_tail and context.tails[index])]

    def _color(self, twinkle: Twinkle, elapsed: float) -> tuple[int, int, int]:
        if self.mode == "fixed":
            return twinkle.color
        hue = ((twinkle.hue or 0.0) + (elapsed - twinkle.born) * self.color_change_speed * 0.03) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    def _level(self, age: float) -> float | None:
        total = self.fade_in + self.hold + self.fade_out
        if age >= total:
            return None
        if self.fade_in > 0 and age < self.fade_in:
            phase = smoothstep(age / self.fade_in)
        elif age < self.fade_in + self.hold:
            phase = 1.0
        else:
            phase = 1.0 - smoothstep((age - self.fade_in - self.hold) / max(self.fade_out, 1e-9))
        return self.minimum + (self.maximum - self.minimum) * phase

    def _spawn(self, elapsed: float) -> None:
        if not self.indices:
            return
        capacity = int(len(self.indices) * self.density)
        if len(self.active) >= capacity:
            return
        self.carry += max(0.0, elapsed - self.last_elapsed) * self.spawn_rate
        count = min(capacity - len(self.active), int(self.carry))
        self.carry -= count
        for _ in range(count):
            for _attempt in range(8):
                index = self.random.choice(self.indices)
                if index not in self.active:
                    hue = self.random.random() if self.mode == "random" else None
                    self.active[index] = Twinkle(index, elapsed, self.color, hue)
                    break

    def apply(self, base: RGBFrame, elapsed: float, *, brightness=255, mode="replace") -> RGBFrame:
        frame = RGBFrame.allocate(base.led_count)
        frame.data[:] = base.data
        self._spawn(elapsed)
        for index, twinkle in list(self.active.items()):
            level = self._level(elapsed - twinkle.born)
            if level is None:
                del self.active[index]
                continue
            color = self._color(twinkle, elapsed)
            rgb = tuple(int(channel * level) for channel in color)
            if mode == "brighten":
                offset = index * 3
                rgb = tuple(max(rgb[channel], frame.data[offset + channel]) for channel in range(3))
            elif mode == "blend":
                offset = index * 3
                rgb = tuple(int(frame.data[offset + channel] * (1 - level) + rgb[channel] * level) for channel in range(3))
            frame.set_pixel(index, _scale((rgb[0], rgb[1], rgb[2]), brightness))
        self.last_elapsed = elapsed
        return frame



_SPACE_BODY_BAND_COUNT = 4


def render_space_body(context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, style="soft", palette=((255, 255, 255),), speed=0.3, coverage=1.0, **_) -> RGBFrame:
    if speed <= 0:
        raise ValueError(f"speed must be positive, got {speed!r}")
    zmin, zmax = context.z_bounds
    zspan = max(zmax - zmin, 1e-9)
    frame = _frame(brightness=brightness)
    for index, (x, y, z) in enumerate(context.xyz):
        if exclude_tail and context.tails[index]:
            continue
        height = (z - zmin) / zspan
        if style == "bands":
            wobble = 0.06 * (_noise(x * 1.4, y * 1.4, z, elapsed * speed, seed) - 0.5)
            triangle = abs(((height * _SPACE_BODY_BAND_COUNT + elapsed * speed * 0.15 + wobble) % 1.0) * 2 - 1)
            color, level = _ramp(palette, triangle), 1.0
        elif style == "mottled":
            n1 = _noise(x * 2.1, y * 2.1, z * 2.1, elapsed * speed * 0.5, seed)
            n2 = _noise(x * 4.3 + 5, y * 4.3, z * 4.3, elapsed * speed * 0.3, seed + 11)
            color, level = _ramp(palette, _clamp(0.5 * n1 + 0.5 * n2)), 1.0
        elif style == "sun":
            n1 = _noise(x * 2.0, y * 2.0, z * 2.0, elapsed * speed, seed)
            n2 = _noise(x * 5.0, y * 5.0, z * 5.0, elapsed * speed * 1.7, seed + 3)
            color, level = _ramp(palette, _clamp(0.4 + 0.45 * n1 + 0.15 * n2)), 1.0
        elif style == "belt":
            threshold = 1.0 - coverage
            n = _noise(x * 3.0, y * 3.0, z * 3.0, elapsed * speed, seed)
            if n <= threshold:
                continue
            above = (n - threshold) / max(coverage, 1e-9)
            color, level = _ramp(palette, above), _clamp(above)
        else:  # soft
            n = _noise(x, y, z, elapsed * speed, seed)
            color, level = _ramp(palette, _clamp(0.35 + 0.45 * n)), 1.0
        rgb = tuple(int(component * level) for component in color)
        frame.set_pixel(index, _scale(rgb, brightness))
    return frame


class ProceduralRenderer:
    """Stateful renderer wrapper that keeps reusable per-run objects alive."""

    def __init__(self, kind: str, context: SpatialContext, *, brightness=32, exclude_tail=False, seed=1, **options):
        self.kind = kind
        self.context = context
        self.brightness = brightness
        self.exclude_tail = exclude_tail
        self.seed = seed
        self.options = options
        self._particle_system = None
        self._twinkle_overlay = None
        if kind == "Fireflies":
            bounds = _selected_bounds(context, exclude_tail)
            self._particle_system = ParticleSystem(
                int(options.get("count", 25)),
                seed,
                bounds,
                color=options.get("color", "FFFFB0"),
                color_variation=float(options.get("color_variation", 0.25)),
            )
        if kind == "Twinkle":
            self._twinkle_overlay = TwinkleOverlay(context, seed=seed, exclude_tail=exclude_tail, **options)

    def render(self, elapsed: float) -> RGBFrame:
        if self.kind == "Twinkle":
            if self._twinkle_overlay is None:
                raise RuntimeError("twinkle overlay was not initialized")
            base = _frame(self._twinkle_overlay.background, brightness=self.brightness)
            return self._twinkle_overlay.apply(base, elapsed, brightness=self.brightness)
        if self.kind != "Fireflies":
            return render(self.kind, self.context, elapsed, brightness=self.brightness, exclude_tail=self.exclude_tail, seed=self.seed, **self.options)
        options = self.options
        system = self._particle_system
        if system is None:
            raise RuntimeError("fireflies particle system was not initialized")
        speed = float(options.get("speed", 0.35))
        glow_radius_mm = float(options.get("glow_radius_mm", 300.0))
        lifetime_seconds = float(options.get("lifetime_seconds", 8.0))
        if min(speed, glow_radius_mm, lifetime_seconds) <= 0:
            raise ValueError("speed, glow-radius-mm, and lifetime-seconds must be positive")
        radius = glow_radius_mm / 1000.0
        particles = system.particles(elapsed, speed=speed, lifetime_seconds=lifetime_seconds)
        accum = [[0.0, 0.0, 0.0] for _ in range(LOGICAL_LED_COUNT)]
        for particle in particles:
            for index, point in enumerate(self.context.xyz):
                if self.exclude_tail and self.context.tails[index]:
                    continue
                falloff = max(0.0, 1.0 - distance3(point, particle.position) / radius)
                glow = falloff * falloff * particle.brightness
                if glow <= 0:
                    continue
                for channel in range(3):
                    accum[index][channel] += particle.color[channel] * glow
        frame = _frame(brightness=self.brightness)
        for index, rgb in enumerate(accum):
            if any(rgb):
                frame.set_pixel(index, _scale(tuple(min(255, int(channel)) for channel in rgb), self.brightness))
        return frame


def create_renderer(kind: str, context: SpatialContext, *, brightness=32, exclude_tail=False, seed=1, **options) -> ProceduralRenderer:
    kind = LEGACY_NAMES.get(kind, kind)
    return ProceduralRenderer(kind, context, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)


def render(kind: str, context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, **options) -> RGBFrame:
    kind = LEGACY_NAMES.get(kind, kind)
    if kind in SPACE_BODIES:
        space_body = SPACE_BODIES[kind]
        return render_space_body(context, elapsed, brightness=brightness, exclude_tail=exclude_tail, seed=seed,
                             style=space_body.style, palette=space_body.palette, coverage=space_body.coverage,
                             speed=float(options.get("speed", space_body.speed)))
    renderers = {
        "Fire": render_fire,
        "RotatingPlane": render_rotating_plane,
        "Radar": render_radar,
        "Aurora": render_aurora,
        "Fireflies": render_fireflies,
        "Twinkle": lambda context, elapsed, **options: create_renderer("Twinkle", context, **options).render(elapsed),
    }
    if kind not in renderers:
        raise ValueError(f"unknown procedural effect {kind!r}")
    return renderers[kind](context, elapsed, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)
