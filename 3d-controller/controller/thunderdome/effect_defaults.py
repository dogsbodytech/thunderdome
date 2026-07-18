"""Atomic local persistence for operator effect defaults."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .schemas import EFFECT_SCHEMAS, validate_effect_parameters
from .effects.Registry import LEGACY_NAMES


class EffectDefaults:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed effect defaults JSON: {exc.msg}") from exc
        if not isinstance(data, dict) or any(not isinstance(name, str) or not isinstance(values, dict) for name, values in data.items()):
            raise ValueError("malformed effect defaults JSON")
        normalized: dict[str, dict[str, object]] = {}
        for name, values in data.items():
            effect = LEGACY_NAMES.get(name) or name
            self._validate_override(effect, values)
            if effect in normalized:
                raise ValueError(f"duplicate defaults for {effect!r}")
            normalized[effect] = values
        return normalized

    def _validate_override(self, effect: str, values: Mapping[str, object]) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        if effect not in EFFECT_SCHEMAS or effect == "Auto":
            raise ValueError(f"unknown effect {effect!r}")
        runtime = {name for name, parameter in EFFECT_SCHEMAS[effect].parameters.items() if parameter.classification == "runtime"}
        if runtime.intersection(values):
            raise ValueError("runtime parameters cannot be saved as effect defaults")
        return validate_effect_parameters(effect, values)

    def saved(self, effect: str) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        return dict(self._read().get(effect, {}))

    def resolved(self, effect: str) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        saved = self.saved(effect)
        return dict(validate_effect_parameters(effect, saved))

    def payload(self, effect: str) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        return {"effect": effect, "built_in": validate_effect_parameters(effect), "saved": self.saved(effect), "resolved": self.resolved(effect)}

    def save(self, effect: str, values: Mapping[str, object]) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        resolved = self._validate_override(effect, values)
        data = self._read()
        data[effect] = {name: value for name, value in resolved.items() if name not in {"brightness", "fps", "exclude_tail"} and name in values}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, self.path)
        return self.payload(effect)

    def delete(self, effect: str) -> dict[str, object]:
        effect = LEGACY_NAMES.get(effect, effect)
        if effect not in EFFECT_SCHEMAS or effect == "Auto":
            raise ValueError(f"unknown effect {effect!r}")
        data = self._read(); data.pop(effect, None)
        if self.path.exists():
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, self.path)
        return self.payload(effect)

    def all_payload(self) -> dict[str, object]:
        return {"effects": [self.payload(effect) for effect in EFFECT_SCHEMAS if effect != "Auto"]}
