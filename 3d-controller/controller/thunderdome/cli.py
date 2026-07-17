"""CLI for controller management, geometry validation, and direct DDP frames."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Sequence

from .animation.loop import FrameLoopStats, run_frame_loop
from .config import CONTROLLER_LED_COUNT, DDP_CHUNK_LEDS, DDP_PORT, GEOMETRY_PATH, LOGICAL_LED_COUNT
from .controllers import load_controllers
from .frame import RGBFrame
from .geometry import load_geometry
from .led_positions import generate_positions, load_led_positions, write_positions
from .routes import generate_route_document, load_routes, write_route_document
from .transport.ddp import DirectDDPSession, parse_hex_color, send_frame
from .transport.multi_ddp import MultiControllerDDPSession, SendResult
from .wled.client import WLEDApiError, WLEDClient


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
    parser.add_argument("--controllers", default="config/controllers.json")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="thunderdome", description=__doc__)
    groups = parser.add_subparsers(dest="area", required=True)

    controller = groups.add_parser("controller", help="Secondary WLED HTTP management commands")
    controller_sub = controller.add_subparsers(dest="command", required=True)
    for command in ("info", "state"):
        item = controller_sub.add_parser(command)
        _host(item)
    brightness = controller_sub.add_parser("brightness")
    _host(brightness)
    brightness.add_argument("value", type=int)
    live = controller_sub.add_parser("live", help="enable or disable WLED realtime live mode")
    _host(live)
    live.add_argument("state", choices=("on", "off"))

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
    controllers_live = controllers_sub.add_parser("live", help="set WLED realtime live mode on enabled controllers")
    _controllers_option(controllers_live)
    controllers_live.add_argument("state", choices=("on", "off"))

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


def _run_controllers_live(args: argparse.Namespace) -> int:
    controllers = load_controllers(args.controllers)
    enabled = args.state == "on"
    failed = False
    for controller in controllers.controllers:
        if not controller.enabled:
            continue
        try:
            WLEDClient(controller.host).set_live(enabled)
        except Exception as exc:
            failed = True
            print(f"controller {controller.controller_number} {controller.host}: live {args.state} failed: {exc}", file=sys.stderr)
        else:
            print(f"controller {controller.controller_number} {controller.host}: live {args.state}")
    return 1 if failed else 0


def _main(args: argparse.Namespace) -> int:
    if args.area == "controller":
        client = WLEDClient(args.host)
        if args.command == "info":
            print(json.dumps(client.get_info(), indent=2, sort_keys=True))
        elif args.command == "state":
            print(json.dumps(client.get_state(), indent=2, sort_keys=True))
        elif args.command == "brightness":
            print(json.dumps(client.set_brightness(args.value), indent=2, sort_keys=True))
        else:
            client.set_live(args.state == "on")
            print(f"{args.host}: live {args.state}")
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
        if args.command == "live":
            return _run_controllers_live(args)
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

    return _run_single_ddp(args)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _main(parse_args(argv))
    except (OSError, ValueError, WLEDApiError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
