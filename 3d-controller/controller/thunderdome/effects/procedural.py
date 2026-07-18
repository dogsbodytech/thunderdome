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
from .common import SpatialContext, distance3, selected_xyz, smoothstep

TAU = math.tau
Vector = tuple[float, float, float]
MAX_ROTATING_PLANE_TRAIL_DEGREES = 180.0
MAX_ROTATING_PLANE_TRAIL_SAMPLES = 12


@dataclass(frozen=True)
class PlaneSample:
    normal: Vector
    weight: float


def finite_vector(value: str | Sequence[float], *, option: str = "vector", allow_named_axis: bool = False) -> Vector:
    """Parse and normalize a finite non-zero XYZ vector."""
    if isinstance(value, str):
        named = {"vertical": (0.0, 0.0, 1.0), "horizontal": (1.0, 0.0, 0.0), "tilted": (1.0, 1.0, 1.0)}
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


def dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def rotating_plane_initial_normal(axis: str | Sequence[float]) -> Vector:
    axis_vector = finite_vector(axis, option="axis", allow_named_axis=True)
    reference = (0.0, 0.0, 1.0)
    if abs(dot(axis_vector, reference)) > 0.9:
        reference = (1.0, 0.0, 0.0)
    return finite_vector(cross(axis_vector, reference), option="plane initial normal")


def rotate_vector(vector: Vector, axis: Vector, angle: float) -> Vector:
    """Rotate ``vector`` around normalized ``axis`` using Rodrigues' formula."""
    cosine = math.cos(angle)
    sine = math.sin(angle)
    axis_cross = cross(axis, vector)
    axis_dot = dot(axis, vector)
    return finite_vector(
        tuple(
            vector[i] * cosine + axis_cross[i] * sine + axis[i] * axis_dot * (1.0 - cosine)
            for i in range(3)
        ),
        option="rotated plane normal",
    )


def rotating_plane_normal(axis: str | Sequence[float], *, elapsed: float, rotation_seconds: float, direction: str) -> Vector:
    if rotation_seconds <= 0:
        raise ValueError("rotation-seconds must be greater than zero")
    sign = -1.0 if direction == "clockwise" else 1.0 if direction == "counterclockwise" else None
    if sign is None:
        raise ValueError(f"direction must be clockwise or counterclockwise, got {direction!r}")
    axis_vector = finite_vector(axis, option="axis", allow_named_axis=True)
    angle = sign * elapsed * TAU / rotation_seconds
    return rotate_vector(rotating_plane_initial_normal(axis_vector), axis_vector, angle)


def _plane_level(point: Vector, centre: Vector, normal: Vector, thickness_m: float) -> float:
    half = thickness_m / 2.0
    if half <= 0:
        raise ValueError("thickness must be greater than zero")
    dist = abs(signed_plane_distance(point, centre, normal))
    return 1.0 - smoothstep(dist / half) if dist <= half else 0.0


def rotating_plane_intensity(
    point: Vector,
    centre: Vector,
    *,
    axis: str | Sequence[float],
    elapsed: float,
    rotation_seconds: float,
    thickness_m: float,
    trail_degrees: float,
    direction: str,
) -> float:
    samples = build_rotating_plane_samples(
        axis=axis,
        elapsed=elapsed,
        rotation_seconds=rotation_seconds,
        trail_degrees=trail_degrees,
        direction=direction,
    )
    return plane_intensity_from_samples(point, centre, samples, thickness_m)


def build_rotating_plane_samples(
    *,
    axis: str | Sequence[float],
    elapsed: float,
    rotation_seconds: float,
    trail_degrees: float,
    direction: str,
) -> tuple[PlaneSample, ...]:
    """Build current and trailing plane normals once for a rotating-plane frame."""
    if rotation_seconds <= 0:
        raise ValueError("rotation-seconds must be greater than zero")
    if trail_degrees < 0 or trail_degrees > MAX_ROTATING_PLANE_TRAIL_DEGREES:
        raise ValueError(f"trail-degrees={trail_degrees!r} must be in range 0..180")
    axis_vector = finite_vector(axis, option="axis", allow_named_axis=True)
    sign = -1.0 if direction == "clockwise" else 1.0 if direction == "counterclockwise" else None
    if sign is None:
        raise ValueError(f"direction must be clockwise or counterclockwise, got {direction!r}")
    current_angle = sign * elapsed * TAU / rotation_seconds
    initial = rotating_plane_initial_normal(axis_vector)
    samples = [PlaneSample(rotate_vector(initial, axis_vector, current_angle), 1.0)]
    if trail_degrees <= 0:
        return tuple(samples)
    trail_angle = math.radians(trail_degrees)
    sample_count = max(2, min(MAX_ROTATING_PLANE_TRAIL_SAMPLES, int(math.ceil(trail_degrees / 10))))
    for sample in range(1, sample_count + 1):
        fraction = sample / sample_count
        previous_angle = current_angle - sign * trail_angle * fraction
        normal = rotate_vector(initial, axis_vector, previous_angle)
        samples.append(PlaneSample(normal, smoothstep(1.0 - fraction) * 0.7))
    return tuple(samples)


def plane_intensity_from_samples(point: Vector, centre: Vector, samples: Sequence[PlaneSample], thickness_m: float) -> float:
    level = 0.0
    for sample in samples:
        plane_level = _plane_level(point, centre, sample.normal, thickness_m)
        if plane_level > 0:
            level = max(level, plane_level * sample.weight)
    return _clamp(level)


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
        if not 0 <= density <= 1 or spawn_rate < 0 or min(fade_in, hold, fade_out) < 0:
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
        if kind == "fireflies":
            bounds = _selected_bounds(context, exclude_tail)
            self._particle_system = ParticleSystem(
                int(options.get("count", 25)),
                seed,
                bounds,
                color=options.get("color", "FFFFB0"),
                color_variation=float(options.get("color_variation", 0.25)),
            )
        if kind == "twinkle":
            self._twinkle_overlay = TwinkleOverlay(context, seed=seed, exclude_tail=exclude_tail, **options)

    def render(self, elapsed: float) -> RGBFrame:
        if self.kind == "twinkle":
            if self._twinkle_overlay is None:
                raise RuntimeError("twinkle overlay was not initialized")
            base = _frame(self._twinkle_overlay.background, brightness=self.brightness)
            return self._twinkle_overlay.apply(base, elapsed, brightness=self.brightness)
        if self.kind != "fireflies":
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
    return ProceduralRenderer(kind, context, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)


def render(kind: str, context: SpatialContext, elapsed: float, *, brightness=32, exclude_tail=False, seed=1, **options) -> RGBFrame:
    renderers = {
        "fire": render_fire,
        "rotating-plane": render_rotating_plane,
        "radar": render_radar,
        "aurora": render_aurora,
        "fireflies": render_fireflies,
        "twinkle": lambda context, elapsed, **options: create_renderer("twinkle", context, **options).render(elapsed),
    }
    if kind not in renderers:
        raise ValueError(f"unknown procedural effect {kind!r}")
    return renderers[kind](context, elapsed, brightness=brightness, exclude_tail=exclude_tail, seed=seed, **options)
