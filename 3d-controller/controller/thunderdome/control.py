"""Local-only Stage C1 control APIs and the single cooperative frame worker."""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from aiohttp import web

from .animation.loop import run_frame_loop
from .effects.common import SpatialContext, parse_spatial_origin
from .effects.clock_hand import angle_for_elapsed, render_clock_hand
from .effects.expanding_rings import render_expanding_rings
from .effects.height_wave import render_height_wave
from .effects.procedural import create_renderer
from .effects.registry import BY_NAME
from .frame import RGBFrame
from .runtime import CommandAction, CommandSource, DisplayDefinition, OutputMode, RuntimeCommand, RuntimeCoordinator
from .schemas import EFFECT_SCHEMAS, validate_effect_parameters
from .sinks import CompositeFrameSink, DDPFrameSink, FrameSink, NullFrameSink, SimulatorFrameSink


@dataclass(frozen=True)
class ControlSettings:
    simulator_url: str
    controllers_path: str | None = None
    live_control_enabled: bool = False

    @property
    def live_available(self) -> bool:
        return self.live_control_enabled and self.controllers_path is not None


class FrameRuntime:
    """One cancellable worker thread; all selected sinks live inside that worker."""
    def __init__(self, settings: ControlSettings, producer_factory: Callable[[DisplayDefinition], tuple[Callable[[int, float], RGBFrame], int]] | None = None) -> None:
        self.settings = settings
        self.producer_factory = producer_factory or make_effect_producer
        self._lock = threading.RLock()
        self._cancel: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self.frames = 0
        self.active_since: float | None = None
        self.error: str | None = None

    def _sink(self, output: OutputMode) -> FrameSink:
        if output == OutputMode.NULL:
            return NullFrameSink()
        if output == OutputMode.SIMULATOR:
            return SimulatorFrameSink(self.settings.simulator_url)
        if not self.settings.live_available:
            raise ValueError("live DDP output is not enabled by this control service")
        assert self.settings.controllers_path is not None
        ddp = DDPFrameSink(self.settings.controllers_path)
        return ddp if output == OutputMode.DDP else CompositeFrameSink([SimulatorFrameSink(self.settings.simulator_url), ddp])

    def start(self, display: DisplayDefinition) -> None:
        self.stop()
        cancel = threading.Event()
        with self._lock:
            self._cancel = cancel
            self.frames = 0
            self.error = None
            self.active_since = time.monotonic()
            self._thread = threading.Thread(target=self._run, args=(display, cancel), name="thunderdome-control-runtime", daemon=True)
            self._thread.start()

    def _run(self, display: DisplayDefinition, cancel: threading.Event) -> None:
        try:
            producer, fps = self.producer_factory(display)
            with self._sink(display.output) as sink:
                def send(frame: RGBFrame) -> None:
                    result = sink.send_frame(frame)
                    if not result.ok:
                        raise OSError(f"{result.name}: {result.error or 'delivery failed'}")
                    with self._lock:
                        self.frames += 1
                run_frame_loop(producer, send, fps=fps, cancel_event=cancel)
        except (OSError, ValueError) as exc:
            with self._lock:
                self.error = str(exc)
        finally:
            with self._lock:
                if self._cancel is cancel:
                    self._cancel = None
                    self.active_since = None

    def stop(self) -> None:
        with self._lock:
            cancel, thread = self._cancel, self._thread
        if cancel is not None:
            cancel.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self._lock:
            if self._thread is thread:
                self._thread = None

    def shutdown(self) -> None:
        self.stop()


