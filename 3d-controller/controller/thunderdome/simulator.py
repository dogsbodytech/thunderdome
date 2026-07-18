"""Offline geometry simulator with live aiohttp WebSocket frame streaming."""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import mimetypes
import socket
import threading
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from aiohttp import WSCloseCode, WSMsgType, web

from .config import GEOMETRY_PATH, LED_POSITIONS_PATH, PROJECT_ROOT, REFERENCE_ROUTE_PATH
from .geometry import DomeGeometry, load_geometry
from .led_positions import load_led_positions
from .routes import load_routes
from .streaming import FRAME_PAYLOAD_LENGTH, FRAME_VERSION, FrameProtocolError, decode_frame

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


class SimulatorHTTPServer:
    """Compatibility wrapper that hosts the aiohttp simulator in its own loop thread."""

    def __init__(self, server_address: tuple[str, int], payload: dict[str, Any], static_dir: Path):
        self.payload = payload
        self.static_dir = static_dir.resolve()
        self._host, self._requested_port = server_address
        self.server_address = server_address
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._startup_error: BaseException | None = None
        self._closed = False
        self._producer: web.WebSocketResponse | None = None
        self._viewers: dict[web.WebSocketResponse, asyncio.Queue[bytes]] = {}
        self._latest_frame: bytes | None = None
        self._last_frame: dict[str, Any] | None = None
        self._received_frames = 0
        self._rejected_frames = 0
        self._app = web.Application(client_max_size=FRAME_PAYLOAD_LENGTH + 64)
        self._configure_routes()
        self._thread = threading.Thread(target=self._run, name="thunderdome-simulator", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            raise RuntimeError("could not start simulator server") from self._startup_error

    def _configure_routes(self) -> None:
        self._app.router.add_get("/api/simulator/metadata", self._metadata)
        self._app.router.add_get("/api/simulator/status", self._status)
        self._app.router.add_get("/api/simulator/geometry", self._geometry)
        self._app.router.add_get("/api/simulator/leds", self._leds)
        self._app.router.add_get("/ws/producer", self._producer_ws)
        self._app.router.add_get("/ws/viewer", self._viewer_ws)
        self._app.router.add_get("/{path:.*}", self._static)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
        else:
            self._ready.set()
            self._loop.run_forever()
        finally:
            self._loop.run_until_complete(self._cleanup())
            self._stopped.set()
            self._loop.close()

    async def _start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._requested_port)
        await self._site.start()
        sockets = self._site._server.sockets  # aiohttp exposes the bound server here.
        self.server_address = (self._host, int(sockets[0].getsockname()[1]))

    async def _cleanup(self) -> None:
        if hasattr(self, "_runner"):
            await self._runner.cleanup()

    @staticmethod
    def _json(value: Any, *, status: int = 200) -> web.Response:
        return web.Response(
            status=status,
            body=json.dumps(value, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
        )

    async def _metadata(self, request: web.Request) -> web.Response:
        metadata = dict(self.payload["metadata"])
        metadata["streaming"] = {
            "supported": True,
            "protocol_version": FRAME_VERSION,
            "encoding": "rgb8",
            "expected_pixel_count": FRAME_PAYLOAD_LENGTH // 3,
            "expected_payload_length": FRAME_PAYLOAD_LENGTH,
            "producer_websocket_path": "/ws/producer",
            "viewer_websocket_path": "/ws/viewer",
            "viewer_queue_size": 1,
        }
        return self._json(metadata)

    async def _status(self, request: web.Request) -> web.Response:
        return self._json(
            {
                "producer_connected": self._producer is not None and not self._producer.closed,
                "viewer_count": len(self._viewers),
                "received_frames": self._received_frames,
                "rejected_frames": self._rejected_frames,
                "last_frame": self._last_frame,
            }
        )

    async def _geometry(self, request: web.Request) -> web.Response:
        return self._json(self.payload["geometry"])

    async def _leds(self, request: web.Request) -> web.Response:
        return self._json({"leds": self.payload["leds"]})

    async def _producer_ws(self, request: web.Request) -> web.StreamResponse:
        if self._producer is not None and not self._producer.closed:
            return self._json({"error": "a producer is already connected"}, status=409)
        websocket = web.WebSocketResponse(max_msg_size=FRAME_PAYLOAD_LENGTH + 64)
        await websocket.prepare(request)
        self._producer = websocket
        producer_last_sequence: int | None = None
        try:
            async for message in websocket:
                if message.type != WSMsgType.BINARY:
                    self._rejected_frames += 1
                    await websocket.close(code=WSCloseCode.UNSUPPORTED_DATA, message=b"binary frames required")
                    break
                try:
                    decoded = decode_frame(message.data)
                except FrameProtocolError as exc:
                    self._rejected_frames += 1
                    await websocket.close(code=WSCloseCode.UNSUPPORTED_DATA, message=str(exc).encode("utf-8"))
                    break
                if producer_last_sequence is not None and decoded.sequence <= producer_last_sequence:
                    self._rejected_frames += 1
                    continue
                producer_last_sequence = decoded.sequence
                wire_frame = bytes(message.data)
                self._latest_frame = wire_frame
                self._last_frame = {
                    "sequence": decoded.sequence,
                    "timestamp": decoded.timestamp,
                    "pixel_count": decoded.pixel_count,
                }
                self._received_frames += 1
                self._broadcast_newest(wire_frame)
        finally:
            if self._producer is websocket:
                self._producer = None
        return websocket

    def _broadcast_newest(self, wire_frame: bytes) -> None:
        for queue in tuple(self._viewers.values()):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(wire_frame)

    async def _send_viewer_frames(self, websocket: web.WebSocketResponse, queue: asyncio.Queue[bytes]) -> None:
        while not websocket.closed:
            await websocket.send_bytes(await queue.get())

    async def _viewer_ws(self, request: web.Request) -> web.StreamResponse:
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
        self._viewers[websocket] = queue
        if self._latest_frame is not None:
            queue.put_nowait(self._latest_frame)
        sender = asyncio.create_task(self._send_viewer_frames(websocket, queue))
        try:
            async for message in websocket:
                if message.type == WSMsgType.ERROR:
                    break
        finally:
            self._viewers.pop(websocket, None)
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
        return websocket

    async def _static(self, request: web.Request) -> web.Response:
        raw_path = unquote(request.match_info.get("path", ""))
        relative = Path("index.html") if not raw_path else Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            return self._json({"error": "invalid static path"}, status=403)
        candidate = (self.static_dir / relative).resolve()
        try:
            candidate.relative_to(self.static_dir)
        except ValueError:
            return self._json({"error": "invalid static path"}, status=403)
        if not candidate.is_file():
            if raw_path.startswith("api/"):
                return self._json({"error": "unknown simulator API endpoint"}, status=404)
            return self._json({"error": "static asset not found"}, status=404)
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        return web.Response(body=candidate.read_bytes(), headers={"Content-Type": content_type, "Cache-Control": "no-store"})

    def serve_forever(self) -> None:
        """Block like ``ThreadingHTTPServer.serve_forever`` for API compatibility."""
        self._stopped.wait()

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def server_close(self) -> None:
        self.shutdown()


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
    print("Simulator mode: live viewer")
    print("No HTTP requests will be sent to WLED controllers.")
    print("No UDP/DDP packets will be sent by the simulator server.")
    print("\nGeometry:")
    print(f"  {Path(geometry_path).resolve()}")
    print("\nRoutes:")
    print(f"  {Path(routes_path).resolve()}")
    print("\nPositions:")
    print(f"  {Path(positions_path).resolve()}")
    print("\nSimulator available at:")
    for url in urls:
        print(url)
    print(f"\nProducer WebSocket: ws://{urls[0].removeprefix('http://').rstrip('/')}/ws/producer")
    print(f"Viewer WebSocket: ws://{urls[0].removeprefix('http://').rstrip('/')}/ws/viewer")
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
