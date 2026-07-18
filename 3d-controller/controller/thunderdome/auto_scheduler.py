"""Shared playlist timing and crossfade rendering for CLI and control runtime."""
from __future__ import annotations

import random
from dataclasses import dataclass
from collections.abc import Callable, Sequence

from .effects.procedural import blend
from .frame import RGBFrame


@dataclass(frozen=True)
class AutoDecision:
    active: str
    active_elapsed: float
    transitioning: bool = False
    incoming: str | None = None
    incoming_elapsed: float | None = None
    blend: float = 0.0


class AutoScheduler:
    def __init__(self, names: Sequence[str], *, interval: float, transition: float, shuffle: bool = False, seed: int = 1) -> None:
        if not names or interval <= 0 or transition < 0 or transition >= interval:
            raise ValueError("auto requires names and transition less than interval")
        self.names = list(names)
        if shuffle:
            random.Random(seed).shuffle(self.names)
        self.interval = interval
        self.transition = transition

    def decision(self, elapsed: float) -> AutoDecision:
        slot = int((elapsed + 1e-12) // self.interval)
        start = slot * self.interval
        active = self.names[slot % len(self.names)]
        active_elapsed = elapsed - (0.0 if slot == 0 else start - self.transition)
        local = elapsed - start
        if self.transition and local >= self.interval - self.transition - 1e-12:
            incoming_start = start + self.interval - self.transition
            return AutoDecision(active, active_elapsed, True, self.names[(slot + 1) % len(self.names)], elapsed - incoming_start, (elapsed - incoming_start) / self.transition)
        return AutoDecision(active, active_elapsed)

    def frame(self, elapsed: float, renderer_for: Callable[[str, float], RGBFrame], *, brightness: int) -> RGBFrame:
        choice = self.decision(elapsed)
        if choice.transitioning:
            assert choice.incoming is not None and choice.incoming_elapsed is not None
            frame = blend(renderer_for(choice.active, choice.active_elapsed), renderer_for(choice.incoming, choice.incoming_elapsed), choice.blend)
        else:
            frame = renderer_for(choice.active, choice.active_elapsed)
        frame.apply_brightness(brightness)
        return frame


def auto_duration(names: Sequence[str], *, interval: float, duration: float | None, cycles: int | None) -> float | None:
    return duration if duration is not None else (cycles * len(names) * interval if cycles is not None else None)
