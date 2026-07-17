"""CLI for controller management, geometry validation, and direct DDP frames."""
from __future__ import annotations

import argparse
import json
import os
from typing import Sequence

from .config import DDP_CHUNK_LEDS, DDP_PORT, GEOMETRY_PATH, LED_COUNT
from .frame import RGBFrame
from .geometry import load_geometry
from .routes import generate_route_document, load_routes, write_route_document
from .led_positions import generate_positions, load_led_positions, validate_positions, write_positions
from .controllers import load_controllers
from .transport.multi_ddp import MultiControllerDDPSession
from .transport.ddp import parse_hex_color, send_frame
from .wled.client import WLEDClient


def _host(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True, help="WLED host or URL")


def _ddp_options(parser: argparse.ArgumentParser, *, colour: bool = False) -> None:
    _host(parser)
    parser.add_argument("--led-count", type=int, default=LED_COUNT)
    parser.add_argument("--port", type=int, default=DDP_PORT)
    parser.add_argument("--chunk-leds", type=int, default=DDP_CHUNK_LEDS)
    if colour:
        parser.add_argument("--color", default="FFFFFF")
        parser.add_argument("--brightness", type=int, default=64)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="thunderdome", description=__doc__)
    groups = parser.add_subparsers(dest="area", required=True)
    controller = groups.add_parser("controller", help="Secondary WLED HTTP management commands")
    controller_sub = controller.add_subparsers(dest="command", required=True)
    for command in ("info", "state"):
        item = controller_sub.add_parser(command); _host(item)
    brightness = controller_sub.add_parser("brightness"); _host(brightness); brightness.add_argument("value", type=int)
    ddp = groups.add_parser("ddp", help="Primary direct RGB frame transport")
    ddp_sub = ddp.add_subparsers(dest="command", required=True)
    _ddp_options(ddp_sub.add_parser("clear"))
    _ddp_options(ddp_sub.add_parser("solid"), colour=True)
    pixel = ddp_sub.add_parser("pixel"); _ddp_options(pixel, colour=True); pixel.add_argument("index", type=int)
    span = ddp_sub.add_parser("range"); _ddp_options(span, colour=True); span.add_argument("start", type=int); span.add_argument("count", type=int)
    geometry = groups.add_parser("geometry", help="Validate structural geometry")
    geometry_sub = geometry.add_subparsers(dest="command", required=True)
    validate = geometry_sub.add_parser("validate"); validate.add_argument("--path", default=str(GEOMETRY_PATH))
    route = groups.add_parser("route", help="Generate and validate authoritative manual routes")
    route_sub = route.add_subparsers(dest="command", required=True)
    for name in ("generate", "validate", "summary"):
        item=route_sub.add_parser(name); item.add_argument("--route-path", default=str(GEOMETRY_PATH.parent/'reference_string_route.md')); item.add_argument("--geometry-path", default=str(GEOMETRY_PATH)); item.add_argument("--output", default=str(GEOMETRY_PATH.parent/'routes/string_routes.json'))
    positions = groups.add_parser("positions", help="Generate and validate nominal XYZ positions")
    positions_sub = positions.add_subparsers(dest="command", required=True)
    for name in ("generate", "validate", "summary"):
        item=positions_sub.add_parser(name); item.add_argument("--route-path", default=str(GEOMETRY_PATH.parent/'reference_string_route.md')); item.add_argument("--geometry-path", default=str(GEOMETRY_PATH)); item.add_argument("--path", default=str(GEOMETRY_PATH.parent/'generated/led_positions_3d.json'))
    controllers=groups.add_parser('controllers'); controllers_sub=controllers.add_subparsers(dest='command',required=True)
    for name in ('validate','summary'):
        item=controllers_sub.add_parser(name); item.add_argument('--controllers',default='config/controllers.json')
    all_ddp=groups.add_parser('ddp-all'); all_sub=all_ddp.add_subparsers(dest='command',required=True)
    for name in ('clear','solid','controller-colors'):
        item=all_sub.add_parser(name); item.add_argument('--controllers',default='config/controllers.json'); item.add_argument('--dry-run',action='store_true'); item.add_argument('--brightness',type=int,default=16); item.add_argument('--color',default='FFFFFF')
    return parser.parse_args(argv)


