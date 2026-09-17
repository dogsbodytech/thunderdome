"""Argument parser construction for the public controller CLI."""
from __future__ import annotations
import argparse
from typing import Sequence
from .config import CONTROLLER_LED_COUNT, CONTROLLERS_PATH, DDP_CHUNK_LEDS, DDP_PORT, EFFECT_DEFAULTS_PATH, GEOMETRY_PATH, LED_POSITIONS_PATH, LOGICAL_LED_COUNT, ROUTES_PATH
from .effects.Procedural import SPACE_BODIES
from .effects.Registry import PRESETS

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
    parser.add_argument("--controllers", default=str(CONTROLLERS_PATH))


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", choices=("simulator", "ddp", "both", "null"), default="simulator", help="frame destination (default: simulator)")
    parser.add_argument("--simulator-url", default="ws://127.0.0.1:8080/ws/producer", help="local simulator producer WebSocket URL")


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
    _output_options(parser)
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
    _output_options(parser)
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
    parser = argparse.ArgumentParser(prog="thunderdome", description="CLI for controller management, geometry validation, and direct DDP frames.")
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

    route = groups.add_parser("route", help="Validate and summarize authoritative structured routes")
    route_sub = route.add_subparsers(dest="command", required=True)
    for name in ("validate", "summary"):
        item = route_sub.add_parser(name)
        item.add_argument("--route-path", default=str(ROUTES_PATH))
        item.add_argument("--geometry-path", default=str(GEOMETRY_PATH))

    xlights = groups.add_parser("xlights", help="Export canonical layout models for xLights")
    xlights_sub = xlights.add_subparsers(dest="command", required=True)
    xlights_generate = xlights_sub.add_parser("generate")
    xlights_generate.add_argument("--output", required=True, metavar="FILE")
    xlights_generate.add_argument("--geometry-path", default=str(GEOMETRY_PATH))
    xlights_generate.add_argument("--route-path", default=str(ROUTES_PATH))

    positions = groups.add_parser("positions", help="Generate and validate nominal XYZ positions")
    positions_sub = positions.add_subparsers(dest="command", required=True)
    for name in ("generate", "validate", "summary"):
        item = positions_sub.add_parser(name)
        item.add_argument("--route-path", default=str(ROUTES_PATH))
        item.add_argument("--geometry-path", default=str(GEOMETRY_PATH))
        item.add_argument("--path", default=str(LED_POSITIONS_PATH))

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

    simulator = groups.add_parser("simulator", help="Offline local dome simulator")
    simulator_sub = simulator.add_subparsers(dest="command", required=True)
    serve = simulator_sub.add_parser("serve", help="serve the static offline dome simulator")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--geometry", default=None, help="geometry file; built-in default is the standard project geometry")
    serve.add_argument("--routes", default=None, help="route file defining LED traversal and spar association; geometry, routes, and positions must describe the same dome")
    serve.add_argument("--positions", default=None, help="generated LED positions file; built-in default is the standard project positions")
    browser = serve.add_mutually_exclusive_group()
    browser.add_argument("--open-browser", dest="open_browser", action="store_true")
    browser.add_argument("--no-open-browser", dest="open_browser", action="store_false")
    serve.set_defaults(open_browser=False)

    control = groups.add_parser("control", help="Local operator control service")
    control_sub = control.add_subparsers(dest="command", required=True)
    control_serve = control_sub.add_parser("serve", help="serve simulator plus local control APIs")
    control_serve.add_argument("--host", default="127.0.0.1")
    control_serve.add_argument("--port", type=int, default=8080)
    control_serve.add_argument("--controllers")
    control_serve.add_argument("--allow-live-control", action="store_true")
    control_serve.add_argument("--default-output", choices=("simulator", "ddp", "both"), default="simulator")
    control_serve.add_argument("--effect-defaults", default=None, metavar="FILE", help="operator effect-defaults JSON (configured default path)")
    control_serve.add_argument("--geometry", default=None)
    control_serve.add_argument("--routes", default=None)
    control_serve.add_argument("--positions", default=None)
    control_browser = control_serve.add_mutually_exclusive_group()
    control_browser.add_argument("--open-browser", dest="open_browser", action="store_true")
    control_browser.add_argument("--no-open-browser", dest="open_browser", action="store_false")
    control_serve.set_defaults(open_browser=False)

    effect = groups.add_parser("effect", help="Application-rendered spatial DDP effects")
    effect_sub = effect.add_subparsers(dest="command", required=True)
    clock = effect_sub.add_parser("ClockHand", aliases=("clock-hand",), help="render a rotating radial hand through DDP")
    _controllers_option(clock)
    _output_options(clock)
    clock.add_argument("--positions", default=str(LED_POSITIONS_PATH)); clock.add_argument("--geometry", default=str(GEOMETRY_PATH))
    clock.add_argument("--color", default="FFFFFF"); clock.add_argument("--background", default="000000")
    clock.add_argument("--brightness", type=int, default=32); clock.add_argument("--width-mm", type=float, default=300)
    clock.add_argument("--rotation-seconds", type=float, default=3); clock.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise")
    clock.add_argument("--angle-offset-degrees", type=float, default=0); clock.add_argument("--exclude-tail", action="store_true"); clock.add_argument("--dry-run", action="store_true")
    mode=clock.add_mutually_exclusive_group(); mode.add_argument("--hold", action="store_true"); mode.add_argument("--duration", type=float); mode.add_argument("--rotations", type=int)
    clock.add_argument("--fps", type=int, default=30)
    rings = effect_sub.add_parser("ExpandingRings", aliases=("expanding-rings",), help="render an expanding XYZ spherical shell through DDP")
    _add_spatial_effect_options(rings)
    rings.add_argument("--origin", default="apex", metavar="apex|centre|base|X,Y,Z")
    rings.add_argument("--thickness-mm", type=float, default=200)
    wave = effect_sub.add_parser("HeightWave", aliases=("height-wave",), help="render a moving horizontal height band through DDP")
    _add_spatial_effect_options(wave)
    wave.add_argument("--direction", choices=("up", "down", "bounce"), default="up")
    wave.add_argument("--height-mm", type=float, default=200)
    auto = effect_sub.add_parser("Auto", aliases=("auto",), help="cycle the registry playlist with crossfades")
    _controllers_option(auto)
    _output_options(auto)
    auto.add_argument("--positions", default=str(LED_POSITIONS_PATH)); auto.add_argument("--geometry", default=str(GEOMETRY_PATH))
    auto.add_argument("--effects", "--playlist", dest="effects"); auto.add_argument("--preset", choices=tuple(PRESETS))
    auto.add_argument("--interval", type=float, default=30); auto.add_argument("--transition", "--crossfade", dest="transition", type=float, default=2)
    auto.add_argument("--shuffle", action="store_true"); auto.add_argument("--seed", type=int, default=1)
    mode=auto.add_mutually_exclusive_group(); mode.add_argument("--duration", type=float); mode.add_argument("--loops", "--cycles", dest="cycles", type=_positive_int)
    auto.add_argument("--brightness", type=int, default=32); auto.add_argument("--fps", type=int, default=30); auto.add_argument("--exclude-tail", action="store_true"); auto.add_argument("--dry-run", action="store_true")

    fire = effect_sub.add_parser("Fire", aliases=("fire",), help="render rising turbulent XYZ flames")
    _add_effect_runtime_options(fire)
    fire.add_argument("--speed", type=float, default=1.0); fire.add_argument("--flame-height-m", type=float, default=2.5); fire.add_argument("--turbulence", type=float, default=.65); fire.add_argument("--cooling", type=float, default=.35); fire.add_argument("--scale", type=float, default=1.0); fire.add_argument("--palette", default="fire"); fire.add_argument("--seed", type=int, default=1)

    plane = effect_sub.add_parser("RotatingPlane", aliases=("rotating-plane",), help="render a rotating signed-distance plane")
    _add_effect_runtime_options(plane, loops=True)
    plane.add_argument("--axis", default="vertical", metavar="vertical|horizontal|tilted|X,Y,Z", help="rotation axis: vertical=(0,0,1), horizontal=(1,0,0), tilted=normalize(1,1,1), or explicit X,Y,Z"); plane.add_argument("--rotation-seconds", type=float, default=10); plane.add_argument("--thickness-mm", type=float, default=220); plane.add_argument("--color", default="FFFFFF"); plane.add_argument("--background", default="000000"); plane.add_argument("--trail-degrees", type=float, default=20, metavar="0..180", help="directional fading trail in degrees; 0 disables, 180 covers all unique plane orientations"); plane.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise"); plane.add_argument("--seed", type=int, default=1)

    radar = effect_sub.add_parser("Radar", aliases=("radar",), help="render a rotating XY radar beam")
    _add_effect_runtime_options(radar, loops=True)
    radar.add_argument("--rotation-seconds", type=float, default=8); radar.add_argument("--beam-width-degrees", type=float, default=12); radar.add_argument("--trail-degrees", type=float, default=35); radar.add_argument("--range-m", type=float, default=9999); radar.add_argument("--vertical-falloff", type=float, default=0); radar.add_argument("--color", default="00FF80"); radar.add_argument("--background", default="000000"); radar.add_argument("--direction", choices=("clockwise", "counterclockwise"), default="clockwise"); radar.add_argument("--seed", type=int, default=1)

    aurora = effect_sub.add_parser("Aurora", aliases=("aurora",), help="render flowing luminous XYZ bands")
    _add_effect_runtime_options(aurora)
    aurora.add_argument("--speed", type=float, default=.25); aurora.add_argument("--scale", type=float, default=1.2); aurora.add_argument("--band-width", type=float, default=.45); aurora.add_argument("--intensity", type=float, default=1); aurora.add_argument("--palette", default="mixed"); aurora.add_argument("--direction", default="1,0,0"); aurora.add_argument("--seed", type=int, default=1)

    flies = effect_sub.add_parser("Fireflies", aliases=("fireflies",), help="render deterministic 3D glowing particles")
    _add_effect_runtime_options(flies)
    flies.add_argument("--count", type=_positive_int, default=25); flies.add_argument("--speed", type=float, default=.35); flies.add_argument("--glow-radius-mm", type=float, default=300); flies.add_argument("--lifetime-seconds", type=float, default=8); flies.add_argument("--color", default="FFFFB0"); flies.add_argument("--color-variation", type=float, default=.25); flies.add_argument("--seed", type=int, default=1)

    twinkle = effect_sub.add_parser("Twinkle", aliases=("twinkle",), help="render stateful LED twinkles")
    _add_effect_runtime_options(twinkle)
    twinkle.set_defaults(brightness=255)
    twinkle.add_argument("--density", type=float, default=.08); twinkle.add_argument("--spawn-rate", type=float, default=12); twinkle.add_argument("--fade-in", type=float, default=.25); twinkle.add_argument("--hold-time", dest="twinkle_hold", type=float, default=.25); twinkle.add_argument("--fade-out", type=float, default=.7); twinkle.add_argument("--minimum-brightness", type=float, default=.05); twinkle.add_argument("--maximum-brightness", type=float, default=1); twinkle.add_argument("--color", default="FFFFFF"); twinkle.add_argument("--mode", choices=("fixed", "random"), default="fixed"); twinkle.add_argument("--background", default="000000"); twinkle.add_argument("--color-change-speed", type=float, default=0); twinkle.add_argument("--seed", type=int, default=1)

    for _name, _space_body in SPACE_BODIES.items():
        _space_body_parser = effect_sub.add_parser(_name, help=f"render {_space_body.description}")
        _add_effect_runtime_options(_space_body_parser)
        _space_body_parser.add_argument("--speed", type=float, default=_space_body.speed, help="animation speed")
        _space_body_parser.add_argument("--seed", type=int, default=1)

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

    args = parser.parse_args(argv)
    aliases = {"clock-hand": "ClockHand", "expanding-rings": "ExpandingRings", "height-wave": "HeightWave", "auto": "Auto", "fire": "Fire", "rotating-plane": "RotatingPlane", "radar": "Radar", "aurora": "Aurora", "fireflies": "Fireflies", "twinkle": "Twinkle"}
    args.command = aliases.get(args.command, args.command)
    return args
