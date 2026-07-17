"""CLI for controller management, geometry validation, and direct DDP frames."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Sequence

from .animation.loop import FrameLoopStats, run_frame_loop
from .config import CONTROLLER_LED_COUNT, DDP_CHUNK_LEDS, DDP_PORT, GEOMETRY_PATH, LED_POSITIONS_PATH, LOGICAL_LED_COUNT
from .controllers import load_controllers
from .effects.clock_hand import angle_for_elapsed, render_clock_hand
from .effects.common import SpatialContext, distance3, parse_spatial_origin, selected_xyz
from .effects.expanding_rings import render_expanding_rings
from .effects.height_wave import render_height_wave
from .effects.procedural import blend, create_renderer, render as render_procedural
from .effects.registry import BY_NAME, DEFAULT_PLAYLIST, PRESETS
from .frame import RGBFrame
from .geometry import load_geometry
from .led_positions import generate_positions, load_led_positions, write_positions
from .routes import generate_route_document, load_routes, write_route_document
from .transport.ddp import DirectDDPSession, parse_hex_color, send_frame
from .transport.multi_ddp import MultiControllerDDPSession, SendResult
from .wled.client import WLEDApiError, WLEDClient
from .wled.multi import WLEDOperationResult, run_wled_operation


@dataclass(frozen=True)
class LoopOptions:
    hold: bool
    duration: float | None
    loops: int | None
    fps: int

    @property
    def enabled(self) -> bool:
        return self.hold or self.duration is not None or self.loops is not None

    @property
    def description(self) -> str:
        if self.hold:
            return "hold until Ctrl+C"
        if self.duration is not None:
            return f"duration {self.duration:g}s"
        return f"{self.loops} loops"


def _host(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True, help="WLED host or URL")


def _add_loop_options(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hold", action="store_true", help="resend until Ctrl+C")
    mode.add_argument("--duration", type=float, help="resend for this many seconds")
    mode.add_argument("--loops", type=int, help="resend exactly this many frames")
    parser.add_argument("--fps", type=int, default=20, help="frame rate for held/looped output (1..60; default: 20)")


def _ddp_options(parser: argparse.ArgumentParser, *, colour: bool = False) -> None:
    _host(parser)
    parser.add_argument(
        "--led-count",
        type=int,
        default=CONTROLLER_LED_COUNT,
        help=f"LEDs on this controller (default: {CONTROLLER_LED_COUNT})",
    )
    parser.add_argument("--port", type=int, default=DDP_PORT)
    parser.add_argument("--chunk-leds", type=int, default=DDP_CHUNK_LEDS)
    if colour:
        parser.add_argument("--color", default="FFFFFF")
        parser.add_argument("--brightness", type=int, default=64)
    _add_loop_options(parser)


def _controllers_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--controllers", default=str(GEOMETRY_PATH.parent.parent / "config" / "controllers.json"))


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return parsed


def _add_spatial_effect_options(parser: argparse.ArgumentParser) -> None:
    _controllers_option(parser)
    parser.add_argument("--positions", default=str(LED_POSITIONS_PATH))
    parser.add_argument("--geometry", default=str(GEOMETRY_PATH))
    parser.add_argument("--color", default="FFFFFF")
    parser.add_argument("--background", default="000000")
    parser.add_argument("--brightness", type=int, default=32)
    parser.add_argument("--speed-mps", type=float, default=0.5, help="movement speed in metres per second")
    parser.add_argument("--exclude-tail", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hold", action="store_true")
    mode.add_argument("--duration", type=float)
    mode.add_argument("--loops", type=_positive_int, help="complete spatial movement cycles")
    parser.add_argument("--fps", type=int, default=30)


def _add_effect_runtime_options(parser: argparse.ArgumentParser, *, loops: bool = False) -> None:
    _controllers_option(parser)
    parser.add_argument("--positions", default=str(LED_POSITIONS_PATH))
    parser.add_argument("--geometry", default=str(GEOMETRY_PATH))
    parser.add_argument("--brightness", type=int, default=32)
    parser.add_argument("--exclude-tail", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hold", action="store_true")
    mode.add_argument("--duration", type=float)
    if loops:
        mode.add_argument("--loops", type=_positive_int, help="complete effect cycles")
    parser.add_argument("--fps", type=int, default=30)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="thunderdome", description=__doc__)
    groups = parser.add_subparsers(dest="area", required=True)

    controller = groups.add_parser("controller", help="Secondary WLED HTTP management commands")
    controller_sub = controller.add_subparsers(dest="command", required=True)
    for command in ("info", "state"):
        item = controller_sub.add_parser(command)
        _host(item)
    for name in ("power", "live"):
        item = controller_sub.add_parser(name)
        _host(item); item.add_argument("state", choices=("on", "off"))
    brightness = controller_sub.add_parser("brightness"); _host(brightness); brightness.add_argument("value", type=int)
    color = controller_sub.add_parser("color"); _host(color); color.add_argument("color")
    for plural in ("effects", "palettes"):
        item = controller_sub.add_parser(plural); _host(item)
    for name in ("effect", "palette"):
        item = controller_sub.add_parser(name); _host(item); item.add_argument("value", type=int)
    preset = controller_sub.add_parser("preset"); _host(preset); preset.add_argument("preset_id", type=int)
    prepare = controller_sub.add_parser("prepare-ddp"); _host(prepare)


    ddp = groups.add_parser("ddp", help="Primary direct RGB frame transport")
    ddp_sub = ddp.add_subparsers(dest="command", required=True)
    _ddp_options(ddp_sub.add_parser("clear"))
    _ddp_options(ddp_sub.add_parser("solid"), colour=True)
    pixel = ddp_sub.add_parser("pixel")
    _ddp_options(pixel, colour=True)
    pixel.add_argument("index", type=int)
    span = ddp_sub.add_parser("range")
    _ddp_options(span, colour=True)
    span.add_argument("start", type=int)
    span.add_argument("count", type=int)

    geometry = groups.add_parser("geometry", help="Validate structural geometry")
    geometry_sub = geometry.add_subparsers(dest="command", required=True)
    validate = geometry_sub.add_parser("validate")
    validate.add_argument("--path", default=str(GEOMETRY_PATH))

    route = groups.add_parser("route", help="Generate and validate authoritative manual routes")
    route_sub = route.add_subparsers(dest="command", required=True)
    for name in ("generate", "validate", "summary"):
        item = route_sub.add_parser(name)
        item.add_argument("--route-path", default=str(GEOMETRY_PATH.parent / "reference_string_route.md"))
        item.add_argument("--geometry-path", default=str(GEOMETRY_PATH))
        item.add_argument("--output", default=str(GEOMETRY_PATH.parent / "routes/string_routes.json"))

    positions = groups.add_parser("positions", help="Generate and validate nominal XYZ positions")
    positions_sub = positions.add_subparsers(dest="command", required=True)
    for name in ("generate", "validate", "summary"):
        item = positions_sub.add_parser(name)
        item.add_argument("--route-path", default=str(GEOMETRY_PATH.parent / "reference_string_route.md"))
        item.add_argument("--geometry-path", default=str(GEOMETRY_PATH))
        item.add_argument("--path", default=str(GEOMETRY_PATH.parent / "generated/led_positions_3d.json"))

    controllers = groups.add_parser("controllers", help="Multi-controller configuration and HTTP commands")
    controllers_sub = controllers.add_subparsers(dest="command", required=True)
    for name in ("validate", "summary"):
        item = controllers_sub.add_parser(name)
        _controllers_option(item)
    for name in ("state", "power", "live", "brightness", "color", "effect", "palette", "preset", "prepare-ddp"):
        item = controllers_sub.add_parser(name); _controllers_option(item)
        if name in {"power", "live"}: item.add_argument("state", choices=("on", "off"))
        elif name == "brightness": item.add_argument("value", type=int)
        elif name in {"color"}: item.add_argument("color")
        elif name in {"effect", "palette"}: item.add_argument("value", type=int)
        elif name == "preset": item.add_argument("preset_id", type=int)

    effect = groups.add_parser("effect", help="Application-rendered spatial DDP effects")
    effect_sub = effect.add_subparsers(dest="command", required=True)
    clock = effect_sub.add_parser("clock-hand", help="render a rotating radial hand through DDP")
    _controllers_option(clock)
    clock.add_argument("--positions", default=str(LED_POSITIONS_PATH)); clock.add_argument("--geometry", default=str(GEOMETRY_PATH))
    clock.add_argument("--color", default="FFFFFF"); clock.add_argument("--background", default="000000")
    clock.add_argument("--brightness", type=int, default=32); clock.add_argument("--width-mm", type=float, default=300)
    clock.add_argument("--rotation-seconds", type=float, default=3); clock.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise")
    clock.add_argument("--angle-offset-degrees", type=float, default=0); clock.add_argument("--exclude-tail", action="store_true"); clock.add_argument("--dry-run", action="store_true")
    mode=clock.add_mutually_exclusive_group(); mode.add_argument("--hold", action="store_true"); mode.add_argument("--duration", type=float); mode.add_argument("--rotations", type=int)
    clock.add_argument("--fps", type=int, default=30)
    rings = effect_sub.add_parser("expanding-rings", help="render an expanding XYZ spherical shell through DDP")
    _add_spatial_effect_options(rings)
    rings.add_argument("--origin", default="apex", metavar="apex|centre|base|X,Y,Z")
    rings.add_argument("--thickness-mm", type=float, default=200)
    wave = effect_sub.add_parser("height-wave", help="render a moving horizontal height band through DDP")
    _add_spatial_effect_options(wave)
    wave.add_argument("--direction", choices=("up", "down", "bounce"), default="up")
    wave.add_argument("--height-mm", type=float, default=200)
    auto = effect_sub.add_parser("auto", help="cycle the registry playlist with crossfades")
    _controllers_option(auto)
    auto.add_argument("--positions", default=str(LED_POSITIONS_PATH)); auto.add_argument("--geometry", default=str(GEOMETRY_PATH))
    auto.add_argument("--effects", "--playlist", dest="effects"); auto.add_argument("--preset", choices=tuple(PRESETS))
    auto.add_argument("--interval", type=float, default=30); auto.add_argument("--transition", "--crossfade", dest="transition", type=float, default=2)
    auto.add_argument("--shuffle", action="store_true"); auto.add_argument("--seed", type=int, default=1)
    mode=auto.add_mutually_exclusive_group(); mode.add_argument("--duration", type=float); mode.add_argument("--loops", "--cycles", dest="cycles", type=_positive_int)
    auto.add_argument("--brightness", type=int, default=32); auto.add_argument("--fps", type=int, default=30); auto.add_argument("--exclude-tail", action="store_true"); auto.add_argument("--dry-run", action="store_true")

    fire = effect_sub.add_parser("fire", help="render rising turbulent XYZ flames")
    _add_effect_runtime_options(fire)
    fire.add_argument("--speed", type=float, default=1.0); fire.add_argument("--flame-height-m", type=float, default=2.5); fire.add_argument("--turbulence", type=float, default=.65); fire.add_argument("--cooling", type=float, default=.35); fire.add_argument("--scale", type=float, default=1.0); fire.add_argument("--palette", default="fire"); fire.add_argument("--seed", type=int, default=1)

    plane = effect_sub.add_parser("rotating-plane", help="render a rotating signed-distance plane")
    _add_effect_runtime_options(plane, loops=True)
    plane.add_argument("--axis", default="vertical", metavar="vertical|horizontal|tilted|X,Y,Z", help="rotation axis: vertical=(0,0,1), horizontal=(1,0,0), tilted=normalize(1,1,1), or explicit X,Y,Z"); plane.add_argument("--rotation-seconds", type=float, default=10); plane.add_argument("--thickness-mm", type=float, default=220); plane.add_argument("--color", default="FFFFFF"); plane.add_argument("--background", default="000000"); plane.add_argument("--trail-degrees", type=float, default=20); plane.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise"); plane.add_argument("--seed", type=int, default=1)

    radar = effect_sub.add_parser("radar", help="render a rotating XY radar beam")
    _add_effect_runtime_options(radar, loops=True)
    radar.add_argument("--rotation-seconds", type=float, default=8); radar.add_argument("--beam-width-degrees", type=float, default=12); radar.add_argument("--trail-degrees", type=float, default=35); radar.add_argument("--range-m", type=float, default=9999); radar.add_argument("--vertical-falloff", type=float, default=0); radar.add_argument("--color", default="00FF80"); radar.add_argument("--background", default="000000"); radar.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise"); radar.add_argument("--seed", type=int, default=1)

    aurora = effect_sub.add_parser("aurora", help="render flowing luminous XYZ bands")
    _add_effect_runtime_options(aurora)
    aurora.add_argument("--speed", type=float, default=.25); aurora.add_argument("--scale", type=float, default=1.2); aurora.add_argument("--band-width", type=float, default=.45); aurora.add_argument("--intensity", type=float, default=1); aurora.add_argument("--palette", default="mixed"); aurora.add_argument("--direction", default="1,0,0"); aurora.add_argument("--seed", type=int, default=1)

    flies = effect_sub.add_parser("fireflies", help="render deterministic 3D glowing particles")
    _add_effect_runtime_options(flies)
    flies.add_argument("--count", type=_positive_int, default=25); flies.add_argument("--speed", type=float, default=.35); flies.add_argument("--glow-radius-mm", type=float, default=300); flies.add_argument("--lifetime-seconds", type=float, default=8); flies.add_argument("--color", default="FFFFB0"); flies.add_argument("--color-variation", type=float, default=.25); flies.add_argument("--seed", type=int, default=1)

    all_ddp = groups.add_parser(
        "ddp-all",
        help=f"Fan one logical {LOGICAL_LED_COUNT:,}-pixel frame out to all controllers",
    )
    all_sub = all_ddp.add_subparsers(dest="command", required=True)
    for name in ("clear", "solid", "controller-colors"):
        item = all_sub.add_parser(name)
        _controllers_option(item)
        item.add_argument("--dry-run", action="store_true")
        item.add_argument("--brightness", type=int, default=16)
        item.add_argument("--color", default="FFFFFF")
        _add_loop_options(item)

    return parser.parse_args(argv)


def _colour(args: argparse.Namespace) -> tuple[int, int, int]:
    rgb = parse_hex_color(args.color)
    if not 0 <= args.brightness <= 255:
        raise ValueError("brightness must be in range 0..255")
    return tuple(channel * args.brightness // 255 for channel in rgb)


def _loop_options(args: argparse.Namespace, *, dry_run: bool = False) -> LoopOptions:
    options = LoopOptions(args.hold, args.duration, args.loops, args.fps)
    if not 1 <= options.fps <= 60:
        raise ValueError("fps must be in range 1..60")
    if options.duration is not None and options.duration <= 0:
        raise ValueError("duration must be greater than zero")
    if options.loops is not None and options.loops <= 0:
        raise ValueError("loops must be a positive integer")
    if dry_run and options.enabled:
        raise ValueError("dry-run cannot be combined with --hold, --duration, or --loops")
    return options


def _report_loop(stats: FrameLoopStats) -> None:
    state = "Interrupted" if stats.interrupted else "Completed"
    print(f"{state}: {stats.frames_sent} frames sent in {stats.elapsed_seconds:.2f}s")


def _report_results(results: list[SendResult]) -> None:
    for result in results:
        suffix = f" error={result.error}" if result.error else ""
        print(f"controller {result.controller_number} {result.host}: {result.packets} packets{suffix}")


def _record_controller_failures(
    failed_controllers: dict[int, SendResult], results: list[SendResult]
) -> None:
    """Keep the first failure for each controller across a DDP command."""
    for result in results:
        if result.error:
            failed_controllers.setdefault(result.controller_number, result)


def _report_persistent_failures(failed_controllers: dict[int, SendResult]) -> None:
    if failed_controllers:
        print("Controller failures during DDP output:")
        _report_results(list(failed_controllers.values()))


def _run_single_ddp(args: argparse.Namespace) -> int:
    frame = RGBFrame.allocate(args.led_count)
    if args.command == "solid":
        frame.fill(_colour(args))
    elif args.command == "pixel":
        frame.set_pixel(args.index, _colour(args))
    elif args.command == "range":
        frame.set_range(args.start, args.count, _colour(args))

    options = _loop_options(args)
    if not options.enabled:
        packets = send_frame(args.host, frame.data, port=args.port, chunk_leds=args.chunk_leds)
        print(f"Sent DDP {args.command} frame to {args.host}:{args.port} ({args.led_count} LEDs, {packets} packets)")
        return 0

    print(
        f"Starting DDP {args.command} to {args.host}:{args.port} "
        f"({args.led_count} LEDs, {options.fps} FPS, {options.description})"
    )
    with DirectDDPSession(args.host, port=args.port, chunk_leds=args.chunk_leds) as session:
        stats = run_frame_loop(
            lambda _frame_number, _elapsed: frame.data,
            session.send,
            fps=options.fps,
            duration=options.duration,
            loops=options.loops,
        )
    _report_loop(stats)
    return 0


def _run_multi_ddp(args: argparse.Namespace) -> int:
    options = _loop_options(args, dry_run=args.dry_run)
    controllers = load_controllers(args.controllers)
    frame = RGBFrame.allocate(LOGICAL_LED_COUNT)
    if args.command == "solid":
        frame.fill(_colour(args))
    elif args.command == "controller-colors":
        colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255))
        for controller, color in zip(controllers.controllers, colors):
            frame.set_range(
                controller.global_start,
                CONTROLLER_LED_COUNT,
                tuple(channel * args.brightness // 255 for channel in color),
            )

    if not options.enabled:
        with MultiControllerDDPSession(controllers) as session:
            results = session.send_frame(frame, dry_run=args.dry_run)
        _report_results(results)
        return 1 if any(result.error for result in results) else 0

    print(f"Starting DDP-all {args.command} ({options.fps} FPS, {options.description})")
    last_results: list[SendResult] = []
    failed_controllers: dict[int, SendResult] = {}

    def send(current_frame: RGBFrame) -> None:
        nonlocal last_results
        last_results = session.send_frame(current_frame)
        _record_controller_failures(failed_controllers, last_results)

    with MultiControllerDDPSession(controllers) as session:
        stats = run_frame_loop(
            lambda _frame_number, _elapsed: frame,
            send,
            fps=options.fps,
            duration=options.duration,
            loops=options.loops,
        )
    _report_results(last_results)
    _report_persistent_failures(failed_controllers)
    _report_loop(stats)
    return 1 if failed_controllers else 0


def _wled_operation(args: argparse.Namespace, client: WLEDClient):
    if args.command == "state": return client.get_state()
    if args.command == "power": return client.set_power(args.state == "on")
    if args.command == "brightness": return client.set_brightness(args.value)
    if args.command == "color": return client.set_color(parse_hex_color(args.color))
    if args.command == "effect": return client.set_effect(args.value)
    if args.command == "palette": return client.set_palette(args.value)
    if args.command == "preset": return client.set_preset(args.preset_id)
    if args.command == "live": return client.set_live(args.state == "on")
    if args.command == "prepare-ddp": return client.prepare_ddp()
    raise ValueError(f"unsupported WLED operation {args.command}")

def _run_multi_wled(args: argparse.Namespace) -> int:
    results=run_wled_operation(load_controllers(args.controllers), lambda client: _wled_operation(args, client), client_factory=WLEDClient)
    for result in results:
        if result.error: print(f"controller {result.controller_number} {result.host}: {args.command} failed: {result.error}", file=sys.stderr)
        else: print(f"controller {result.controller_number} {result.host}: {args.command} ok" + (f" {json.dumps(result.value, sort_keys=True)}" if args.command == "state" else ""))
    return 1 if any(result.error for result in results) else 0

def _run_clock_hand(args: argparse.Namespace) -> int:
    if not 1 <= args.fps <= 60: raise ValueError("fps must be in range 1..60")
    if args.width_mm <= 0: raise ValueError("width-mm must be greater than zero")
    if args.rotation_seconds <= 0: raise ValueError("rotation-seconds must be greater than zero")
    if args.duration is not None and args.duration <= 0: raise ValueError("duration must be greater than zero")
    if args.rotations is not None and args.rotations <= 0: raise ValueError("rotations must be a positive integer")
    path=Path(args.positions)
    if not path.exists(): raise ValueError(f"positions file not found: {path}; run 'thunderdome positions generate'")
    rows=load_led_positions(path); controllers=load_controllers(args.controllers)
    geometry=load_geometry(args.geometry)
    if "H061" not in geometry.hubs: raise ValueError("geometry is missing apex hub H061")
    apex=geometry.hubs["H061"]; center_xy=(apex.x, apex.y)
    duration=None if args.hold else (args.duration if args.duration is not None else (args.rotations or 1) * args.rotation_seconds)
    color=parse_hex_color(args.color); background=parse_hex_color(args.background)
    def frame_for(_number: int, elapsed: float) -> RGBFrame:
        return render_clock_hand(rows, angle_radians=angle_for_elapsed(elapsed, rotation_seconds=args.rotation_seconds, direction=args.direction, offset_degrees=args.angle_offset_degrees), width_m=args.width_mm / 1000, color=color, background=background, brightness=args.brightness, center_xy=center_xy, exclude_tail=args.exclude_tail)
    if args.dry_run:
        print(f"Starting clock-hand: {args.direction}, width {args.width_mm:g}mm, rotation {args.rotation_seconds:g}s, {args.fps} FPS (dry run)")
        return _send_effect_frames(controllers, frame_for, fps=args.fps, duration=duration, dry_run=True, label="clock-hand")
    print(f"Starting clock-hand: {args.direction}, width {args.width_mm:g}mm, rotation {args.rotation_seconds:g}s, {args.fps} FPS")
    failures: dict[int, SendResult]={}; last=[]
    def send(frame: RGBFrame):
        nonlocal last
        last=session.send_frame(frame); _record_controller_failures(failures,last)
    with MultiControllerDDPSession(controllers) as session:
        stats=run_frame_loop(frame_for, send, fps=args.fps, duration=duration)
    _report_results(last); _report_persistent_failures(failures); _report_loop(stats)
    print(f"Completed rotations: {stats.elapsed_seconds / args.rotation_seconds:.2f}")
    return 1 if failures else 0



def _send_effect_frames(
    controllers,
    frame_for,
    *,
    fps: int,
    duration: float | None,
    dry_run: bool,
    label: str,
) -> int:
    failures: dict[int, SendResult] = {}
    last: list[SendResult] = []

    def send(frame: RGBFrame) -> None:
        nonlocal last
        last = session.send_frame(frame, dry_run=dry_run)
        _record_controller_failures(failures, last)

    with MultiControllerDDPSession(controllers) as session:
        stats = run_frame_loop(frame_for, send, fps=fps, duration=duration)
    _report_results(last)
    _report_persistent_failures(failures)
    _report_loop(stats)
    if dry_run:
        print(f"Dry run complete for {label}: {stats.frames_sent} frames")
    return 1 if failures else 0


def _run_spatial_effect(args: argparse.Namespace) -> int:
    if not 1 <= args.fps <= 60:
        raise ValueError("fps must be in range 1..60")
    if args.speed_mps <= 0:
        raise ValueError("speed-mps must be greater than zero")
    if args.duration is not None and args.duration <= 0:
        raise ValueError("duration must be greater than zero")
    if args.command == "expanding-rings":
        thickness_mm = args.thickness_mm
        if thickness_mm <= 0:
            raise ValueError("thickness-mm must be greater than zero")
    else:
        thickness_mm = args.height_mm
        if thickness_mm <= 0:
            raise ValueError("height-mm must be greater than zero")
    path = Path(args.positions)
    if not path.exists():
        raise ValueError(f"positions file not found: {path}; run 'thunderdome positions generate'")
    context = SpatialContext.load(path, args.geometry)
    controllers = load_controllers(args.controllers)
    color = parse_hex_color(args.color)
    background = parse_hex_color(args.background)
    thickness_m = thickness_mm / 1000
    selected = selected_xyz(context, exclude_tail=args.exclude_tail)
    if args.command == "expanding-rings":
        origin = parse_spatial_origin(args.origin, context)
        cycle_distance = max(distance3(point, origin) for point in selected)
        if cycle_distance <= 0:
            raise ValueError("maximum shell distance must be greater than zero")
        cycle_seconds = cycle_distance / args.speed_mps
    else:
        origin = None
        minimum_z = min(point[2] for point in selected)
        maximum_z = max(point[2] for point in selected)
        traversal = maximum_z - minimum_z
        if traversal <= 0:
            raise ValueError("selected Z bounds must have positive height")
        cycle_seconds = traversal / args.speed_mps * (2 if args.direction == "bounce" else 1)

    def frame_for(_number: int, elapsed: float) -> RGBFrame:
        kwargs = dict(
            elapsed_seconds=elapsed,
            speed_m_per_s=args.speed_mps,
            color=color,
            background=background,
            brightness=args.brightness,
            exclude_tail=args.exclude_tail,
        )
        if args.command == "expanding-rings":
            return render_expanding_rings(context, thickness_m=thickness_m, origin=origin, **kwargs)
        return render_height_wave(context, height_m=thickness_m, direction=args.direction, **kwargs)

    duration = None if args.hold else (args.duration if args.duration is not None else (args.loops or 1) * cycle_seconds)
    print(f"Starting {args.command}: thickness {thickness_mm:g}mm, speed {args.speed_mps:g}m/s, {args.fps} FPS" + (" (dry run)" if args.dry_run else ""))
    return _send_effect_frames(controllers, frame_for, fps=args.fps, duration=duration, dry_run=args.dry_run, label=args.command)


PROCEDURAL_DURATION_DEFAULTS = {"fire": 5.0, "aurora": 10.0, "fireflies": 8.0}
PROCEDURAL_LOOP_EFFECTS = {"rotating-plane", "radar"}


def _procedural_options(args: argparse.Namespace) -> dict[str, object]:
    shared = {"command", "controllers", "positions", "geometry", "brightness", "exclude_tail", "dry_run", "hold", "duration", "loops", "fps", "area"}
    return {key: value for key, value in vars(args).items() if key not in shared and value is not None}


def _procedural_duration(args: argparse.Namespace) -> float | None:
    if args.hold:
        return None
    if args.duration is not None:
        return args.duration
    if args.command in PROCEDURAL_LOOP_EFFECTS:
        return (args.loops or 1) * args.rotation_seconds
    return PROCEDURAL_DURATION_DEFAULTS[args.command]


def _validate_range(option: str, value: float, *, minimum: float | None = None, maximum: float | None = None, inclusive_minimum: bool = True) -> None:
    if minimum is not None:
        valid = value >= minimum if inclusive_minimum else value > minimum
        if not valid:
            comparator = ">=" if inclusive_minimum else ">"
            raise ValueError(f"{option}={value!r} must be {comparator} {minimum:g}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{option}={value!r} must be <= {maximum:g}")


def _validate_procedural_options(args: argparse.Namespace) -> None:
    if args.command == "fire":
        _validate_range("speed", args.speed, minimum=0, inclusive_minimum=False)
        _validate_range("flame-height-m", args.flame_height_m, minimum=0, inclusive_minimum=False)
        _validate_range("scale", args.scale, minimum=0, inclusive_minimum=False)
        _validate_range("turbulence", args.turbulence, minimum=0, maximum=1)
        _validate_range("cooling", args.cooling, minimum=0, maximum=1)
    elif args.command == "rotating-plane":
        _validate_range("rotation-seconds", args.rotation_seconds, minimum=0, inclusive_minimum=False)
        _validate_range("thickness-mm", args.thickness_mm, minimum=0, inclusive_minimum=False)
        _validate_range("trail-degrees", args.trail_degrees, minimum=0, maximum=360)
    elif args.command == "radar":
        _validate_range("rotation-seconds", args.rotation_seconds, minimum=0, inclusive_minimum=False)
        _validate_range("beam-width-degrees", args.beam_width_degrees, minimum=0, maximum=360, inclusive_minimum=False)
        _validate_range("trail-degrees", args.trail_degrees, minimum=0, maximum=360)
        _validate_range("range-m", args.range_m, minimum=0, inclusive_minimum=False)
        _validate_range("vertical-falloff", args.vertical_falloff, minimum=0, maximum=1)
    elif args.command == "aurora":
        _validate_range("speed", args.speed, minimum=0, inclusive_minimum=False)
        _validate_range("scale", args.scale, minimum=0, inclusive_minimum=False)
        _validate_range("band-width", args.band_width, minimum=0, maximum=1, inclusive_minimum=False)
        _validate_range("intensity", args.intensity, minimum=0, maximum=1, inclusive_minimum=False)
    elif args.command == "fireflies":
        _validate_range("speed", args.speed, minimum=0, inclusive_minimum=False)
        _validate_range("glow-radius-mm", args.glow_radius_mm, minimum=0, inclusive_minimum=False)
        _validate_range("lifetime-seconds", args.lifetime_seconds, minimum=0, inclusive_minimum=False)
        _validate_range("color-variation", args.color_variation, minimum=0, maximum=1)


def _run_procedural_effect(args: argparse.Namespace) -> int:
    if args.command not in {"fire", "rotating-plane", "radar", "aurora", "fireflies"}:
        raise ValueError(f"unknown procedural effect command: {args.command}")
    if not 1 <= args.fps <= 60:
        raise ValueError("fps must be in range 1..60")
    if args.duration is not None and args.duration <= 0:
        raise ValueError("duration must be greater than zero")
    if not 0 <= args.brightness <= 255:
        raise ValueError("brightness must be in range 0..255")
    _validate_procedural_options(args)
    options = _procedural_options(args)
    context = SpatialContext.load(args.positions, args.geometry)
    controllers = load_controllers(args.controllers)
    seed = int(options.pop("seed", 1))
    renderer = create_renderer(args.command, context, brightness=args.brightness, exclude_tail=args.exclude_tail, seed=seed, **options)
    duration = _procedural_duration(args)

    def frame_for(_number: int, elapsed: float) -> RGBFrame:
        return renderer.render(elapsed)

    print(f"Starting {args.command}: {args.fps} FPS" + (" (dry run)" if args.dry_run else ""))
    return _send_effect_frames(controllers, frame_for, fps=args.fps, duration=duration, dry_run=args.dry_run, label=args.command)


def _resolve_auto_playlist(effects: str | None, preset: str | None, shuffle: bool, seed: int) -> list[str]:
    if effects is not None:
        names = [part.strip() for part in effects.split(",")]
    elif preset:
        names = list(PRESETS[preset])
    else:
        names = list(DEFAULT_PLAYLIST)
    if not names or any(not name for name in names):
        raise ValueError("effects must be a non-empty comma-separated list")
    if len(set(names)) != len(names):
        raise ValueError("effects playlist contains duplicates")
    unknown = [name for name in names if name not in BY_NAME]
    if unknown:
        raise ValueError(f"unknown auto effect {unknown[0]!r}; valid choices: {', '.join(BY_NAME)}")
    non_auto = [name for name in names if not BY_NAME[name].supports_auto]
    if non_auto:
        raise ValueError(f"effect {non_auto[0]!r} is not auto-capable")
    if shuffle:
        import random
        random.Random(seed).shuffle(names)
    return names


def _auto_duration(args: argparse.Namespace, names: list[str]) -> float | None:
    if args.duration is not None:
        return args.duration
    if args.cycles is not None:
        return args.cycles * len(names) * args.interval
    return None


def _auto_timing(names: list[str], *, elapsed: float, interval: float, transition: float) -> dict[str, object]:
    slot = int((elapsed + 1e-12) // interval)
    interval_start = slot * interval
    local_in_interval = elapsed - interval_start
    index = slot % len(names)
    active_started = 0.0 if slot == 0 else interval_start - transition
    active_elapsed = elapsed - active_started
    timing: dict[str, object] = {
        "active": names[index],
        "active_elapsed": active_elapsed,
        "transitioning": False,
    }
    if transition and local_in_interval >= interval - transition - 1e-12:
        incoming_start = interval_start + interval - transition
        timing.update(
            {
                "transitioning": True,
                "incoming": names[(index + 1) % len(names)],
                "incoming_elapsed": elapsed - incoming_start,
                "blend": (elapsed - incoming_start) / transition,
            }
        )
    return timing


def _auto_frame_for_elapsed(names, renderer_for, *, elapsed: float, interval: float, transition: float, brightness: int) -> RGBFrame:
    timing = _auto_timing(names, elapsed=elapsed, interval=interval, transition=transition)
    if timing["transitioning"]:
        frame = blend(
            renderer_for(timing["active"], timing["active_elapsed"]),
            renderer_for(timing["incoming"], timing["incoming_elapsed"]),
            timing["blend"],
        )
    else:
        frame = renderer_for(timing["active"], timing["active_elapsed"])
    frame.apply_brightness(brightness)
    return frame


def _run_auto(args: argparse.Namespace) -> int:
    if not 1 <= args.fps <= 60:
        raise ValueError("fps must be in range 1..60")
    if not 0 <= args.brightness <= 255:
        raise ValueError("brightness must be in range 0..255")
    if args.interval <= 0 or args.transition < 0 or args.transition >= args.interval:
        raise ValueError("transition must be >= 0 and less than interval")
    if args.duration is not None and args.duration <= 0:
        raise ValueError("duration must be greater than zero")
    if args.dry_run and args.duration is None and args.cycles is None:
        raise ValueError("auto dry-run requires --cycles or --duration so it can finish safely")
    names = _resolve_auto_playlist(args.effects, args.preset, args.shuffle, args.seed)
    context = SpatialContext.load(args.positions, args.geometry)
    controllers = load_controllers(args.controllers)
    procedural_renderers = {
        name: BY_NAME[name].create_renderer(context, brightness=255, exclude_tail=args.exclude_tail, seed=args.seed)
        for name in names
        if BY_NAME[name].category == "procedural"
    }

    def renderer_for(name: str, elapsed: float) -> RGBFrame:
        preset = BY_NAME[name].auto_options
        if name == "clock-hand":
            return render_clock_hand(context.positions, angle_radians=angle_for_elapsed(elapsed, rotation_seconds=preset["rotation_seconds"]), width_m=preset["width_mm"] / 1000, center_xy=context.apex[:2], brightness=255, exclude_tail=args.exclude_tail)
        if name == "expanding-rings":
            return render_expanding_rings(context, elapsed_seconds=elapsed, speed_m_per_s=preset["speed_mps"], thickness_m=preset["thickness_mm"] / 1000, origin=parse_spatial_origin(preset["origin"], context), brightness=255, exclude_tail=args.exclude_tail)
        if name == "height-wave":
            return render_height_wave(context, elapsed_seconds=elapsed, speed_m_per_s=preset["speed_mps"], height_m=preset["height_mm"] / 1000, direction=preset["direction"], brightness=255, exclude_tail=args.exclude_tail)
        return procedural_renderers[name].render(elapsed)

    def frame_for(_number: int, elapsed: float) -> RGBFrame:
        return _auto_frame_for_elapsed(names, renderer_for, elapsed=elapsed, interval=args.interval, transition=args.transition, brightness=args.brightness)

    duration = _auto_duration(args, names)
    print(f"Starting auto playlist: {', '.join(names)}; interval {args.interval:g}s; transition {args.transition:g}s" + (" (dry run)" if args.dry_run else ""))
    return _send_effect_frames(controllers, frame_for, fps=args.fps, duration=duration, dry_run=args.dry_run, label="auto")

def _main(args: argparse.Namespace) -> int:
    if args.area == "controller":
        client = WLEDClient(args.host)
        if args.command == "info":
            print(json.dumps(client.get_info(), indent=2, sort_keys=True))
        elif args.command == "state":
            print(json.dumps(client.get_state(), indent=2, sort_keys=True))
        elif args.command == "effects": print(json.dumps(client.get_effects(), indent=2))
        elif args.command == "palettes": print(json.dumps(client.get_palettes(), indent=2))
        else:
            _wled_operation(args, client)
            print(f"{args.host}: {args.command} ok")
        return 0

    if args.area == "geometry":
        geometry = load_geometry(args.path)
        print(f"Validated {args.path}: {len(geometry.hubs)} hubs, {len(geometry.spars)} spars, connected graph")
        return 0

    if args.area == "route":
        geometry = load_geometry(args.geometry_path)
        routes = load_routes(args.route_path, geometry)
        if args.command == "generate":
            write_route_document(args.output, generate_route_document(routes, args.route_path, args.geometry_path))
            print(f"Generated {args.output}")
        elif args.command == "summary":
            for route in routes:
                print(
                    f"controller {route.controller_number}; string {route.string_id}; "
                    f"{route.start_hub}->{route.end_hub}; segments {len(route.segments)}; "
                    f"unique spars {route.unique_spar_count}; length {route.total_length_m:.6f} m; "
                    f"indexes {route.global_index_start}..{route.global_index_end}"
                )
        else:
            print("Validated 5 routes, 120 unique spars, 0 shared spars")
        return 0

    if args.area == "positions":
        geometry = load_geometry(args.geometry_path)
        routes = load_routes(args.route_path, geometry)
        if args.command == "generate":
            write_positions(args.path, generate_positions(routes, geometry))
            print(f"Generated {args.path}")
        else:
            rows = load_led_positions(args.path, geometry, routes)
            if args.command == "validate":
                print("Validated 5,000 nominal LED positions")
            else:
                for string_id in range(5):
                    group = [row for row in rows if row["string_id"] == string_id]
                    dome = [row for row in group if row["location_type"] == "spar"]
                    tail = [row for row in group if row["location_type"] == "tail"]
                    print(
                        f"string {string_id}: dome {len(dome)}, tail {len(tail)}, "
                        f"dome indexes {dome[0]['global_index']}..{dome[-1]['global_index']}, "
                        f"tail length {(tail[-1]['distance_below_apex_m'] if tail else 0):.3f} m"
                    )
        return 0

    if args.area == "controllers":
        if args.command in {"state", "power", "live", "brightness", "color", "effect", "palette", "preset", "prepare-ddp"}:
            return _run_multi_wled(args)
        controllers = load_controllers(args.controllers)
        if args.command == "validate":
            print("Validated five direct-DDP controllers")
        else:
            for controller in controllers.controllers:
                print(
                    f"{controller.controller_number}: {controller.host}; string {controller.string_id}; "
                    f"{controller.start_hub}; global {controller.global_start}..{controller.global_end}; "
                    f"local 0..999; enabled={controller.enabled}"
                )
        return 0

    if args.area == "ddp-all":
        return _run_multi_ddp(args)

    if args.area == "effect":
        if args.command == "clock-hand": return _run_clock_hand(args)
        if args.command == "auto": return _run_auto(args)
        if args.command in {"expanding-rings", "height-wave"}: return _run_spatial_effect(args)
        if args.command in {"fire", "rotating-plane", "radar", "aurora", "fireflies"}: return _run_procedural_effect(args)
        raise ValueError(f"unknown effect command: {args.command}")

    return _run_single_ddp(args)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _main(parse_args(argv))
    except (OSError, ValueError, WLEDApiError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
