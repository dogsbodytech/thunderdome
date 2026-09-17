"""Canonical structured definitions for the five physical LED routes."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .geometry import DomeGeometry


class RouteError(ValueError):
    pass


EXPECTED = {
    1: (0, "H032", 0, 999),
    2: (1, "H033", 1000, 1999),
    3: (2, "H034", 2000, 2999),
    4: (3, "H035", 3000, 3999),
    5: (4, "H031", 4000, 4999),
}
ROUTE_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class DirectedSegment:
    spar_id: str
    spar_type: str
    from_hub: str
    to_hub: str
    length_m: float


@dataclass(frozen=True)
class RouteDefinition:
    string_id: int
    hubs: tuple[str, ...]
    rotation_degrees: float = 0.0
    controller_number: int = 0
    global_index_start: int = 0
    global_index_end: int = 999
    start_hub: str = ""
    end_hub: str = ""
    segments: tuple[DirectedSegment, ...] = ()

    @property
    def total_length_m(self) -> float:
        return sum(segment.length_m for segment in self.segments)

    @property
    def unique_spar_count(self) -> int:
        return len({segment.spar_id for segment in self.segments})

    def spar_ids(self, geometry: DomeGeometry) -> tuple[str, ...]:
        return tuple(
            geometry.spar_between(start, end).id
            for start, end in zip(self.hubs, self.hubs[1:])
            if geometry.spar_between(start, end)
        )


def _route_error(route_path: Path, route_id: object, detail: str) -> RouteError:
    return RouteError(f"{route_path}: route {route_id}: {detail}")


def load_routes(path: str | Path, geometry: DomeGeometry) -> list[RouteDefinition]:
    route_path = Path(path)
    if route_path.suffix.lower() != ".json":
        raise RouteError(f"{route_path}: canonical routes must be JSON")
    try:
        document = json.loads(route_path.read_text())
    except json.JSONDecodeError as exc:
        raise RouteError(f"{route_path}: malformed routes JSON: {exc.msg}") from exc
    except OSError as exc:
        raise RouteError(f"{route_path}: cannot read routes file: {exc}") from exc

    if not isinstance(document, dict) or document.get("schema_version") != ROUTE_SCHEMA_VERSION:
        raise RouteError(f"{route_path}: unsupported routes schema")
    records = document.get("routes")
    if not isinstance(records, list):
        raise RouteError(f"{route_path}: routes JSON must contain a routes array")

    routes: list[RouteDefinition] = []
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise RouteError(f"{route_path}: route {index} must be an object")
        route_id = record.get("string_id", index)
        try:
            controller_number = int(record["controller_number"])
            string_id = int(record["string_id"])
            global_index_start = int(record["global_index_start"])
            global_index_end = int(record["global_index_end"])
            start_hub = record["start_hub"]
            end_hub = record["end_hub"]
            hubs = record["ordered_hubs"]
        except (KeyError, TypeError, ValueError) as exc:
            raise _route_error(route_path, route_id, "metadata is incomplete") from exc
        if not all(isinstance(value, str) for value in (start_hub, end_hub)):
            raise _route_error(route_path, route_id, "endpoints must be canonical hub IDs")
        if not isinstance(hubs, list) or not all(isinstance(hub, str) for hub in hubs):
            raise _route_error(route_path, route_id, "ordered_hubs must contain canonical hub IDs")
        unknown_hub = next((hub for hub in hubs if hub not in geometry.hubs), None)
        if unknown_hub is not None:
            raise _route_error(route_path, route_id, f"unknown hub {unknown_hub}")
        if len(hubs) != 25:
            raise _route_error(route_path, route_id, "expected 25 hubs")
        if hubs[0] != start_hub or hubs[-1] != end_hub:
            raise _route_error(route_path, route_id, "ordered hubs do not match endpoints")

        segments: list[DirectedSegment] = []
        for from_hub, to_hub in zip(hubs, hubs[1:]):
            spar = geometry.spar_between(from_hub, to_hub)
            if spar is None:
                raise _route_error(route_path, route_id, f"{from_hub}->{to_hub} is not a spar")
            segments.append(DirectedSegment(spar.id, spar.type, from_hub, to_hub, spar.length_m))
        routes.append(
            RouteDefinition(
                string_id=string_id,
                hubs=tuple(hubs),
                controller_number=controller_number,
                global_index_start=global_index_start,
                global_index_end=global_index_end,
                start_hub=start_hub,
                end_hub=end_hub,
                segments=tuple(segments),
            )
        )

    validate_routes(geometry, routes)
    return sorted(routes, key=lambda route: route.string_id)


def validate_routes(geometry: DomeGeometry, routes: list[RouteDefinition], require_apex: bool = True) -> None:
    # Minimal geometry-only routes remain useful for focused geometry tests.
    if routes and all(route.controller_number == 0 for route in routes):
        used: set[str] = set()
        for route in routes:
            for start, end in zip(route.hubs, route.hubs[1:]):
                spar = geometry.spar_between(start, end)
                if spar is None:
                    raise RouteError(f"{start}->{end} is not a spar")
                if spar.id in used:
                    raise RouteError(f"shared spar {spar.id}")
                used.add(spar.id)
        return

    if len(routes) != 5:
        raise RouteError("expected exactly five routes")
    used: dict[str, int] = {}
    types: tuple[str, ...] | None = None
    length: float | None = None
    controllers: set[int] = set()
    strings: set[int] = set()
    for route in routes:
        expected = EXPECTED.get(route.controller_number)
        if expected is None or (route.string_id, route.start_hub, route.global_index_start, route.global_index_end) != expected:
            raise RouteError(f"controller allocation mismatch for {route.controller_number}")
        if route.controller_number in controllers or route.string_id in strings:
            raise RouteError("controller and string allocations must be unique")
        controllers.add(route.controller_number)
        strings.add(route.string_id)
        if len(route.hubs) != 25 or len(route.segments) != 24:
            raise RouteError(f"string {route.string_id}: expected 25 hubs/24 segments")
        if require_apex and route.end_hub != "H061":
            raise RouteError("all routes must end H061")
        route_types = tuple(segment.spar_type for segment in route.segments)
        if types is None:
            types = route_types
            length = route.total_length_m
        if route_types != types or abs(route.total_length_m - length) > 1e-5:
            raise RouteError("routes must have identical types and length")
        for segment in route.segments:
            if segment.spar_id in used:
                raise RouteError(f"shared spar {segment.spar_id}")
            used[segment.spar_id] = route.string_id
    if controllers != set(EXPECTED) or strings != {0, 1, 2, 3, 4}:
        raise RouteError("expected controller and string allocations")
    if len(used) != 120:
        raise RouteError("expected 120 unique route spars")
