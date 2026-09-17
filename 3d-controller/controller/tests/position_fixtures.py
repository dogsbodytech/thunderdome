"""Temporary nominal-position fixtures derived from authoritative inputs."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from thunderdome.geometry import load_geometry
from thunderdome.led_positions import generate_positions, write_positions
from thunderdome.routes import load_routes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = PROJECT_ROOT / "geometry" / "thunderdome_geometry.json"
ROUTES_PATH = PROJECT_ROOT / "geometry" / "reference_string_route.md"


@contextmanager
def generated_positions_path() -> Iterator[Path]:
    """Yield a generated full positions document for the caller's scope."""
    with TemporaryDirectory() as directory:
        geometry = load_geometry(GEOMETRY_PATH)
        routes = load_routes(ROUTES_PATH, geometry)
        path = Path(directory) / "led_positions_3d.json"
        write_positions(path, generate_positions(routes, geometry))
        yield path


@contextmanager
def existing_positions_path() -> Iterator[Path]:
    """Yield an existing placeholder for tests that mock position loading."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "positions.json"
        path.touch()
        yield path
