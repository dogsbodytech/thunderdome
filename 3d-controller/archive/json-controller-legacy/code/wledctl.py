#!/usr/bin/env python3
"""Tiny CLI wrapper around wled_client.py.

Examples:
    export WLED_BASE_URL=http://wled.local
    python wledctl.py info
    python wledctl.py on --return-state
    python wledctl.py brightness 128
    python wledctl.py color 255 0 0
    python wledctl.py segment 0 color 0 255 200
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from wled_client import WLEDApiError, WLEDClient
from wled_ddp import DDPError, empty_frame, pixel_frame, range_frame, send_frame as send_ddp_frame, solid_frame
from wled_mapping import (
    MappingError,
    clear_leds,
    load_positions,
    minify_ledmap,
    positions_info,
    run_clock_hand_sweep,
    run_clock_test,
    select_clock_hand_leds,
    send_sparse_led_updates,
    sparse_diff_payload,
    upload_edit_file,
    validate_ledmap,
)
from wled_favorites import (
    DEFAULT_FAVORITES_FILE,
    FavoritesError,
    FavoritesStore,
    cycle_favorites,
    filter_effects,
    validate_interval,
)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WLED_BASE_URL"),
        help="WLED base URL (default: WLED_BASE_URL)",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--return-state", action="store_true", help="Ask WLED v0.13+ to return updated state")
    parser.add_argument(
        "--favorites-file",
        default=os.environ.get("WLED_FAVORITES_FILE", DEFAULT_FAVORITES_FILE),
        help=f"favorites/favourites JSON file (default: {DEFAULT_FAVORITES_FILE})",
    )


def _normalize_common_options(argv: list[str] | None = None) -> list[str]:
    """Allow common options before or after the subcommand.

    argparse normally requires top-level options before the subcommand. Operators
    often type `wledctl info --base-url ...`, so move known common options to the
    front before parsing.
    """
    src = list(sys.argv[1:] if argv is None else argv)
    front: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(src):
        token = src[i]
        if token in {"--base-url", "--timeout", "--favorites-file"}:
            if i + 1 >= len(src):
                rest.append(token)  # let argparse report the missing value
                i += 1
            else:
                front.extend([token, src[i + 1]])
                i += 2
        elif token == "--return-state":
            front.append(token)
            i += 1
        else:
            rest.append(token)
            i += 1
    return front + rest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wledctl", description="Simple WLED JSON API CLI")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="GET /json/info")
    sub.add_parser("state", help="GET /json/state")
    effects = sub.add_parser("effects", help="GET /json/eff")
    effects.add_argument("--filter", help="case-insensitive substring filter for effect names")
    palettes = sub.add_parser("palettes", help="GET /json/pal")
    palettes.add_argument("--filter", help="case-insensitive substring filter for palette names")
    sub.add_parser("on", help="Turn LEDs on")
    sub.add_parser("off", help="Turn LEDs off")
    sub.add_parser("toggle", help="Toggle LEDs")

    brightness = sub.add_parser("brightness", help="Set global brightness 0-255")
    brightness.add_argument("value", type=int)

    transition = sub.add_parser("transition", help="Set transition units; 1 unit = 100 ms")
    transition.add_argument("value", type=int)
    transition.add_argument("--temporary", action="store_true", help="Use tt for this request only")

    color = sub.add_parser("color", help="Set primary color on segment 0 by default")
    color.add_argument("r", type=int)
    color.add_argument("g", type=int)
    color.add_argument("b", type=int)

    effect = sub.add_parser("effect", help="Set effect by ID")
    effect.add_argument("effect_id", type=int)

    palette = sub.add_parser("palette", help="Set palette by ID")
    palette.add_argument("palette_id", type=int)

    segment = sub.add_parser("segment", help="Per-segment commands")
    segment.add_argument("segment_id", type=int)
    seg_sub = segment.add_subparsers(dest="segment_command", required=True)

    seg_color = seg_sub.add_parser("color", help="Set segment primary color")
    seg_color.add_argument("r", type=int)
    seg_color.add_argument("g", type=int)
    seg_color.add_argument("b", type=int)

    seg_effect = seg_sub.add_parser("effect", help="Set segment effect")
    seg_effect.add_argument("effect_id", type=int)

    seg_palette = seg_sub.add_parser("palette", help="Set segment palette")
    seg_palette.add_argument("palette_id", type=int)

    seg_on = seg_sub.add_parser("on", help="Turn segment on")
    seg_on.set_defaults(segment_on=True)
    seg_off = seg_sub.add_parser("off", help="Turn segment off")
    seg_off.set_defaults(segment_on=False)

    raw = sub.add_parser("post", help="POST raw JSON state payload, e.g. '{\"on\":true}'")
    raw.add_argument("json_payload")

    favorites = sub.add_parser("favorites", help="Manage and cycle favourite/favorite effects")
    fav_sub = favorites.add_subparsers(dest="favorites_command", required=True)
    fav_sub.add_parser("list", help="List saved favorite effects")

    fav_add = fav_sub.add_parser("add", help="Add favorite effect by numeric ID")
    fav_add.add_argument("effect_id", type=int)
    fav_add.add_argument("--notes", help="operator notes stored with this effect")

    fav_add_name = fav_sub.add_parser("add-name", help="Add favorite effect by exact/substr name match")
    fav_add_name.add_argument("name")
    fav_add_name.add_argument("--notes", help="operator notes stored with this effect")

    fav_remove = fav_sub.add_parser("remove", help="Remove favorite effect by ID")
    fav_remove.add_argument("effect_id", type=int)

    fav_interval = fav_sub.add_parser("interval", help="Set saved default favorite cycle interval in seconds")
    fav_interval.add_argument("seconds", type=float)

    fav_clear = fav_sub.add_parser("clear", help="Clear all saved favorite effects")
    fav_clear.add_argument("--yes", action="store_true", help="required confirmation")

    fav_cycle = fav_sub.add_parser("cycle", help="Apply saved favorite effects in order")
    fav_cycle.add_argument("--interval", type=float, help="seconds between effects; overrides config default")
    fav_cycle.add_argument("--loop", action="store_true", help="repeat until Ctrl-C")
    fav_cycle.add_argument("--segment", type=int, help="apply effects to a specific WLED segment ID")

    ddp = sub.add_parser("ddp", help="Send realtime DDP RGB frames over UDP")
    ddp_sub = ddp.add_subparsers(dest="ddp_command", required=True)

    def add_ddp_common(parser: argparse.ArgumentParser, *, color: bool = False) -> None:
        parser.add_argument("--host", required=True, help="WLED host/IP for UDP DDP")
        parser.add_argument("--led-count", type=int, required=True)
        parser.add_argument("--ddp-port", type=int, default=4048)
        parser.add_argument("--ddp-chunk-leds", type=int, default=480)
        if color:
            parser.add_argument("--color", default="FFFFFF")
            parser.add_argument("--brightness", type=int, default=64)

    add_ddp_common(ddp_sub.add_parser("clear", help="Send a full black DDP frame"))
    add_ddp_common(ddp_sub.add_parser("solid", help="Send a solid-colour DDP frame"), color=True)
    ddp_pixel = ddp_sub.add_parser("pixel", help="Light one physical pixel index in a black DDP frame")
    add_ddp_common(ddp_pixel, color=True)
    ddp_pixel.add_argument("--index", type=int, required=True)
    ddp_range = ddp_sub.add_parser("range", help="Light a contiguous physical pixel range in a black DDP frame")
    add_ddp_common(ddp_range, color=True)
    ddp_range.add_argument("--start", type=int, required=True)
    ddp_range.add_argument("--count", type=int, required=True)

    mapping = sub.add_parser("mapping", help="Validate/upload ledmaps and run top-down mapping tests")
    map_sub = mapping.add_subparsers(dest="mapping_command", required=True)

    map_validate = map_sub.add_parser("validate", help="Validate a WLED ledmap JSON file")
    map_validate.add_argument("path")

    map_upload = map_sub.add_parser("upload", help="Upload a ledmap file to WLED as ledmap.json")
    map_upload.add_argument("path")
    map_upload.add_argument("--host", default=os.environ.get("WLED_BASE_URL"), help="WLED host/IP or URL")
    map_upload.add_argument("--dry-run", action="store_true", help="validate and show minified size without uploading")
    map_upload.add_argument("--reboot", action="store_true", help="POST {\"rb\":true} after successful upload")

    map_info = map_sub.add_parser("info", help="Summarize led_positions_2d.json")
    map_info.add_argument("path")

    def add_clock_options(parser: argparse.ArgumentParser, *, include_duration: bool) -> None:
        parser.add_argument("path")
        parser.add_argument("--host", default=os.environ.get("WLED_BASE_URL"), help="WLED host/IP or URL")
        if include_duration:
            parser.add_argument("--duration", type=float, default=60.0, help="seconds to run")
            parser.add_argument("--fps", type=float, default=5.0, help="frames per second")
        else:
            parser.add_argument("--angle", type=float, required=True, help="hand angle: 0=east/right, 90=north/up, 180=west, 270=south")
        parser.add_argument("--hand-width-deg", type=float, default=3.0)
        parser.add_argument("--radius-min-mm", type=float, default=0.0)
        parser.add_argument("--radius-max-mm", type=float, default=3000.0)
        parser.add_argument("--hand-color", default="FF0000")
        parser.add_argument("--background-color", default="000000")
        parser.add_argument("--brightness", type=int, default=64)
        parser.add_argument("--segment", type=int, default=0)
        parser.add_argument("--include-tail", action="store_true")
        parser.add_argument("--leave-on", action="store_true")
        parser.add_argument("--max-pairs", type=int, default=200, help="max sparse LED index/color pairs per JSON request")

    map_clock = map_sub.add_parser("clock-test", help="Run rotating top-down clock-hand mapping test")
    add_clock_options(map_clock, include_duration=True)

    map_frame = map_sub.add_parser("clock-frame", help="Light one static top-down clock-hand angle")
    add_clock_options(map_frame, include_duration=False)

    map_sweep = map_sub.add_parser("clock-hand-sweep", help="Run 10-pitch-wide straight radial clock-hand sweep")
    map_sweep.add_argument("path")
    map_sweep.add_argument("--host", default=os.environ.get("WLED_BASE_URL"), help="WLED host/IP or URL")
    map_sweep.add_argument("--duration", type=float, default=3.0)
    map_sweep.add_argument("--fps", type=float, help="frames per second; if omitted timing is duration / frame count")
    map_sweep.add_argument("--step-deg", type=float, default=1.0)
    map_sweep.add_argument("--pitch-mm", type=float, default=30.0)
    map_sweep.add_argument("--hand-width-pitches", type=float, default=10.0)
    map_sweep.add_argument("--hand-width-mm", type=float, help="override pitch-mm * hand-width-pitches")
    map_sweep.add_argument("--brightness", type=int, default=64)
    map_sweep.add_argument("--color", default="FFFFFF")
    map_sweep.add_argument("--background", default="000000")
    map_sweep.add_argument("--include-tail", action="store_true")
    map_sweep.add_argument("--leave-on", action="store_true")
    map_sweep.add_argument("--dry-run", action="store_true")
    map_sweep.add_argument("--transport", choices=["http-json", "ddp"], default="http-json")
    map_sweep.add_argument("--led-count", type=int, help="DDP frame LED count; defaults to max physical index + 1")
    map_sweep.add_argument("--ddp-port", type=int, default=4048)
    map_sweep.add_argument("--ddp-chunk-leds", type=int, default=480)
    map_sweep.add_argument("--verbose", action="store_true", help="print each DDP frame while sweeping")
    repeat_group = map_sweep.add_mutually_exclusive_group()
    repeat_group.add_argument("--loop", action="store_true", help="repeat sweeps until Ctrl-C")
    repeat_group.add_argument("--repeat", type=int, help="repeat the full sweep COUNT times")
    map_sweep.add_argument("--quiet", action="store_true", help="reserved for future quieter output; current default prints frame info")
    map_sweep.add_argument("--segment", type=int, default=0)
    map_sweep.add_argument("--max-pairs", type=int, default=200, help="max sparse LED index/color pairs per JSON request")

    args = parser.parse_args(_normalize_common_options(argv))
    if getattr(args, "mapping_command", None) == "clock-hand-sweep" and not args.loop and args.repeat is None:
        args.repeat = 1
    return args


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def format_indexed_names(names: list[str], query: str | None = None) -> list[str]:
    return [f"{item_id:4d}  {name}" for item_id, name in filter_effects(names, query)]


def print_indexed_names(names: list[str], query: str | None = None) -> None:
    for line in format_indexed_names(names, query):
        print(line)


def print_effects(effects: list[str], query: str | None = None) -> None:
    print_indexed_names(effects, query)


def print_favorites(store: FavoritesStore) -> None:
    data = store.load()
    print(f"Favorites file: {store.path}")
    print(f"Default interval: {data['default_interval_seconds']} seconds")
    if not data["effects"]:
        print("No favorite effects saved.")
        return
    print("\n ID   Name                           Notes")
    print("----  -----------------------------  ------------------------------")
    for entry in data["effects"]:
        print(f"{entry.get('id', '')!s:>4}  {entry.get('name', '')[:29]:<29}  {entry.get('notes', '')}")


def print_ledmap_report(report: Any) -> None:
    print(f"Validated {report.path}")
    print(f"Grid: {report.width} x {report.height}")
    print(f"Total cells: {report.total_cells}")
    print(f"Mapped LEDs: {report.mapped_leds}")
    print(f"Blank cells: {report.blank_cells}")
    print(f"Minimum LED index: {report.min_led_index}")
    print(f"Maximum LED index: {report.max_led_index}")
    print(f"Duplicate count: {report.duplicate_count}")


def print_mapping_info(info: dict[str, Any]) -> None:
    for label, key in [
        ("Grid size", "grid_size"),
        ("Dome diameter", "dome_diameter"),
        ("Cell size", "cell_size"),
        ("Number of strings", "number_of_strings"),
        ("LEDs per string", "leds_per_string"),
        ("On-dome LEDs", "on_dome_leds"),
        ("Tail LEDs", "tail_leds"),
        ("Path sequence", "path_sequence"),
        ("Top-centre grid coordinate", "top_centre_grid_coordinate"),
    ]:
        print(f"{label}: {info.get(key)}")
    print("\nCounts by note:")
    for key, value in sorted(info.get("note_counts", {}).items()):
        print(f"  {key or '<blank>'}: {value}")
    print("\nCounts by on_dome_path:")
    for key, value in sorted(info.get("on_dome_path_counts", {}).items()):
        print(f"  {key}: {value}")


def require_host(host: str | None) -> str:
    if not host:
        raise MappingError("provide --host or set WLED_BASE_URL")
    return host


def validate_hex_color(value: str, name: str) -> str:
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise MappingError(f"{name} must be a 6-character hex colour like FF0000")
    return value.upper()


def make_mapping_client(host: str, timeout: float) -> WLEDClient:
    return WLEDClient(host, timeout=timeout)


class MockClient:
    def post_state(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("dry-run mock client should not send post_state")

    def set_individual_leds(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("dry-run mock client should not send set_individual_leds")


def needs_wled_client(args: argparse.Namespace) -> bool:
    if args.command == "favorites":
        return args.favorites_command in {"add", "add-name", "cycle"}
    if args.command == "mapping":
        return False
    return args.command not in set()


def main() -> int:
    args = parse_args()
    store = FavoritesStore(args.favorites_file)

    client: WLEDClient | None = None
    if needs_wled_client(args):
        if not args.base_url:
            print("error: provide --base-url or set WLED_BASE_URL", file=sys.stderr)
            return 2
        # Keep the target configurable: the real dome currently uses
        # 192.168.12.11, but this tool should work with any WLED controller.
        client = WLEDClient(args.base_url, timeout=args.timeout)

    try:
        if args.command == "ddp":
            if args.ddp_command == "clear":
                frame = empty_frame(args.led_count)
            elif args.ddp_command == "solid":
                frame = solid_frame(args.led_count, args.color, args.brightness)
            elif args.ddp_command == "pixel":
                frame = pixel_frame(args.led_count, args.index, args.color, args.brightness)
            elif args.ddp_command == "range":
                frame = range_frame(args.led_count, args.start, args.count, args.color, args.brightness)
            else:
                raise DDPError(f"unknown ddp command {args.ddp_command}")
            packets = send_ddp_frame(args.host, frame, port=args.ddp_port, chunk_leds=args.ddp_chunk_leds)
            print(f"Sent DDP {args.ddp_command} frame to {args.host}:{args.ddp_port} ({args.led_count} LEDs, {packets} packets)")
        elif args.command == "mapping":
            if args.mapping_command == "validate":
                print_ledmap_report(validate_ledmap(args.path))
            elif args.mapping_command == "upload":
                report = validate_ledmap(args.path)
                print_ledmap_report(report)
                content = minify_ledmap(report.data)
                print(f"Minified size: {len(content)} bytes")
                if args.dry_run:
                    print("Dry run: not uploading")
                else:
                    host = require_host(args.host)
                    print(f"Uploading to {host.rstrip('/')}/edit as ledmap.json...")
                    try:
                        upload_edit_file(host, content, remote_name="ledmap.json", timeout=args.timeout)
                    except WLEDApiError:
                        print(f"Manual fallback: open http://{host.replace('http://', '').replace('https://', '').rstrip('/')}/edit and upload this file as ledmap.json", file=sys.stderr)
                        raise
                    print("Upload complete")
                    print("Reboot WLED to apply the map")
                    if args.reboot:
                        make_mapping_client(host, args.timeout).post_state({"rb": True})
                        print("Reboot command sent")
            elif args.mapping_command == "info":
                print_mapping_info(positions_info(args.path))
            elif args.mapping_command == "clock-frame":
                host = require_host(args.host)
                hand_color = validate_hex_color(args.hand_color, "hand color")
                background_color = validate_hex_color(args.background_color, "background color")
                positions, _ = load_positions(args.path, include_tail=args.include_tail)
                client = make_mapping_client(host, args.timeout)
                client.post_state({"on": True, "bri": args.brightness})
                all_indexes = {p.led_index for p in positions}
                clear_leds(client, all_indexes, segment_id=args.segment, color=background_color, max_pairs=args.max_pairs)
                current = select_clock_hand_leds(
                    positions,
                    angle_deg=args.angle,
                    hand_width_deg=args.hand_width_deg,
                    radius_min_mm=args.radius_min_mm,
                    radius_max_mm=args.radius_max_mm,
                )
                send_sparse_led_updates(
                    client,
                    sparse_diff_payload(set(), current, hand_color=hand_color, background_color=background_color),
                    segment_id=args.segment,
                    max_pairs=args.max_pairs,
                )
                print(f"Clock frame angle {args.angle:g}° lit {len(current)} LEDs")
                if not args.leave_on:
                    clear_leds(client, current, segment_id=args.segment, color=background_color, max_pairs=args.max_pairs)
                    print("Cleared clock frame LEDs")
            elif args.mapping_command == "clock-test":
                host = require_host(args.host)
                hand_color = validate_hex_color(args.hand_color, "hand color")
                background_color = validate_hex_color(args.background_color, "background color")
                positions, _ = load_positions(args.path, include_tail=args.include_tail)
                print(f"Loaded {len(positions)} LED positions ({'including' if args.include_tail else 'excluding'} tail)")
                run_clock_test(
                    make_mapping_client(host, args.timeout),
                    positions,
                    duration=args.duration,
                    fps=args.fps,
                    hand_width_deg=args.hand_width_deg,
                    radius_min_mm=args.radius_min_mm,
                    radius_max_mm=args.radius_max_mm,
                    hand_color=hand_color,
                    background_color=background_color,
                    brightness=args.brightness,
                    segment_id=args.segment,
                    leave_on=args.leave_on,
                    max_pairs=args.max_pairs,
                )
            elif args.mapping_command == "clock-hand-sweep":
                color = validate_hex_color(args.color, "color")
                background = validate_hex_color(args.background, "background")
                positions, _ = load_positions(args.path, include_tail=args.include_tail)
                sweep_client = MockClient() if args.dry_run else make_mapping_client(require_host(args.host), args.timeout)
                run_clock_hand_sweep(
                    sweep_client,
                    positions,
                    duration=args.duration,
                    fps=args.fps,
                    step_deg=args.step_deg,
                    pitch_mm=args.pitch_mm,
                    hand_width_pitches=args.hand_width_pitches,
                    hand_width_mm=args.hand_width_mm,
                    brightness=args.brightness,
                    color=color,
                    background=background,
                    include_tail=args.include_tail,
                    leave_on=args.leave_on,
                    dry_run=args.dry_run,
                    loop=args.loop,
                    repeat=args.repeat,
                    transport=args.transport,
                    host=args.host,
                    led_count=args.led_count,
                    ddp_port=args.ddp_port,
                    ddp_chunk_leds=args.ddp_chunk_leds,
                    verbose=args.verbose,
                    segment_id=args.segment,
                    max_pairs=args.max_pairs,
                )
        elif args.command == "favorites":
            if args.favorites_command == "list":
                print_favorites(store)
            elif args.favorites_command == "add":
                assert client is not None
                entry, created = store.add_effect(args.effect_id, client.get_effects(), notes=args.notes)
                action = "Added" if created else "Updated existing"
                print(f"{action} favorite {entry['id']}: {entry['name']}")
            elif args.favorites_command == "add-name":
                assert client is not None
                entry, created = store.add_effect_by_name(args.name, client.get_effects(), notes=args.notes)
                action = "Added" if created else "Updated existing"
                print(f"{action} favorite {entry['id']}: {entry['name']}")
            elif args.favorites_command == "remove":
                if store.remove_effect(args.effect_id):
                    print(f"Removed favorite effect {args.effect_id}")
                else:
                    print(f"Favorite effect {args.effect_id} was not saved")
            elif args.favorites_command == "interval":
                store.set_default_interval(args.seconds)
                interval = int(args.seconds) if float(args.seconds).is_integer() else args.seconds
                print(f"Default favourite cycle interval set to {interval} seconds")
            elif args.favorites_command == "clear":
                if not args.yes:
                    raise FavoritesError("favorites clear requires --yes")
                store.clear()
                print("Cleared all favorite effects")
            elif args.favorites_command == "cycle":
                assert client is not None
                if args.interval is not None:
                    validate_interval(args.interval)
                cycle_favorites(
                    client,
                    store,
                    interval=args.interval,
                    loop=args.loop,
                    segment_id=args.segment,
                    return_state=args.return_state,
                )
        elif args.command == "info":
            assert client is not None
            print_json(client.get_info())
        elif args.command == "state":
            assert client is not None
            print_json(client.get_state())
        elif args.command == "effects":
            assert client is not None
            print_effects(client.get_effects(), args.filter)
        elif args.command == "palettes":
            assert client is not None
            print_indexed_names(client.get_palettes(), args.filter)
        elif args.command == "on":
            assert client is not None
            print_json(client.set_power(True, return_state=args.return_state))
        elif args.command == "off":
            assert client is not None
            print_json(client.set_power(False, return_state=args.return_state))
        elif args.command == "toggle":
            assert client is not None
            print_json(client.toggle_power(return_state=args.return_state))
        elif args.command == "brightness":
            assert client is not None
            print_json(client.set_brightness(args.value, return_state=args.return_state))
        elif args.command == "transition":
            assert client is not None
            print_json(client.set_transition(args.value, temporary=args.temporary, return_state=args.return_state))
        elif args.command == "color":
            assert client is not None
            print_json(client.set_color((args.r, args.g, args.b), return_state=args.return_state))
        elif args.command == "effect":
            assert client is not None
            print_json(client.set_effect(args.effect_id, return_state=args.return_state))
        elif args.command == "palette":
            assert client is not None
            print_json(client.set_palette(args.palette_id, return_state=args.return_state))
        elif args.command == "segment":
            assert client is not None
            if args.segment_command == "color":
                print_json(client.set_color((args.r, args.g, args.b), segment_id=args.segment_id, return_state=args.return_state))
            elif args.segment_command == "effect":
                print_json(client.set_effect(args.effect_id, segment_id=args.segment_id, return_state=args.return_state))
            elif args.segment_command == "palette":
                print_json(client.set_palette(args.palette_id, segment_id=args.segment_id, return_state=args.return_state))
            elif args.segment_command in {"on", "off"}:
                print_json(client.update_segment(args.segment_id, {"on": args.segment_on}, return_state=args.return_state))
        elif args.command == "post":
            assert client is not None
            print_json(client.post_state(json.loads(args.json_payload), return_state=args.return_state))
    except (ValueError, json.JSONDecodeError, WLEDApiError, FavoritesError, MappingError, DDPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
