"""Runtime defaults for the Python-rendered Thunderdome controller."""
from __future__ import annotations

from pathlib import Path

LED_COUNT = 5_000
DDP_PORT = 4048
DDP_CHUNK_LEDS = 480
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = PROJECT_ROOT / "geometry" / "thunderdome_geometry.json"
REFERENCE_ROUTE_PATH = PROJECT_ROOT / "geometry" / "reference_string_route.md"
LED_POSITIONS_PATH = PROJECT_ROOT / "geometry" / "generated" / "led_positions_3d.json"