def make_effect_producer(display: DisplayDefinition) -> tuple[Callable[[int, float], RGBFrame], int]:
    values = dict(display.parameters)
    context = SpatialContext.load(values.pop("positions", None) or Path(__file__).resolve().parents[2] / "geometry/generated/led_positions_3d.json", values.pop("geometry", None) or Path(__file__).resolve().parents[2] / "geometry/thunderdome_geometry.json")
    brightness = int(values.pop("brightness", 255)); fps = int(values.pop("fps", 30)); exclude_tail = bool(values.pop("exclude_tail", False))
    if display.effect == "auto":
        names = list(values["effects"]); interval = float(values["interval"]); transition = float(values["transition"]); seed = int(values["seed"])
        renderers = {name: create_renderer(name, context, brightness=255, exclude_tail=exclude_tail, seed=seed, **{k: v for k, v in dict(display.parameters).items() if k not in {"brightness", "fps", "exclude_tail", "effects", "interval", "transition", "cycles", "shuffle", "seed"}}) for name in names if BY_NAME[name].category == "procedural"}
        def auto(_number: int, elapsed: float) -> RGBFrame:
            index = int(elapsed // interval) % len(names); name = names[index]
            if name in renderers: frame = renderers[name].render(elapsed)
            else: frame = _spatial_frame(name, context, elapsed, brightness=255, exclude_tail=exclude_tail, values=validate_effect_parameters(name))
            frame.apply_brightness(brightness); return frame
        return auto, fps
    if BY_NAME[display.effect].category == "procedural":
        renderer = create_renderer(display.effect, context, brightness=brightness, exclude_tail=exclude_tail, seed=int(values.pop("seed", 1)), **values)
        return lambda _number, elapsed: renderer.render(elapsed), fps
    return lambda _number, elapsed: _spatial_frame(display.effect, context, elapsed, brightness=brightness, exclude_tail=exclude_tail, values=values), fps


def _spatial_frame(effect: str, context: SpatialContext, elapsed: float, *, brightness: int, exclude_tail: bool, values: dict[str, object]) -> RGBFrame:
    if effect == "clock-hand":
        return render_clock_hand(context.positions, angle_radians=angle_for_elapsed(elapsed, rotation_seconds=float(values["rotation_seconds"]), direction=str(values["direction"]), offset_degrees=float(values["angle_offset_degrees"])), width_m=float(values["width_mm"]) / 1000, color=tuple(int(values["color"][i:i+2], 16) for i in (0, 2, 4)), background=tuple(int(values["background"][i:i+2], 16) for i in (0, 2, 4)), brightness=brightness, center_xy=context.apex[:2], exclude_tail=exclude_tail)
    if effect == "expanding-rings":
        return render_expanding_rings(context, elapsed_seconds=elapsed, speed_m_per_s=float(values["speed_mps"]), thickness_m=float(values["thickness_mm"]) / 1000, origin=parse_spatial_origin(str(values["origin"]), context), color=tuple(int(values["color"][i:i+2], 16) for i in (0, 2, 4)), background=tuple(int(values["background"][i:i+2], 16) for i in (0, 2, 4)), brightness=brightness, exclude_tail=exclude_tail)
    return render_height_wave(context, elapsed_seconds=elapsed, speed_m_per_s=float(values["speed_mps"]), height_m=float(values["height_mm"]) / 1000, direction=str(values["direction"]), color=tuple(int(values["color"][i:i+2], 16) for i in (0, 2, 4)), background=tuple(int(values["background"][i:i+2], 16) for i in (0, 2, 4)), brightness=brightness, exclude_tail=exclude_tail)


class ControlAPI:
    def __init__(self, settings: ControlSettings, runtime: FrameRuntime | None = None) -> None:
        self.settings = settings
        self.runtime = runtime or FrameRuntime(settings)
        self.coordinator = RuntimeCoordinator(self.runtime)

    def register_routes(self, app: web.Application) -> None:
        app.router.add_get("/api/control/capabilities", self.capabilities)
        app.router.add_get("/api/effects", self.effects)
        app.router.add_get("/api/effects/{name}", self.effect)
        app.router.add_get("/api/runtime/status", self.status)
        app.router.add_post("/api/runtime/baseline", self.command)
        app.router.add_post("/api/runtime/override", self.command)
        app.router.add_post("/api/runtime/cancel-override", self.command)
        app.router.add_post("/api/runtime/restart-baseline", self.command)
        app.router.add_post("/api/runtime/stop", self.command)

    def capabilities_payload(self) -> dict[str, object]:
        return {"service_mode": "control", "simulator_available": True, "live_ddp_available": self.settings.live_available, "both_available": self.settings.live_available, "controller_config_loaded": self.settings.controllers_path is not None, "live_control_enabled": self.settings.live_control_enabled, "supported_outputs": ["simulator"] + (["ddp", "both"] if self.settings.live_available else []), "brightness_default": 255, "effect_count": len(EFFECT_SCHEMAS), "auto_mode_available": True, "mqtt_configured": False}

    async def capabilities(self, request: web.Request) -> web.Response:
        return web.json_response(self.capabilities_payload())

    async def effects(self, request: web.Request) -> web.Response:
        return web.json_response({"effects": [schema.as_dict() for schema in EFFECT_SCHEMAS.values()]})

    async def effect(self, request: web.Request) -> web.Response:
        schema = EFFECT_SCHEMAS.get(request.match_info["name"])
        if schema is None:
            return web.json_response({"error": "unknown effect"}, status=404)
        return web.json_response(schema.as_dict())

    async def status(self, request: web.Request) -> web.Response:
        payload = self.coordinator.status(); payload.update({"rendered_frames": self.runtime.frames, "active_since": self.runtime.active_since, "latest_sink_error": self.runtime.error})
        return web.json_response(payload)

    async def command(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            action = {"/api/runtime/baseline": CommandAction.SET_BASELINE, "/api/runtime/override": CommandAction.APPLY_OVERRIDE, "/api/runtime/cancel-override": CommandAction.CANCEL_OVERRIDE, "/api/runtime/restart-baseline": CommandAction.RESTART_BASELINE, "/api/runtime/stop": CommandAction.STOP_ALL}[request.path]
            output = payload.get("output")
            parsed_output = OutputMode(output) if output is not None else None
            if parsed_output in {OutputMode.DDP, OutputMode.BOTH} and not self.settings.live_available:
                raise ValueError("live DDP output is not enabled")
            command = RuntimeCommand(CommandSource.BROWSER, action, str(payload.get("request_id") or uuid.uuid4()), payload.get("effect"), payload.get("parameters", {}), parsed_output, int(payload.get("priority", 0)), payload.get("duration_seconds"))
            result = self.coordinator.execute(command)
            if result.accepted and action == CommandAction.APPLY_OVERRIDE and command.duration_seconds is not None:
                timer = threading.Timer(command.duration_seconds, self.coordinator.expire_overrides)
                timer.daemon = True
                timer.start()
            return web.json_response({"accepted": result.accepted, "reason": result.reason, "status": result.status}, status=200 if result.accepted else 409)
        except (TypeError, ValueError) as exc:
            return web.json_response({"accepted": False, "error": str(exc)}, status=400)

    def shutdown(self) -> None:
        self.runtime.shutdown()
