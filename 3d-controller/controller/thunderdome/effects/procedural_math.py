"""Shared deterministic mathematics, palettes, and plane helpers."""
from __future__ import annotations
import colorsys
import math
from dataclasses import dataclass
from typing import Sequence
from ..frame import RGBFrame, validate_rgb
from .Common import smoothstep

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


def _ramp(stops: Sequence[tuple[int, int, int]], value: float) -> tuple[int, int, int]:
    """Piecewise-linear colour ramp across an arbitrary list of RGB stops."""
    value = _clamp(value)
    if len(stops) == 1:
        return stops[0]
    scaled = value * (len(stops) - 1)
    index = min(int(scaled), len(stops) - 2)
    fraction = scaled - index
    low, high = stops[index], stops[index + 1]
    return tuple(int(low[c] + (high[c] - low[c]) * fraction) for c in range(3))


def blend(a: RGBFrame, b: RGBFrame, t: float) -> RGBFrame:
    """Blend two logical frames into one frame using smoothstep."""
    if len(a.data) != len(b.data):
        raise ValueError("cannot blend frames of different lengths")
    factor = smoothstep(t)
    out = RGBFrame.allocate(a.led_count)
    out.data[:] = bytes(int(x * (1.0 - factor) + y * factor) for x, y in zip(a.data, b.data))
    return out


