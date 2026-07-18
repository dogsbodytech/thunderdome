"""Offline static geometry simulator server for Thunderdome Stage A."""
from __future__ import annotations

import json
import math
import mimetypes
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import GEOMETRY_PATH, LED_POSITIONS_PATH, PROJECT_ROOT, REFERENCE_ROUTE_PATH
from .geometry import DomeGeometry, load_geometry
from .led_positions import load_led_positions
from .routes import load_routes

SIMULATOR_SCHEMA_VERSION = 1
THREE_VERSION = "0.160.0"


class SimulatorDataError(ValueError):
    """Raised when simulator source data cannot be normalized safely."""


def simulator_static_dir() -> Path:
    return PROJECT_ROOT / "simulator" / "static"


def resolve_user_path(value: str | None, default: str | Path) -> Path:
    """Resolve a CLI path while preserving explicit relative-path semantics."""
    return Path(default) if value is None else Path(value)


def _xyz(row: Any) -> tuple[float, float, float]:
    try:
        values = (float(row["x"]), float(row["y"]), float(row["z"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise SimulatorDataError(f"invalid XYZ row: {row!r}") from exc
    if not all(math.isfinite(value) for value in values):
        raise SimulatorDataError(f"non-finite XYZ row: {row!r}")
    return values


def _bounds(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    return {
        axis: [min(point[index] for point in points), max(point[index] for point in points)]
        for index, axis in enumerate("xyz")
    }


def _normalize_geometry(geometry: DomeGeometry) -> dict[str, Any]:
    if "H061" not in geometry.hubs:
        raise SimulatorDataError("geometry is missing required apex hub H061")
    hubs = [
        {"id": hub.id, "xyz": [hub.x, hub.y, hub.z], "x": hub.x, "y": hub.y, "z": hub.z, "is_apex": hub.id == "H061"}
        for hub in sorted(geometry.hubs.values(), key=lambda hub: hub.id)
    ]
    spars = []
    for spar in sorted(geometry.spars.values(), key=lambda spar: spar.id):
        start = geometry.hubs[spar.start_hub]
        end = geometry.hubs[spar.end_hub]
        spars.append(
            {
                "id": spar.id,
                "type": spar.type,
                "start_hub": spar.start_hub,
                "end_hub": spar.end_hub,
                "start_xyz": [start.x, start.y, start.z],
                "end_xyz": [end.x, end.y, end.z],
                "length_m": spar.length_m,
            }
        )
    return {
        "hubs": hubs,
        "spars": spars,
        "apex_id": "H061",
        "apex_xyz": list(geometry.hubs["H061"].xyz),
        "bounds": _bounds([hub.xyz for hub in geometry.hubs.values()]),
    }


def _normalize_leds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leds: list[dict[str, Any]] = []
    for row in rows:
        global_index = int(row["global_index"])
        controller_number = int(row.get("controller_number", global_index // 1000 + 1))
        string_id = int(row.get("string_id", controller_number - 1))
        local_index = int(row.get("string_index", global_index % 1000))
        is_tail = row.get("location_type") == "tail"
        led = {
            "global_index": global_index,
            "controller_number": controller_number,
            "string_id": string_id,
            "local_index": local_index,
            "string_index": local_index,
            "xyz": list(_xyz(row)),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "z": float(row["z"]),
            "is_tail": is_tail,
            "location_type": row.get("location_type"),
            "distance_along_string_m": float(row.get("distance_along_string_m", 0.0)),
        }
        for key in (
            "spar_id",
            "spar_type",
            "from_hub",
            "to_hub",
            "fraction_along_spar",
            "distance_along_spar_m",
            "distance_along_route_m",
            "tail_index",
            "distance_below_apex_m",
        ):
            if key in row:
                led[key] = row[key]
        leds.append(led)
    return leds


def validate_simulator_data(payload: dict[str, Any], geometry_path: str | Path, routes_path: str | Path, positions_path: str | Path) -> None:
    leds = payload.get("leds")
    if not isinstance(leds, list) or len(leds) != 5000:
        raise SimulatorDataError(f"{positions_path}: expected exactly 5,000 LEDs; run `thunderdome positions generate`")
    indexes = [led.get("global_index") for led in leds]
    if indexes != list(range(5000)) or len(set(indexes)) != 5000:
        raise SimulatorDataError(f"{positions_path}: LED global indexes must be exactly 0..4999")
    for led in leds:
        coords = led.get("xyz")
        if not isinstance(coords, list) or len(coords) != 3 or not all(math.isfinite(float(value)) for value in coords):
            raise SimulatorDataError(f"{positions_path}: LED {led.get('global_index')} has non-finite XYZ coordinates")
        expected_controller = int(led["global_index"]) // 1000 + 1
        expected_local = int(led["global_index"]) % 1000
        if led.get("controller_number") != expected_controller or led.get("local_index") != expected_local:
            raise SimulatorDataError(f"{positions_path}: LED {led.get('global_index')} has inconsistent controller/local index")
        if led.get("is_tail") and "tail_index" not in led:
            raise SimulatorDataError(f"{positions_path}: tail LED {led.get('global_index')} is missing tail_index")
    geometry = payload.get("geometry", {})
    hubs = geometry.get("hubs")
    if not isinstance(hubs, list) or not any(hub.get("id") == "H061" for hub in hubs):
        raise SimulatorDataError(f"{geometry_path}: required apex hub H061 is missing")
    hub_ids = {hub.get("id") for hub in hubs}
    for spar in geometry.get("spars", []):
        if spar.get("start_hub") not in hub_ids or spar.get("end_hub") not in hub_ids:
            raise SimulatorDataError(f"{geometry_path}: spar {spar.get('id')} has invalid endpoints")


def _validate_position_route_metadata(led_rows: list[dict[str, Any]], routes: list[Any], routes_path: Path, positions_path: Path) -> None:
    route_by_string = {route.string_id: route for route in routes}
    for row in led_rows:
        if row.get("location_type") != "spar":
            continue
        route = route_by_string.get(row.get("string_id"))
        if route is None:
            raise SimulatorDataError(f"{positions_path}: LED {row.get('global_index')} references unknown string route in {routes_path}")
        segment = next((item for item in route.segments if item.spar_id == row.get("spar_id")), None)
        if segment is None:
            raise SimulatorDataError(f"{positions_path}: LED {row.get('global_index')} references spar {row.get('spar_id')} absent from {routes_path}")
        if row.get("from_hub") != segment.from_hub or row.get("to_hub") != segment.to_hub:
            raise SimulatorDataError(f"{positions_path}: LED {row.get('global_index')} route metadata conflicts with {routes_path} spar {segment.spar_id}")


def build_simulator_payload(geometry_path: str | Path, routes_path: str | Path, positions_path: str | Path) -> dict[str, Any]:
    geometry_path = Path(geometry_path)
    routes_path = Path(routes_path)
    positions_path = Path(positions_path)
    try:
        geometry = load_geometry(geometry_path)
        routes = load_routes(routes_path, geometry)
        led_rows = load_led_positions(positions_path, geometry, routes)
    except Exception as exc:
        raise SimulatorDataError(
            f"cannot load simulator data from geometry={geometry_path} routes={routes_path} positions={positions_path}: {exc}; "
            "run `thunderdome positions generate` if generated positions are missing"
        ) from exc
    _validate_position_route_metadata(led_rows, routes, routes_path, positions_path)
    normalized_geometry = _normalize_geometry(geometry)
    leds = _normalize_leds(led_rows)
    points = [tuple(led["xyz"]) for led in leds]
    tail_count = sum(1 for led in leds if led["is_tail"])
    metadata = {
        "schema_version": SIMULATOR_SCHEMA_VERSION,
        "simulator_mode": "static viewer",
        "three_version": THREE_VERSION,
        "geometry_source": str(geometry_path),
        "routes_source": str(routes_path),
        "positions_source": str(positions_path),
        "geometry_source_filename": geometry_path.name,
        "routes_source_filename": routes_path.name,
        "positions_source_filename": positions_path.name,
        "route_count": len(routes),
        "total_led_count": len(leds),
        "tail_count": tail_count,
        "controller_count": len({led["controller_number"] for led in leds}),
        "string_count": len({led["string_id"] for led in leds}),
        "hub_count": len(normalized_geometry["hubs"]),
        "spar_count": len(normalized_geometry["spars"]),
        "apex": {"id": "H061", "xyz": normalized_geometry["apex_xyz"]},
        "bounds": _bounds(points),
        "string_ranges": [
            {"controller_number": controller, "global_start": (controller - 1) * 1000, "global_end": controller * 1000 - 1}
            for controller in range(1, 6)
        ],
    }
    payload = {"metadata": metadata, "geometry": normalized_geometry, "leds": leds}
    validate_simulator_data(payload, geometry_path, routes_path, positions_path)
    return payload


class SimulatorRequestHandler(BaseHTTPRequestHandler):
    server: "SimulatorHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
        return

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any) -> None:
        self._send_bytes(200, json.dumps(obj, separators=(",", ":")).encode("utf-8"), "application/json; charset=utf-8")

    def _send_error(self, status: int, message: str) -> None:
        self._send_bytes(status, json.dumps({"error": message}).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/simulator/metadata":
            self._send_json(self.server.payload["metadata"])
            return
        if path == "/api/simulator/geometry":
            self._send_json(self.server.payload["geometry"])
            return
        if path == "/api/simulator/leds":
            self._send_json({"leds": self.server.payload["leds"]})
            return
        if path.startswith("/api/"):
            self._send_error(404, "unknown simulator API endpoint")
            return
        if path == "/":
            relative = Path("index.html")
        else:
            relative = Path(path.lstrip("/"))
        if relative.is_absolute() or ".." in relative.parts:
            self._send_error(403, "invalid static path")
            return
        candidate = (self.server.static_dir / relative).resolve()
        try:
            candidate.relative_to(self.server.static_dir.resolve())
        except ValueError:
            self._send_error(403, "invalid static path")
            return
        if not candidate.is_file():
            self._send_error(404, "static asset not found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        self._send_bytes(200, candidate.read_bytes(), content_type)


class SimulatorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], payload: dict[str, Any], static_dir: Path):
        super().__init__(server_address, SimulatorRequestHandler)
        self.payload = payload
        self.static_dir = static_dir


def create_http_server(host: str, port: int, geometry_path: str | Path, routes_path: str | Path, positions_path: str | Path) -> SimulatorHTTPServer:
    payload = build_simulator_payload(geometry_path, routes_path, positions_path)
    return SimulatorHTTPServer((host, port), payload, simulator_static_dir())


def _local_urls(host: str, port: int) -> list[str]:
    if host in {"127.0.0.1", "localhost"}:
        return [f"http://127.0.0.1:{port}/"]
    if host == "0.0.0.0":
        urls = [f"http://127.0.0.1:{port}/"]
        try:
            hostname = socket.gethostname()
            for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM):
                address = sockaddr[0]
                if ":" not in address and not address.startswith("127."):
                    url = f"http://{address}:{port}/"
                    if url not in urls:
                        urls.append(url)
        except OSError:
            pass
        return urls
    return [f"http://{host}:{port}/"]


def serve_simulator(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    geometry_path: str | Path = GEOMETRY_PATH,
    routes_path: str | Path = REFERENCE_ROUTE_PATH,
    positions_path: str | Path = LED_POSITIONS_PATH,
    open_browser: bool = False,
) -> int:
    server = create_http_server(host, port, geometry_path, routes_path, positions_path)
    actual_port = server.server_address[1]
    urls = _local_urls(host, actual_port)
    print("Simulator mode: static viewer")
    print("No HTTP requests will be sent to WLED controllers.")
    print("No UDP/DDP packets will be sent.")
    print("\nGeometry:")
    print(f"  {Path(geometry_path).resolve()}")
    print("\nRoutes:")
    print(f"  {Path(routes_path).resolve()}")
    print("\nPositions:")
    print(f"  {Path(positions_path).resolve()}")
    print("\nSimulator available at:")
    for url in urls:
        print(url)
    if host == "0.0.0.0":
        print("\nBinding to 0.0.0.0 exposes the local development server to reachable machines on this network.")
    if open_browser:
        try:
            webbrowser.open(urls[0])
            print(f"Requested browser open: {urls[0]}")
        except Exception as exc:  # pragma: no cover - browser support varies
            print(f"Could not open browser automatically: {exc}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        return 130
    finally:
        server.shutdown()
        server.server_close()
    return 0
