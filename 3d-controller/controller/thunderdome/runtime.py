"""Source-neutral baseline/override arbitration for the control service."""
from __future__ import annotations

import enum
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Callable, Mapping, Protocol

from .schemas import validate_effect_parameters
from .effects.Registry import LEGACY_NAMES


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
    generation: str = field(default_factory=lambda: uuid.uuid4().hex)

    def as_dict(self, *, include_generation: bool = False) -> dict[str, object]:
        payload = {"effect": self.effect, "parameters": dict(self.parameters), "output": self.output.value, "source": self.source.value, "request_id": self.request_id, "created_at": self.created_at, "priority": self.priority, "expires_at": self.expires_at}
        if include_generation:
            payload["generation"] = self.generation
        return payload


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    reason: str | None
    status: Mapping[str, object]


class DisplayRuntime(Protocol):
    on_terminated: Callable[[DisplayDefinition, str | None, bool], None] | None
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
        self._active: DisplayDefinition | None = None
        self._notifications: deque[tuple[DisplayDefinition, str | None, bool]] = deque()
        self._notification_lock = threading.RLock()
        self._guard_depth = 0
        self._state = "idle"
        self._latest_error: str | None = None
        self.default_output = default_output
        self._runtime.on_terminated = self.runtime_terminated

    @contextmanager
    def _guard(self, *, blocking: bool = True):
        """Drain termination events without ever blocking a worker on a joiner.

        Publication and the outermost unlock are paired so a notification cannot
        miss both the worker's nonblocking drain and the command's final drain.
        """
        acquired = self._lock.acquire(blocking=blocking)
        if not acquired:
            yield False
            return
        self._guard_depth += 1
        try:
            if self._guard_depth == 1:
                self._drain_notifications()
            yield True
        finally:
            if self._guard_depth == 1:
                with self._notification_lock:
                    try:
                        self._drain_notifications()
                    finally:
                        self._guard_depth -= 1
                        self._lock.release()
            else:
                self._guard_depth -= 1
                self._lock.release()

    def runtime_terminated(self, display: DisplayDefinition, error: str | None, cancelled: bool) -> None:
        """Called after sink cleanup; display identity identifies one activation."""
        with self._notification_lock:
            self._notifications.append((display, error, cancelled))
        with self._guard(blocking=False):
            pass

    def _drain_notifications(self) -> None:
        while True:
            with self._notification_lock:
                if not self._notifications:
                    return
                display, error, cancelled = self._notifications.popleft()
            if display is not self._active:
                continue
            self._active = None
            self._state = "error" if error else "idle"
            if error:
                self._latest_error = error
            if cancelled:
                # A direct runtime stop is not natural completion. Retain the
                # configured baseline, but never claim its worker is running.
                self._override = None
                continue
            if self._override is not None and display.generation == self._override.generation:
                self._override = None
                try:
                    if self._baseline is not None:
                        self._start(self._baseline)
                except Exception as exc:
                    self._latest_error = str(exc)
            elif error is None:
                self._baseline = None

    def _definition(self, command: RuntimeCommand, *, inherited_output: OutputMode | None = None) -> DisplayDefinition:
        if command.effect is None:
            raise ValueError("effect is required")
        output = command.output or inherited_output or self.default_output
        if output is None:
            raise ValueError("output is required")
        effect = LEGACY_NAMES.get(command.effect, command.effect)
        parameters = validate_effect_parameters(effect, command.parameters)
        now = self._monotonic()
        return DisplayDefinition(effect, parameters, output, command.source, command.request_id, now, command.priority, now + command.duration_seconds if command.duration_seconds else None)

    def _start(self, display: DisplayDefinition | None) -> None:
        if display is None:
            self._state = "idle"
            return
        # A restored baseline has the same definition generation, but each
        # activation has a distinct object identity for completion ownership.
        active = replace(display)
        try:
            self._runtime.start(active)
        except Exception:
            self._active = None
            self._state = "error"
            raise
        self._active = active
        self._state = "running"

    def _replace_effective(self, display: DisplayDefinition | None) -> None:
        if self._active is not None:
            self._runtime.stop()
        self._active = None
        self._state = "idle"
        self._start(display)

    def _effective(self) -> DisplayDefinition | None:
        return self._active

    def _validate_source_policy(self, command: RuntimeCommand) -> None:
        allowed_sources = {
            CommandAction.SET_BASELINE: {CommandSource.BROWSER, CommandSource.CLI, CommandSource.SYSTEM},
            CommandAction.APPLY_OVERRIDE: {CommandSource.BROWSER, CommandSource.MQTT, CommandSource.SYSTEM},
            CommandAction.CANCEL_OVERRIDE: {CommandSource.BROWSER, CommandSource.MQTT, CommandSource.SYSTEM},
            CommandAction.RESTART_BASELINE: {CommandSource.BROWSER, CommandSource.CLI, CommandSource.SYSTEM},
            CommandAction.STOP_ALL: {CommandSource.BROWSER, CommandSource.CLI, CommandSource.SYSTEM},
            CommandAction.GET_STATUS: set(CommandSource),
        }
        if command.source not in allowed_sources.get(command.action, set()):
            raise ValueError(f"{command.source.value.upper()} may not perform {command.action.value}")
        if command.source == CommandSource.MQTT and command.action == CommandAction.APPLY_OVERRIDE:
            if command.duration_seconds is None:
                raise ValueError("MQTT override requires duration_seconds")
            if command.output is not None:
                raise ValueError("MQTT override must omit output")
            if self._baseline is None:
                raise ValueError("MQTT override requires a baseline output")

    def execute(self, command: RuntimeCommand) -> CommandResult:
        with self._guard():
            try:
                self._expire_locked()
                self._validate_source_policy(command)
                if command.action == CommandAction.SET_BASELINE:
                    candidate = self._definition(command)
                    if self._override is not None:
                        self._baseline = candidate
                    else:
                        self._replace_effective(candidate)
                        self._baseline = candidate
                elif command.action == CommandAction.APPLY_OVERRIDE:
                    inherited = self._baseline.output if self._baseline else None
                    candidate = self._definition(command, inherited_output=inherited)
                    if self._override is not None and candidate.priority < self._override.priority:
                        return CommandResult(False, "lower priority override rejected", self.status())
                    self._replace_effective(candidate)
                    self._override = candidate
                elif command.action == CommandAction.CANCEL_OVERRIDE:
                    if self._override is None:
                        return CommandResult(False, "no active override", self.status())
                    self._replace_effective(self._baseline)
                    self._override = None
                elif command.action == CommandAction.RESTART_BASELINE:
                    if self._baseline is None:
                        return CommandResult(False, "no baseline configured", self.status())
                    self._replace_effective(self._baseline)
                    self._override = None
                elif command.action == CommandAction.STOP_ALL:
                    self._replace_effective(None)
                    self._baseline = None
                    self._override = None
                elif command.action != CommandAction.GET_STATUS:
                    return CommandResult(False, "unsupported action", self.status())
            except Exception as exc:
                self._latest_error = str(exc)
                return CommandResult(False, str(exc), self.status())
            return CommandResult(True, None, self.status())

    def _expire_locked(self) -> bool:
        if self._override is not None and self._override.expires_at is not None and self._monotonic() >= self._override.expires_at:
            self._replace_effective(self._baseline)
            self._override = None
            return True
        return False

    def expire_overrides(self, generation: str | None = None) -> bool:
        with self._guard():
            if generation is not None and (self._override is None or self._override.generation != generation):
                return False
            return self._expire_locked()

    def status(self) -> dict[str, object]:
        return self._status(include_generation=False)

    def internal_status(self) -> dict[str, object]:
        """Return status with activation identity for internal timer ownership."""
        return self._status(include_generation=True)

    def _status(self, *, include_generation: bool) -> dict[str, object]:
        with self._guard():
            self._drain_notifications()
            try:
                self._expire_locked()
            except Exception as exc:
                self._latest_error = str(exc)
            self._drain_notifications()
            effective = self._effective()
            remaining = None
            if self._override and self._override.expires_at is not None:
                remaining = max(0.0, self._override.expires_at - self._monotonic())
            as_dict = lambda display: display.as_dict(include_generation=include_generation) if display else None
            return {"service_state": self._state, "baseline": as_dict(self._baseline), "override": as_dict(self._override), "effective": as_dict(effective), "remaining_override_seconds": remaining, "latest_error": self._latest_error}
