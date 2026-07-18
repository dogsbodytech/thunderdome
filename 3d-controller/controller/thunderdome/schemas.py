"""Authoritative, source-neutral effect parameter schemas for control surfaces."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from .effects.registry import BY_NAME, DEFAULT_PLAYLIST


@dataclass(frozen=True)
class ParameterSchema:
    name: str
    type: str
    default: object
    description: str
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    units: str | None = None
    choices: tuple[str, ...] = ()
    required: bool = False
    classification: str = "effect"

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "description": self.description,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "units": self.units,
            "choices": list(self.choices),
            "required": self.required,
            "classification": self.classification,
        }


@dataclass(frozen=True)
class EffectSchema:
    name: str
    label: str
    description: str
    parameters: Mapping[str, ParameterSchema]

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "label": self.label, "description": self.description, "parameters": [item.as_dict() for item in self.parameters.values()]}


def _parameter(name: str, type: str, default: object, description: str, **kwargs: object) -> ParameterSchema:
    return ParameterSchema(name, type, default, description, **kwargs)


def _runtime_parameters() -> tuple[ParameterSchema, ...]:
    return (
        _parameter("brightness", "integer", 255, "Output brightness", minimum=0, maximum=255, step=1, classification="runtime"),
        _parameter("fps", "integer", 30, "Target frame rate", minimum=1, maximum=60, step=1, units="fps", classification="runtime"),
        _parameter("exclude_tail", "boolean", False, "Exclude tail LEDs", classification="runtime"),
    )


def _schema(name: str, label: str, description: str, *parameters: ParameterSchema) -> EffectSchema:
    values = {parameter.name: parameter for parameter in (*_runtime_parameters(), *parameters)}
    return EffectSchema(name, label, description, values)


EFFECT_SCHEMAS: dict[str, EffectSchema] = {
    "clock-hand": _schema("clock-hand", "Clock hand", BY_NAME["clock-hand"].description,
        _parameter("rotation_seconds", "float", 3.0, "Full rotation duration", minimum=0.001, step=0.1, units="seconds"),
        _parameter("width_mm", "float", 300.0, "Visible hand width", minimum=0.001, step=1, units="mm"),
        _parameter("color", "colour", "FFFFFF", "Hand colour"), _parameter("background", "colour", "000000", "Background colour"),
        _parameter("direction", "choice", "clockwise", "Rotation direction", choices=("clockwise", "counterclockwise")),
        _parameter("angle_offset_degrees", "float", 0.0, "Installation angle offset", minimum=-360, maximum=360, step=1, units="degrees")),
    "expanding-rings": _schema("expanding-rings", "Expanding rings", BY_NAME["expanding-rings"].description,
        _parameter("origin", "string", "apex", "apex, centre, base, or X,Y,Z origin"), _parameter("speed_mps", "float", 0.5, "Shell speed", minimum=0.001, step=0.1, units="m/s"),
        _parameter("thickness_mm", "float", 200.0, "Shell thickness", minimum=0.001, step=1, units="mm"), _parameter("color", "colour", "FFFFFF", "Shell colour"), _parameter("background", "colour", "000000", "Background colour")),
    "height-wave": _schema("height-wave", "Height wave", BY_NAME["height-wave"].description,
        _parameter("speed_mps", "float", 0.5, "Band speed", minimum=0.001, step=0.1, units="m/s"), _parameter("height_mm", "float", 200.0, "Band height", minimum=0.001, step=1, units="mm"),
        _parameter("direction", "choice", "up", "Band direction", choices=("up", "down", "bounce")), _parameter("color", "colour", "FFFFFF", "Band colour"), _parameter("background", "colour", "000000", "Background colour")),
    "fire": _schema("fire", "Fire", BY_NAME["fire"].description,
        _parameter("speed", "float", 1.0, "Animation speed", minimum=0.001, step=0.05), _parameter("flame_height_m", "float", 2.5, "Flame height", minimum=0.001, step=0.1, units="m"),
        _parameter("turbulence", "float", .65, "Turbulence", minimum=0, maximum=1, step=.01), _parameter("cooling", "float", .35, "Cooling", minimum=0, maximum=1, step=.01), _parameter("scale", "float", 1.0, "Field scale", minimum=.001, step=.05), _parameter("palette", "choice", "fire", "Palette", choices=("fire",)), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
    "rotating-plane": _schema("rotating-plane", "Rotating plane", BY_NAME["rotating-plane"].description,
        _parameter("axis", "vector", "vertical", "vertical, horizontal, tilted, or X,Y,Z axis"), _parameter("rotation_seconds", "float", 10.0, "Full rotation duration", minimum=.001, step=.1, units="seconds"), _parameter("thickness_mm", "float", 220.0, "Plane thickness", minimum=.001, step=1, units="mm"), _parameter("trail_degrees", "float", 20.0, "Trail length", minimum=0, maximum=180, step=1, units="degrees"), _parameter("direction", "choice", "clockwise", "Rotation direction", choices=("clockwise", "counterclockwise")), _parameter("color", "colour", "FFFFFF", "Plane colour"), _parameter("background", "colour", "000000", "Background colour"), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
    "radar": _schema("radar", "Radar", BY_NAME["radar"].description,
        _parameter("rotation_seconds", "float", 8.0, "Full rotation duration", minimum=.001, step=.1, units="seconds"), _parameter("beam_width_degrees", "float", 12.0, "Beam width", minimum=.001, maximum=360, step=1, units="degrees"), _parameter("trail_degrees", "float", 35.0, "Trail length", minimum=0, maximum=360, step=1, units="degrees"), _parameter("range_m", "float", 9999.0, "Beam range", minimum=.001, step=.1, units="m"), _parameter("vertical_falloff", "float", 0.0, "Vertical falloff", minimum=0, maximum=1, step=.01), _parameter("color", "colour", "00FF80", "Beam colour"), _parameter("background", "colour", "000000", "Background colour"), _parameter("direction", "choice", "clockwise", "Rotation direction", choices=("clockwise", "counterclockwise")), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
    "aurora": _schema("aurora", "Aurora", BY_NAME["aurora"].description,
        _parameter("speed", "float", .25, "Animation speed", minimum=.001, step=.01), _parameter("scale", "float", 1.2, "Pattern scale", minimum=.001, step=.05), _parameter("band_width", "float", .45, "Band width", minimum=.001, maximum=1, step=.01), _parameter("intensity", "float", 1.0, "Intensity", minimum=0, maximum=1, step=.01), _parameter("palette", "choice", "mixed", "Palette", choices=("mixed",)), _parameter("direction", "vector", "1,0,0", "Direction vector"), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
    "fireflies": _schema("fireflies", "Fireflies", BY_NAME["fireflies"].description,
        _parameter("count", "integer", 25, "Particle count", minimum=1, step=1), _parameter("speed", "float", .35, "Animation speed", minimum=.001, step=.01), _parameter("glow_radius_mm", "float", 300.0, "Glow radius", minimum=.001, step=1, units="mm"), _parameter("lifetime_seconds", "float", 8.0, "Particle lifetime", minimum=.001, step=.1, units="seconds"), _parameter("color", "colour", "FFFFB0", "Base colour"), _parameter("color_variation", "float", .25, "Colour variation", minimum=0, maximum=1, step=.01), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
    "auto": _schema("auto", "Auto showcase", "Cycle existing effects with crossfades.",
        _parameter("effects", "effect-list", list(DEFAULT_PLAYLIST), "Ordered auto playlist", required=True), _parameter("interval", "float", 30.0, "Effect interval", minimum=.001, step=.1, units="seconds"), _parameter("transition", "float", 2.0, "Crossfade duration", minimum=0, step=.1, units="seconds"), _parameter("cycles", "integer", None, "Completed playlist cycles", minimum=1, step=1), _parameter("shuffle", "boolean", False, "Shuffle playlist"), _parameter("seed", "integer", 1, "Deterministic seed", step=1)),
}


def validate_effect_parameters(effect: str, values: Mapping[str, Any] | None = None) -> dict[str, object]:
    if effect not in EFFECT_SCHEMAS:
        raise ValueError(f"unknown effect {effect!r}")
    schema = EFFECT_SCHEMAS[effect]
    supplied = dict(values or {})
    unknown = set(supplied) - set(schema.parameters)
    if unknown:
        raise ValueError(f"unknown parameter {sorted(unknown)[0]!r} for {effect}")
    result: dict[str, object] = {}
    for name, parameter in schema.parameters.items():
        value = supplied.get(name, parameter.default)
        if value is None:
            if parameter.required:
                raise ValueError(f"parameter {name!r} is required")
            result[name] = None
            continue
        if parameter.type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"parameter {name!r} must be boolean")
        if parameter.type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"parameter {name!r} must be integer")
        if parameter.type == "float" and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)):
            raise ValueError(f"parameter {name!r} must be numeric")
        if parameter.type == "integer" and not math.isfinite(value):
            raise ValueError(f"parameter {name!r} must be finite")
        if parameter.type == "colour":
            if not isinstance(value, str) or re.fullmatch(r"#?[0-9A-Fa-f]{6}", value) is None:
                raise ValueError(f"parameter {name!r} must be #RRGGBB")
            value = value.upper().removeprefix("#")
        if parameter.type == "string" and not isinstance(value, str):
            raise ValueError(f"parameter {name!r} must be string")
        if parameter.type == "vector":
            if isinstance(value, str):
                if value in {"vertical", "horizontal", "tilted"}:
                    pass
                else:
                    try: value = [float(part) for part in value.split(",")]
                    except ValueError: raise ValueError(f"parameter {name!r} must be a named or numeric 3-vector")
            if isinstance(value, list):
                if len(value) != 3 or any(isinstance(part, bool) or not isinstance(part, (int, float)) or not math.isfinite(part) for part in value) or not any(value):
                    raise ValueError(f"parameter {name!r} must be a non-zero finite 3-vector")
            elif not isinstance(value, str):
                raise ValueError(f"parameter {name!r} must be a named or numeric 3-vector")
        if parameter.type == "choice" and value not in parameter.choices:
            raise ValueError(f"parameter {name!r} must be a supported choice")
        if parameter.type == "effect-list":
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or item not in BY_NAME for item in value):
                raise ValueError("effects contains an unknown effect or is empty")
            if len(set(value)) != len(value):
                raise ValueError("effects contains duplicates")
        if parameter.minimum is not None and value < parameter.minimum:
            raise ValueError(f"parameter {name!r} must be >= {parameter.minimum}")
        if parameter.maximum is not None and value > parameter.maximum:
            raise ValueError(f"parameter {name!r} must be <= {parameter.maximum}")
        result[name] = value
    if effect == "auto" and result["transition"] >= result["interval"]:
        raise ValueError("transition must be less than interval")
    return result
