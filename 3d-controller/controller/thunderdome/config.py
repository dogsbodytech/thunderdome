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
def mutable_runtime_paths(
    *,
    source_root: Path | None = SOURCE_RESOURCE_ROOT,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return controller config, effect defaults, and generated-data paths."""
    import os

    environment = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    config_override = environment.get("THUNDERDOME_CONFIG_DIR")
    data_override = environment.get("THUNDERDOME_DATA_DIR")
    config_dir = Path(config_override) if config_override else (source_root / "config" if source_root is not None else Path(environment.get("XDG_CONFIG_HOME", user_home / ".config")) / "thunderdome")
    data_dir = Path(data_override) if data_override else (source_root / "geometry" / "generated" if source_root is not None else Path(environment.get("XDG_DATA_HOME", user_home / ".local" / "share")) / "thunderdome")
    return config_dir / "controllers.json", config_dir / "effect-defaults.json", data_dir / "led_positions_3d.json"


CONTROLLERS_PATH, EFFECT_DEFAULTS_PATH, LED_POSITIONS_PATH = mutable_runtime_paths()
