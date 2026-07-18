"""Source-neutral baseline/override arbitration for the control service."""
from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from .schemas import validate_effect_parameters


class CommandSource(enum.StrEnum):
    BROWSER = "browser"
    MQTT = "mqtt"
    CLI = "cli"
    SYSTEM = "system"


class CommandAction(enum.StrEnum):
    SET_BASELINE = "set_baseline"
    APPLY_OVERRIDE = "apply_override"
    CANCEL_OVERRIDE = "cancel_override"
    STOP_ALL = "stop_all"
    RESTART_BASELINE = "restart_baseline"
    GET_STATUS = "get_status"


class OutputMode(enum.StrEnum):
    SIMULATOR = "simulator"
    DDP = "ddp"
    BOTH = "both"
    NULL = "null"


@dataclass(frozen=True)
class RuntimeCommand:
    source: CommandSource
    action: CommandAction
    request_id: str
    effect: str | None
    parameters: Mapping[str, object]
    output: OutputMode | None
    priority: int = 0
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", dict(self.parameters))
        if not self.request_id:
            raise ValueError("request_id is required")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.duration_seconds is not None and self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")


@dataclass(frozen=True)
class DisplayDefinition:
    effect: str
    parameters: Mapping[str, object]
    output: OutputMode
    source: CommandSource
    request_id: str
    created_at: float
    priority: int = 0
    expires_at: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {"effect": self.effect, "parameters": dict(self.parameters), "output": self.output.value, "source": self.source.value, "request_id": self.request_id, "created_at": self.created_at, "priority": self.priority, "expires_at": self.expires_at}


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    reason: str | None
    status: Mapping[str, object]


class DisplayRuntime(Protocol):
    def start(self, display: DisplayDefinition) -> None: ...
    def stop(self) -> None: ...


class RuntimeCoordinator:
    """Serializes command arbitration; callers own no rendering loops or sinks."""

    def __init__(self, runtime: DisplayRuntime, *, monotonic: Callable[[], float] = time.monotonic, default_output: OutputMode | None = None) -> None:
        self._runtime = runtime
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._baseline: DisplayDefinition | None = None
        self._override: DisplayDefinition | None = None
        self._state = "idle"
        self._latest_error: str | None = None
        self.default_output = default_output

    def _definition(self, command: RuntimeCommand, *, inherited_output: OutputMode | None = None) -> DisplayDefinition:
        if command.effect is None:
            raise ValueError("effect is required")
        output = command.output or inherited_output or self.default_output
        if output is None:
            raise ValueError("output is required")
        parameters = validate_effect_parameters(command.effect, command.parameters)
        now = self._monotonic()
        return DisplayDefinition(command.effect, parameters, output, command.source, command.request_id, now, command.priority, now + command.duration_seconds if command.duration_seconds else None)

    def _start(self, display: DisplayDefinition | None) -> None:
        if display is None:
            self._state = "idle"
            return
        self._runtime.start(display)
        self._state = "running"

    def _replace_effective(self, display: DisplayDefinition | None) -> None:
        if self._state != "idle":
            self._runtime.stop()
        self._start(display)

    def _effective(self) -> DisplayDefinition | None:
        return self._override or self._baseline

    def execute(self, command: RuntimeCommand) -> CommandResult:
        with self._lock:
            self._expire_locked()
            try:
                if command.action == CommandAction.SET_BASELINE:
                    candidate = self._definition(command)
                    self._baseline = candidate
                    self._replace_effective(self._override or candidate)
                elif command.action == CommandAction.APPLY_OVERRIDE:
                    inherited = self._baseline.output if self._baseline else None
                    candidate = self._definition(command, inherited_output=inherited)
                    if self._override is not None and candidate.priority < self._override.priority:
                        return CommandResult(False, "lower priority override rejected", self.status())
                    self._override = candidate
                    self._replace_effective(candidate)
                elif command.action == CommandAction.CANCEL_OVERRIDE:
                    if self._override is None:
                        return CommandResult(False, "no active override", self.status())
                    self._override = None
                    self._replace_effective(self._baseline)
                elif command.action == CommandAction.RESTART_BASELINE:
                    if self._baseline is None:
                        return CommandResult(False, "no baseline configured", self.status())
                    self._override = None
                    self._replace_effective(self._baseline)
                elif command.action == CommandAction.STOP_ALL:
                    self._baseline = None
                    self._override = None
                    self._replace_effective(None)
                elif command.action != CommandAction.GET_STATUS:
                    return CommandResult(False, "unsupported action", self.status())
            except (ValueError, OSError) as exc:
                self._latest_error = str(exc)
                return CommandResult(False, str(exc), self.status())
            return CommandResult(True, None, self.status())

    def _expire_locked(self) -> bool:
        if self._override is not None and self._override.expires_at is not None and self._monotonic() >= self._override.expires_at:
            self._override = None
            self._replace_effective(self._baseline)
            return True
        return False

    def expire_overrides(self) -> bool:
        with self._lock:
            return self._expire_locked()

    def complete_baseline(self, request_id: str) -> bool:
        """Clear a naturally completed finite baseline if it is still current."""
        with self._lock:
            if self._baseline is None or self._baseline.request_id != request_id:
                return False
            self._baseline = None
            if self._override is None:
                self._state = "idle"
            return True

    def status(self) -> dict[str, object]:
        with self._lock:
            self._expire_locked()
            effective = self._effective()
            remaining = None
            if self._override and self._override.expires_at is not None:
                remaining = max(0.0, self._override.expires_at - self._monotonic())
            return {"service_state": self._state, "baseline": self._baseline.as_dict() if self._baseline else None, "override": self._override.as_dict() if self._override else None, "effective": effective.as_dict() if effective else None, "remaining_override_seconds": remaining, "latest_error": self._latest_error}
