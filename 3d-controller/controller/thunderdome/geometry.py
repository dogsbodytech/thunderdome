"""Validated structural geometry for the Thunderdome 3V 5/8 model."""
from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GeometryError(ValueError):
    pass


@dataclass(frozen=True)
class Hub:
    id: str
    x: float
    y: float
    z: float

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class Spar:
    id: str
    type: str
    start_hub: str
    end_hub: str
    length_m: float


@dataclass(frozen=True)
class DomeGeometry:
    hubs: dict[str, Hub]
    spars: dict[str, Spar]
    adjacency: dict[str, tuple[tuple[str, str], ...]]

    @property
    def spar_type_counts(self) -> dict[str, int]:
        counts = Counter(spar.type for spar in self.spars.values())
        return {kind: counts[kind] for kind in "ABC"}

    def spar_between(self, first_hub: str, second_hub: str) -> Spar | None:
        for neighbour, spar_id in self.adjacency.get(first_hub, ()):
            if neighbour == second_hub:
                return self.spars[spar_id]
        return None

    def is_connected(self) -> bool:
        if not self.hubs:
            return False
        visited = {next(iter(self.hubs))}
        pending = deque(visited)
        while pending:
            hub = pending.popleft()
            for neighbour, _ in self.adjacency[hub]:
                if neighbour not in visited:
                    visited.add(neighbour)
                    pending.append(neighbour)
        return len(visited) == len(self.hubs)


def load_geometry(path: str | Path) -> DomeGeometry:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeometryError(f"cannot load geometry {source}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise GeometryError("geometry must be a schema_version 1 JSON object")
    raw_hubs, raw_spars = document.get("hubs"), document.get("spars")
    if not isinstance(raw_hubs, list) or not isinstance(raw_spars, list):
        raise GeometryError("geometry must contain hubs and spars arrays")
    hubs: dict[str, Hub] = {}
    for row in raw_hubs:
        try:
            hub = Hub(str(row["id"]), float(row["x"]), float(row["y"]), float(row["z"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GeometryError(f"invalid hub: {row!r}") from exc
        if hub.id in hubs:
            raise GeometryError(f"duplicate hub ID: {hub.id}")
        hubs[hub.id] = hub
    spars: dict[str, Spar] = {}
    adjacency: dict[str, list[tuple[str, str]]] = {hub_id: [] for hub_id in hubs}
    for row in raw_spars:
        try:
            spar = Spar(str(row["id"]), str(row["type"]), str(row["start_hub"]), str(row["end_hub"]), float(row["length_m"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GeometryError(f"invalid spar: {row!r}") from exc
        if spar.id in spars or spar.type not in {"A", "B", "C"} or spar.start_hub not in hubs or spar.end_hub not in hubs:
            raise GeometryError(f"invalid spar identity/type/endpoints: {row!r}")
        spars[spar.id] = spar
        adjacency[spar.start_hub].append((spar.end_hub, spar.id))
        adjacency[spar.end_hub].append((spar.start_hub, spar.id))
    if len(hubs) != 61 or len(spars) != 165:
        raise GeometryError(f"expected 61 hubs/165 spars, got {len(hubs)}/{len(spars)}")
    geometry = DomeGeometry(hubs, spars, {hub: tuple(sorted(edges)) for hub, edges in adjacency.items()})
    if geometry.spar_type_counts != {"A": 30, "B": 55, "C": 80}:
        raise GeometryError(f"unexpected spar counts: {geometry.spar_type_counts}")
    if not geometry.is_connected():
        raise GeometryError("spar graph is disconnected")
    return geometry
