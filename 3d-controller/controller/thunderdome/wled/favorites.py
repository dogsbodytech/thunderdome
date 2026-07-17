"""Effect favourites/favorites storage and cycling helpers.

The project uses a tiny JSON file instead of a database so an operator can copy,
back up, or inspect favourites easily. Normal use should still happen through
`wledctl.py favorites ...` so effect IDs are validated against the controller.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, TextIO

from .client import WLEDClient

DEFAULT_FAVORITES_FILE = "./wled_favourites.json"
DEFAULT_INTERVAL_SECONDS = 30

JsonDict = dict[str, Any]


class FavoritesError(ValueError):
    """Raised for invalid favourites config or operator input."""


class FavoritesStore:
    """Read/write the operator's favourite effects config file."""

    def __init__(self, path: str | Path = DEFAULT_FAVORITES_FILE) -> None:
        self.path = Path(path)

    def default_data(self) -> JsonDict:
        return {"default_interval_seconds": DEFAULT_INTERVAL_SECONDS, "effects": []}

    def load(self) -> JsonDict:
        if not self.path.exists():
            return self.default_data()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FavoritesError(f"Invalid JSON in favorites file {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise FavoritesError(f"Favorites file {self.path} must contain a JSON object")
        data.setdefault("default_interval_seconds", DEFAULT_INTERVAL_SECONDS)
        data.setdefault("effects", [])
        if not isinstance(data["effects"], list):
            raise FavoritesError(f"Favorites file {self.path} field 'effects' must be a list")
        validate_interval(data["default_interval_seconds"])
        return data

    def save(self, data: JsonDict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def list_effects(self) -> list[JsonDict]:
        return list(self.load()["effects"])

    def add_effect(self, effect_id: int, effects: list[str], notes: str | None = None) -> tuple[JsonDict, bool]:
        """Add an effect by ID after resolving its current WLED name.

        Returns (entry, created). Duplicate IDs are not added twice; notes are
        updated when supplied so an operator can refine descriptions over time.
        """
        name = resolve_effect_name(effect_id, effects)
        data = self.load()
        for entry in data["effects"]:
            if entry.get("id") == effect_id:
                entry["name"] = name  # keep stored name current with firmware list
                if notes is not None:
                    entry["notes"] = notes
                self.save(data)
                return entry, False

        entry: JsonDict = {"id": effect_id, "name": name}
        if notes:
            entry["notes"] = notes
        data["effects"].append(entry)
        self.save(data)
        return entry, True

    def add_effect_by_name(self, query: str, effects: list[str], notes: str | None = None) -> tuple[JsonDict, bool]:
        return self.add_effect(find_effect_id_by_name(query, effects), effects, notes=notes)

    def remove_effect(self, effect_id: int) -> bool:
        data = self.load()
        original = len(data["effects"])
        data["effects"] = [entry for entry in data["effects"] if entry.get("id") != effect_id]
        changed = len(data["effects"]) != original
        if changed:
            self.save(data)
        return changed

    def clear(self) -> None:
        data = self.load()
        data["effects"] = []
        self.save(data)

    def set_default_interval(self, seconds: float) -> None:
        """Set the saved default cycle interval while preserving favourites."""
        interval = validate_interval(seconds)
        data = self.load()
        # Store whole-number intervals as ints for a tidy operator-facing config,
        # but preserve non-integer seconds if an operator intentionally uses them.
        data["default_interval_seconds"] = int(interval) if interval.is_integer() else interval
        self.save(data)


def validate_interval(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise FavoritesError("interval must be a positive number of seconds")
    return float(value)


def resolve_effect_name(effect_id: int, effects: list[str]) -> str:
    if not isinstance(effect_id, int) or effect_id < 0:
        raise FavoritesError("effect_id must be a non-negative integer")
    if effect_id >= len(effects):
        raise FavoritesError(f"effect_id {effect_id} is out of range; controller has {len(effects)} effects")
    return effects[effect_id]


def find_effect_id_by_name(query: str, effects: list[str]) -> int:
    needle = query.strip().lower()
    if not needle:
        raise FavoritesError("effect name query cannot be empty")

    exact = [idx for idx, name in enumerate(effects) if name.lower() == needle]
    if exact:
        return exact[0]

    matches = [(idx, name) for idx, name in enumerate(effects) if needle in name.lower()]
    if not matches:
        raise FavoritesError(f"no effect name contains {query!r}")
    if len(matches) > 1:
        sample = ", ".join(f"{idx}:{name}" for idx, name in matches[:10])
        raise FavoritesError(f"multiple effects match {query!r}; use an ID. Matches: {sample}")
    return matches[0][0]


def filter_effects(effects: list[str], query: str | None = None) -> list[tuple[int, str]]:
    if not query:
        return list(enumerate(effects))
    needle = query.lower()
    return [(idx, name) for idx, name in enumerate(effects) if needle in name.lower()]


def cycle_favorites(
    client: WLEDClient,
    store: FavoritesStore,
    *,
    interval: float | None = None,
    loop: bool = False,
    segment_id: int | None = None,
    return_state: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    output: TextIO | None = None,
) -> int:
    """Apply saved effects in order, optionally looping until Ctrl-C.

    JSON state changes are intentionally low-rate here. For high-FPS per-pixel
    animation on a 5000 LED dome, use WLED realtime protocols such as DDP/UDP.
    """
    data = store.load()
    effects = data["effects"]
    if not effects:
        raise FavoritesError("no favorite effects saved; add some with 'favorites add <effect_id>'")
    wait_seconds = validate_interval(interval if interval is not None else data["default_interval_seconds"])

    applied = 0
    try:
        while True:
            for entry in effects:
                effect_id = entry.get("id")
                name = entry.get("name", "<unnamed>")
                if not isinstance(effect_id, int):
                    raise FavoritesError(f"favorite entry has invalid id: {entry!r}")
                print(f"Applying effect {effect_id}: {name}", file=output)
                client.set_effect(effect_id, segment_id=segment_id, return_state=return_state)
                applied += 1
                if loop or entry is not effects[-1]:
                    sleep_fn(wait_seconds)
            if not loop:
                return applied
    except KeyboardInterrupt:
        print("Stopped favorite effect cycle.", file=output)
        return applied