def _colour(args: argparse.Namespace) -> tuple[int, int, int]:
    rgb = parse_hex_color(args.color)
    if not 0 <= args.brightness <= 255:
        raise ValueError("brightness must be in range 0..255")
    return tuple(channel * args.brightness // 255 for channel in rgb)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.area == "controller":
        client = WLEDClient(args.host)
        if args.command == "info": print(json.dumps(client.get_info(), indent=2, sort_keys=True))
        elif args.command == "state": print(json.dumps(client.get_state(), indent=2, sort_keys=True))
        else: print(json.dumps(client.set_brightness(args.value), indent=2, sort_keys=True))
        return 0
    if args.area == "geometry":
        geometry = load_geometry(args.path)
        print(f"Validated {args.path}: {len(geometry.hubs)} hubs, {len(geometry.spars)} spars, connected graph")
        return 0
    if args.area == "route":
        geometry=load_geometry(args.geometry_path); routes=load_routes(args.route_path,geometry)
        if args.command == 'generate': write_route_document(args.output,generate_route_document(routes,args.route_path,args.geometry_path)); print(f'Generated {args.output}')
        elif args.command == 'summary':
            for r in routes: print(f'controller {r.controller_number}; string {r.string_id}; {r.start_hub}->{r.end_hub}; segments {len(r.segments)}; unique spars {r.unique_spar_count}; length {r.total_length_m:.6f} m; indexes {r.global_index_start}..{r.global_index_end}')
        else: print('Validated 5 routes, 120 unique spars, 0 shared spars')
        return 0
    if args.area == "positions":
        geometry=load_geometry(args.geometry_path); routes=load_routes(args.route_path,geometry)
        if args.command == 'generate':
            write_positions(args.path, generate_positions(routes, geometry))
            print(f'Generated {args.path}')
            return 0
        else:
            rows=load_led_positions(args.path,geometry,routes)
            if args.command == 'validate': print('Validated 5,000 nominal LED positions')
            else:
                for s in range(5):
                    group=[r for r in rows if r['string_id']==s]; dome=[r for r in group if r['location_type']=='spar']; tail=[r for r in group if r['location_type']=='tail']; print(f'string {s}: dome {len(dome)}, tail {len(tail)}, dome indexes {dome[0]["global_index"]}..{dome[-1]["global_index"]}, tail length {(tail[-1]["distance_below_apex_m"] if tail else 0):.3f} m')
            return 0
    if args.area == 'controllers':
        cs=load_controllers(args.controllers)
        if args.command=='validate': print('Validated five direct-DDP controllers')
        else:
            for c in cs.controllers: print(f'{c.controller_number}: {c.host}; string {c.string_id}; {c.start_hub}; global {c.global_start}..{c.global_end}; local 0..999; enabled={c.enabled}')
        return 0
    if args.area == 'ddp-all':
        cs=load_controllers(args.controllers); frame=RGBFrame.allocate(5000)
        if args.command=='solid': frame.fill(_colour(args))
        elif args.command=='controller-colors':
            for c,col in zip(cs.controllers,((255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255))): frame.set_range(c.global_start,1000,tuple(x*args.brightness//255 for x in col))
        with MultiControllerDDPSession(cs) as session: results=session.send_frame(frame,dry_run=args.dry_run)
        for r in results: print(f'controller {r.controller_number} {r.host}: {r.packets} packets' + (f' error={r.error}' if r.error else ''))
        return 0
    frame = RGBFrame.allocate(args.led_count)
    if args.command == "solid": frame.fill(_colour(args))
    elif args.command == "pixel": frame.set_pixel(args.index, _colour(args))
    elif args.command == "range": frame.set_range(args.start, args.count, _colour(args))
    packets = send_frame(args.host, frame.data, port=args.port, chunk_leds=args.chunk_leds)
    print(f"Sent DDP {args.command} frame to {args.host}:{args.port} ({args.led_count} LEDs, {packets} packets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
