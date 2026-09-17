"""Canonical immutable runtime-resource paths."""
from __future__ import annotations

import sysconfig
from pathlib import Path

CONTROLLER_LED_COUNT = 1_000
LOGICAL_LED_COUNT = CONTROLLER_LED_COUNT * 5
DDP_PORT = 4048
DDP_CHUNK_LEDS = 480


def installed_resource_root(data_root: str | Path | None = None) -> Path:
    """Return the stable data-files location for an installed wheel."""
    return Path(data_root if data_root is not None else sysconfig.get_path("data")) / "share" / "thunderdome"


def _source_resource_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[2]
    required = (
        candidate / "pyproject.toml",
        candidate / "geometry" / "thunderdome_geometry.json",
        candidate / "geometry" / "routes" / "string_routes.json",
        candidate / "simulator" / "static" / "index.html",
    )
    return candidate if all(path.exists() for path in required) else None


def resource_root() -> Path:
    root = _source_resource_root() or installed_resource_root()
    required = (
        root / "geometry" / "thunderdome_geometry.json",
        root / "geometry" / "routes" / "string_routes.json",
        root / "simulator" / "static" / "index.html",
        root / "simulator" / "static" / "simulator.css",
        root / "simulator" / "static" / "simulator.js",
        root / "simulator" / "static" / "control-ui.js",
        root / "simulator" / "static" / "vendor" / "three.module.js",
        root / "simulator" / "static" / "vendor" / "OrbitControls.js",
        root / "simulator" / "static" / "vendor" / "LICENSE.threejs",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Thunderdome immutable runtime resources are missing: " + ", ".join(missing))
    return root


RESOURCE_ROOT = resource_root()
SOURCE_RESOURCE_ROOT = _source_resource_root()
GEOMETRY_PATH = RESOURCE_ROOT / "geometry" / "thunderdome_geometry.json"
ROUTES_PATH = RESOURCE_ROOT / "geometry" / "routes" / "string_routes.json"
SIMULATOR_STATIC_PATH = RESOURCE_ROOT / "simulator" / "static"
# Mutable paths are made install-safe in the following change; retain source defaults now.
_MUTABLE_ROOT = SOURCE_RESOURCE_ROOT or RESOURCE_ROOT
LED_POSITIONS_PATH = _MUTABLE_ROOT / "geometry" / "generated" / "led_positions_3d.json"
CONTROLLERS_PATH = _MUTABLE_ROOT / "config" / "controllers.json"
EFFECT_DEFAULTS_PATH = _MUTABLE_ROOT / "config" / "effect-defaults.json"
