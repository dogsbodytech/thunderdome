"""Reusable best-effort WLED JSON fan-out."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from ..controllers import ControllerSet
from .client import WLEDClient

@dataclass(frozen=True)
class WLEDOperationResult:
    controller_number: int
    host: str
    value: Any = None
    error: str | None = None

def run_wled_operation(
    controllers: ControllerSet,
    operation: Callable[[WLEDClient], Any],
    *, client_factory: Callable[[str], WLEDClient] = WLEDClient,
) -> list[WLEDOperationResult]:
    results=[]
    for controller in controllers.controllers:
        if not controller.enabled: continue
        try: results.append(WLEDOperationResult(controller.controller_number, controller.host, operation(client_factory(controller.host))))
        except Exception as exc: results.append(WLEDOperationResult(controller.controller_number, controller.host, error=str(exc)))
    return results
