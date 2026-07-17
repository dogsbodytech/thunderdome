"""WLED ledmap upload and top-down clock-face test helpers.

This module intentionally stays standard-library only. WLED's JSON API is fine
for low-FPS mapping checks, but not for high-FPS 5000 LED animation; keep test
patterns slow, sparse, and sequential.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable

from thunderdome.wled.client import WLEDApiError, WLEDClient
from thunderdome.transport.ddp import DDP_CHUNK_LEDS, DDP_PORT, DDPError, derive_led_count, empty_frame, parse_hex_color, scale_color, send_frame, set_pixel

JsonDict = dict[str, Any]


class MappingError(ValueError):
    """Raised for invalid ledmap/position data or mapping command input."""


@dataclass(frozen=True)
class LedmapReport:
    path: str
    width: int
    height: int
    total_cells: int
    mapped_leds: int
    blank_cells: int
    min_led_index: int | None
    max_led_index: int | None
    duplicate_count: int
    data: JsonDict


def load_json_file(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MappingError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MappingError(f"invalid JSON in {path}: {exc}") from exc


def validate_ledmap(path: str | Path) -> LedmapReport:
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise MappingError("ledmap must be a JSON object")
    led_map = data.get("map")
    if not isinstance(led_map, list):
        raise MappingError("ledmap must contain a 'map' array")

    width = data.get("width")
    height = data.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise MappingError("2D ledmap must contain integer width and height")
    if width <= 0 or height <= 0:
        raise MappingError("width and height must be positive")
    if width * height != len(led_map):
        raise MappingError(f"width * height ({width * height}) does not match map length ({len(led_map)})")

    seen: set[int] = set()
    duplicates = 0
    mapped: list[int] = []
    for idx, value in enumerate(led_map):
        if not isinstance(value, int):
            raise MappingError(f"map value at cell {idx} is not an integer: {value!r}")
        if value < -1:
            raise MappingError(f"map value at cell {idx} must be -1 or a non-negative LED index")
        if value == -1:
            continue
        if value in seen:
            duplicates += 1
        seen.add(value)
        mapped.append(value)

    if duplicates:
        raise MappingError(f"ledmap contains {duplicates} duplicated physical LED index entries")

    return LedmapReport(
        path=str(path),
        width=width,
        height=height,
        total_cells=len(led_map),
        mapped_leds=len(mapped),
        blank_cells=led_map.count(-1),
        min_led_index=min(mapped) if mapped else None,
        max_led_index=max(mapped) if mapped else None,
        duplicate_count=duplicates,
        data=data,
    )


def minify_ledmap(data: JsonDict) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def normalize_base_url(host_or_url: str) -> str:
    if not host_or_url:
        raise MappingError("host/base URL is required")
    if not host_or_url.startswith(("http://", "https://")):
        host_or_url = "http://" + host_or_url
    return host_or_url.rstrip("/")


def upload_edit_file(host_or_url: str, content: bytes, *, remote_name: str = "ledmap.json", timeout: float = 30.0) -> None:
    """Upload a file to WLED's filesystem as multipart/form-data.

    WLED serves the browser file editor at /edit, but the actual upload
    handler is /upload. Posting multipart data to /edit returns 404 on
    normal WLED builds.
    """
    base = normalize_base_url(host_or_url)
    boundary = "----thunderdome-wled-map-boundary"
    body = b"\r\n".join([
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="data"; filename="{remote_name}"'.encode(),
        b"Content-Type: application/json",
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ])
    request = urllib.request.Request(
        f"{base}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise WLEDApiError(f"HTTP {exc.code} uploading to {base}/upload: {detail}") from exc
    except urllib.error.URLError as exc:
        raise WLEDApiError(f"Could not upload to {base}/upload: {exc.reason}") from exc
    except TimeoutError as exc:
        raise WLEDApiError(f"Timed out uploading to {base}/upload") from exc


@dataclass(frozen=True)
class LedPosition:
    led_index: int
    x_mm: float
    y_mm: float
    note: str = ""
    on_dome_path: bool = True


def _positions_list(data: Any) -> list[JsonDict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("positions", "led_positions", "leds"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise MappingError("positions file must be a list or contain positions/led_positions/leds list")


def _metadata(data: Any) -> JsonDict:
    return data if isinstance(data, dict) else {}


def load_positions(path: str | Path, *, include_tail: bool = False) -> tuple[list[LedPosition], JsonDict]:
    data = load_json_file(path)
    raw_positions = _positions_list(data)
    positions: list[LedPosition] = []
    for i, item in enumerate(raw_positions):
        if not isinstance(item, dict):
            raise MappingError(f"position entry {i} is not an object")
        led_index = None
        for key in ("led_index", "physical_index", "index", "id"):
            if isinstance(item.get(key), int):
                led_index = item[key]
                break
        if not isinstance(led_index, int):
            raise MappingError(f"position entry {i} missing integer led_index/physical_index/index/id")
        try:
            x_mm = float(item["x_mm"])
            y_mm = float(item["y_mm"])
        except KeyError as exc:
            raise MappingError(f"position entry {i} missing x_mm/y_mm") from exc
        except (TypeError, ValueError) as exc:
            raise MappingError(f"position entry {i} has invalid x_mm/y_mm") from exc
        note = str(item.get("note", ""))
        if "on_dome_path" in item:
            on_dome = bool(item.get("on_dome_path"))
        else:
            on_dome = "tail" not in note.lower()
        if not include_tail and not on_dome:
            continue
        positions.append(LedPosition(led_index, x_mm, y_mm, note, on_dome))
    return positions, _metadata(data)


def positions_info(path: str | Path) -> JsonDict:
    data = load_json_file(path)
    raw_positions = _positions_list(data)
    meta = _metadata(data)
    notes = Counter(str(item.get("note", "")) for item in raw_positions if isinstance(item, dict))
    paths = Counter(str(bool(item.get("on_dome_path", True))) for item in raw_positions if isinstance(item, dict))
    return {
        "grid_size": meta.get("grid_size") or [meta.get("width"), meta.get("height")],
        "dome_diameter": meta.get("dome_diameter") or meta.get("dome_diameter_m"),
        "cell_size": meta.get("cell_size") or meta.get("cell_size_mm"),
        "number_of_strings": meta.get("number_of_strings") or meta.get("strings"),
        "leds_per_string": meta.get("leds_per_string"),
        "on_dome_leds": sum(1 for item in raw_positions if isinstance(item, dict) and item.get("on_dome_path", True)),
        "tail_leds": sum(1 for item in raw_positions if isinstance(item, dict) and not item.get("on_dome_path", True)),
        "path_sequence": meta.get("path_sequence"),
        "top_centre_grid_coordinate": meta.get("top_centre_grid_coordinate") or meta.get("top_center_grid_coordinate"),
        "note_counts": dict(notes),
        "on_dome_path_counts": dict(paths),
    }


def angular_distance_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def led_angle_deg(position: LedPosition) -> float:
    return math.degrees(math.atan2(position.y_mm, position.x_mm)) % 360.0


def select_clock_hand_leds(
    positions: Iterable[LedPosition],
    *,
    angle_deg: float,
    hand_width_deg: float = 3.0,
    radius_min_mm: float = 0.0,
    radius_max_mm: float = 3000.0,
) -> set[int]:
    if hand_width_deg <= 0:
        raise MappingError("hand width must be positive")
    selected: set[int] = set()
    half_width = hand_width_deg / 2.0
    for position in positions:
        radius = math.hypot(position.x_mm, position.y_mm)
        if radius < radius_min_mm or radius > radius_max_mm:
            continue
        if angular_distance_deg(led_angle_deg(position), angle_deg % 360.0) <= half_width:
            selected.add(position.led_index)
    return selected


def clock_hand_width_mm(hand_width_mm: float | None, *, pitch_mm: float = 30.0, hand_width_pitches: float = 10.0) -> float:
    if hand_width_mm is not None:
        if hand_width_mm <= 0:
            raise MappingError("hand width mm must be positive")
        return float(hand_width_mm)
    if pitch_mm <= 0 or hand_width_pitches <= 0:
        raise MappingError("pitch and hand width pitches must be positive")
    return float(pitch_mm) * float(hand_width_pitches)


def select_clock_hand_band_leds(
    positions: Iterable[LedPosition],
    *,
    angle_deg: float,
    hand_width_mm: float = 300.0,
    radius_max_mm: float = 3000.0,
    centre_x_mm: float = 0.0,
    centre_y_mm: float = 0.0,
) -> set[int]:
    """Select LEDs in a straight radial band, not an angle wedge.

    0° is +X/east, 90° is +Y/north. `along >= 0` excludes LEDs behind the
    centre and `along <= radius_max_mm` excludes LEDs past the dome edge.
    """
    if hand_width_mm <= 0 or radius_max_mm <= 0:
        raise MappingError("hand width and radius must be positive")
    theta = math.radians(angle_deg % 360.0)
    ux = math.cos(theta)
    uy = math.sin(theta)
    half_width = hand_width_mm / 2.0
    selected: set[int] = set()
    for position in positions:
        dx = position.x_mm - centre_x_mm
        dy = position.y_mm - centre_y_mm
        along = dx * ux + dy * uy
        perp = abs(dx * uy - dy * ux)
        if 0 <= along <= radius_max_mm and perp <= half_width:
            selected.add(position.led_index)
    return selected


@dataclass(frozen=True)
class ClockHandFrame:
    angle_deg: float
    lit_leds: set[int]
    delay_seconds: float


def build_clock_hand_sweep_frames(
    positions: list[LedPosition],
    *,
    duration: float = 3.0,
    step_deg: float = 1.0,
    hand_width_mm: float = 300.0,
    radius_max_mm: float = 3000.0,
    fps: float | None = None,
) -> list[ClockHandFrame]:
    if duration <= 0 or step_deg <= 0:
        raise MappingError("duration and step degrees must be positive")
    if fps is not None and fps <= 0:
        raise MappingError("fps must be positive")
    angles: list[float] = []
    angle = 0.0
    while angle < 360.0 - 1e-9:
        angles.append(round(angle, 10))
        angle += step_deg
    delay = (1.0 / fps) if fps is not None else (duration / len(angles))
    return [
        ClockHandFrame(
            angle_deg=a,
            lit_leds=select_clock_hand_band_leds(
                positions,
                angle_deg=a,
                hand_width_mm=hand_width_mm,
                radius_max_mm=radius_max_mm,
            ),
            delay_seconds=delay,
        )
        for a in angles
    ]


def build_ddp_clock_hand_frame(
    positions: list[LedPosition],
    selected_leds: set[int],
    *,
    led_count: int,
    color: str = "FFFFFF",
    brightness: int = 64,
    background: str = "000000",
) -> bytearray:
    frame = empty_frame(led_count, scale_color(parse_hex_color(background), 255))
    rgb = scale_color(parse_hex_color(color), brightness)
    for position in positions:
        if position.led_index in selected_leds:
            set_pixel(frame, position.led_index, rgb)
    return frame


def print_clock_hand_sweep_summary(
    frames: list[ClockHandFrame],
    *,
    loaded_count: int,
    include_tail: bool,
    duration: float,
    step_deg: float,
    pitch_mm: float,
    hand_width_pitches: float,
    hand_width_mm: float,
    brightness: int,
    repeat: int | None = 1,
    loop: bool = False,
    show_frame_counts: bool = True,
    output: Any = None,
) -> None:
    counts = [len(frame.lit_leds) for frame in frames]
    print(f"Loaded {loaded_count} LED positions ({'including' if include_tail else 'excluding'} tail)", file=output)
    print("Clock hand sweep", file=output)
    print("Centre: 0,0 mm", file=output)
    print("Radius: 3000 mm", file=output)
    print(f"Pitch: {pitch_mm:g} mm", file=output)
    print(f"Hand width: {hand_width_pitches:g} pitches = {hand_width_mm:g} mm", file=output)
    print(f"Step: {step_deg:g} degree", file=output)
    print(f"Duration: {duration:g} seconds", file=output)
    print(f"Frames: {len(frames)}", file=output)
    if loop:
        print("Loop mode enabled. Press Ctrl-C to stop.", file=output)
    elif repeat and repeat > 1:
        print(f"Repeat mode: {repeat} sweeps.", file=output)
    if counts:
        print("Lit LEDs per frame:", file=output)
        print(f"  min: {min(counts)}", file=output)
        print(f"  max: {max(counts)}", file=output)
        print(f"  avg: {mean(counts):.1f}", file=output)
    if brightness > 128:
        print(f"Warning: brightness {brightness} is high. For mapping tests, 32-64 is recommended.", file=output)
    if frames and frames[0].delay_seconds < 0.02:
        print("Warning: requested sweep speed may exceed what WLED JSON API can process over HTTP. The sweep may stutter or run slower than requested.", file=output)
    if show_frame_counts:
        for i, frame in enumerate(frames[:3], start=1):
            print(f"Sweep 1, frame {i}/{len(frames)}: angle {frame.angle_deg:.1f}°, lit {len(frame.lit_leds)} LEDs", file=output)
        if len(frames) > 3:
            frame = frames[-1]
            print(f"Sweep 1, frame {len(frames)}/{len(frames)}: angle {frame.angle_deg:.1f}°, lit {len(frame.lit_leds)} LEDs", file=output)


def run_clock_hand_sweep(
    client: WLEDClient,
    positions: list[LedPosition],
    *,
    duration: float = 3.0,
    fps: float | None = None,
    step_deg: float = 1.0,
    pitch_mm: float = 30.0,
    hand_width_pitches: float = 10.0,
    hand_width_mm: float | None = None,
    brightness: int = 64,
    color: str = "FFFFFF",
    background: str = "000000",
    include_tail: bool = False,
    leave_on: bool = False,
    dry_run: bool = False,
    loop: bool = False,
    repeat: int | None = 1,
    transport: str = "http-json",
    host: str | None = None,
    led_count: int | None = None,
    ddp_port: int = DDP_PORT,
    ddp_chunk_leds: int = DDP_CHUNK_LEDS,
    verbose: bool = False,
    segment_id: int = 0,
    max_pairs: int = 200,
    sleep_fn: Callable[[float], None] = time.sleep,
    output: Any = None,
) -> None:
    if loop and repeat not in (None, 1):
        raise MappingError("--loop and --repeat are mutually exclusive")
    if repeat is None:
        repeat = 1
    if repeat <= 0:
        raise MappingError("repeat count must be positive")
    width_mm = clock_hand_width_mm(hand_width_mm, pitch_mm=pitch_mm, hand_width_pitches=hand_width_pitches)
    frames = build_clock_hand_sweep_frames(
        positions,
        duration=duration,
        fps=fps,
        step_deg=step_deg,
        hand_width_mm=width_mm,
        radius_max_mm=3000.0,
    )
    print_clock_hand_sweep_summary(
        frames,
        loaded_count=len(positions),
        include_tail=include_tail,
        duration=duration,
        step_deg=step_deg,
        pitch_mm=pitch_mm,
        hand_width_pitches=hand_width_pitches,
        hand_width_mm=width_mm,
        brightness=brightness,
        repeat=repeat,
        loop=loop,
        show_frame_counts=dry_run,
        output=output,
    )
    if dry_run:
        return
    if transport not in {"http-json", "ddp"}:
        raise MappingError("transport must be http-json or ddp")
    if transport == "ddp":
        if not host:
            raise MappingError("DDP transport requires --host")
        led_count = led_count or derive_led_count(positions)
        if led_count <= 0:
            raise MappingError("led-count must be positive")
        previous: set[int] = set()
        sent = 0
        started = time.monotonic()
        try:
            sweep_number = 0
            while True:
                sweep_number += 1
                sweep_start = time.monotonic()
                for i, frame in enumerate(frames, start=1):
                    if verbose:
                        print(f"Sweep {sweep_number}, frame {i}/{len(frames)}: angle {frame.angle_deg:.1f}°, lit {len(frame.lit_leds)} LEDs", file=output)
                    rgb_frame = build_ddp_clock_hand_frame(
                        positions,
                        frame.lit_leds,
                        led_count=led_count,
                        color=color,
                        brightness=brightness,
                        background=background,
                    )
                    send_frame(host, rgb_frame, port=ddp_port, chunk_leds=ddp_chunk_leds)
                    previous = frame.lit_leds
                    sent += 1
                    target_time = sweep_start + i * frame.delay_seconds
                    delay = target_time - time.monotonic()
                    if delay > 0:
                        sleep_fn(delay)
                if not loop and sweep_number >= repeat:
                    break
        except KeyboardInterrupt:
            print("Interrupted; clearing lit clock-hand LEDs.", file=output)
            if not leave_on:
                send_frame(host, empty_frame(led_count), port=ddp_port, chunk_leds=ddp_chunk_leds)
            return
        finally:
            actual = time.monotonic() - started
            if sent:
                print(f"Frames sent: {sent}", file=output)
                print(f"Target duration: {duration * (sent / len(frames)):.1f}s", file=output)
                print(f"Actual duration: {actual:.1f}s", file=output)
                print(f"Average FPS: {sent / actual if actual > 0 else 0:.1f}", file=output)
        if not leave_on:
            send_frame(host, empty_frame(led_count), port=ddp_port, chunk_leds=ddp_chunk_leds)
        return

    client.post_state({"on": True, "bri": brightness})
    previous: set[int] = set()
    try:
        sweep_number = 0
        while True:
            sweep_number += 1
            for i, frame in enumerate(frames, start=1):
                print(f"Sweep {sweep_number}, frame {i}/{len(frames)}: angle {frame.angle_deg:.1f}°, lit {len(frame.lit_leds)} LEDs", file=output)
                send_sparse_led_updates(
                    client,
                    sparse_diff_payload(previous, frame.lit_leds, hand_color=color, background_color=background),
                    segment_id=segment_id,
                    max_pairs=max_pairs,
                )
                previous = frame.lit_leds
                sleep_fn(frame.delay_seconds)
            if not loop and sweep_number >= repeat:
                break
    except KeyboardInterrupt:
        print("Interrupted; clearing lit clock-hand LEDs.", file=output)
        if previous and not leave_on:
            clear_leds(client, previous, segment_id=segment_id, color=background, max_pairs=max_pairs)
        return
    if previous and not leave_on:
        clear_leds(client, previous, segment_id=segment_id, color=background, max_pairs=max_pairs)


def sparse_diff_payload(previous: set[int], current: set[int], *, hand_color: str, background_color: str) -> list[Any]:
    payload: list[Any] = []
    for led_index in sorted(previous - current):
        payload.extend([led_index, background_color])
    for led_index in sorted(current - previous):
        payload.extend([led_index, hand_color])
    return payload


def chunk_seg_i_payload(payload: list[Any], *, max_pairs: int = 200) -> list[list[Any]]:
    if max_pairs <= 0:
        raise MappingError("max_pairs must be positive")
    if len(payload) % 2:
        raise MappingError("sparse seg.i payload must contain index/color pairs")
    chunk_size = max_pairs * 2
    return [payload[i : i + chunk_size] for i in range(0, len(payload), chunk_size)]


def send_sparse_led_updates(
    client: WLEDClient,
    payload: list[Any],
    *,
    segment_id: int = 0,
    max_pairs: int = 200,
) -> None:
    for chunk in chunk_seg_i_payload(payload, max_pairs=max_pairs):
        if chunk:
            client.set_individual_leds(chunk, segment_id=segment_id)


def clear_leds(client: WLEDClient, led_indexes: Iterable[int], *, segment_id: int = 0, color: str = "000000", max_pairs: int = 200) -> None:
    payload: list[Any] = []
    for led_index in sorted(set(led_indexes)):
        payload.extend([led_index, color])
    send_sparse_led_updates(client, payload, segment_id=segment_id, max_pairs=max_pairs)


def run_clock_test(
    client: WLEDClient,
    positions: list[LedPosition],
    *,
    duration: float = 60.0,
    fps: float = 5.0,
    hand_width_deg: float = 3.0,
    radius_min_mm: float = 0.0,
    radius_max_mm: float = 3000.0,
    hand_color: str = "FF0000",
    background_color: str = "000000",
    brightness: int = 64,
    segment_id: int = 0,
    leave_on: bool = False,
    max_pairs: int = 200,
    sleep_fn: Callable[[float], None] = time.sleep,
    output: Any = None,
) -> None:
    if fps <= 0 or duration <= 0:
        raise MappingError("duration and fps must be positive")
    client.post_state({"on": True, "bri": brightness})
    all_indexes = {p.led_index for p in positions}
    clear_leds(client, all_indexes, segment_id=segment_id, color=background_color, max_pairs=max_pairs)
    previous: set[int] = set()
    frame_count = int(duration * fps)
    try:
        for frame in range(frame_count):
            angle = (frame / max(frame_count, 1)) * 360.0
            current = select_clock_hand_leds(
                positions,
                angle_deg=angle,
                hand_width_deg=hand_width_deg,
                radius_min_mm=radius_min_mm,
                radius_max_mm=radius_max_mm,
            )
            send_sparse_led_updates(
                client,
                sparse_diff_payload(previous, current, hand_color=hand_color, background_color=background_color),
                segment_id=segment_id,
                max_pairs=max_pairs,
            )
            print(f"Frame {frame + 1}/{frame_count}: angle {angle:.1f}°, lit {len(current)} LEDs", file=output)
            previous = current
            sleep_fn(1.0 / fps)
    except KeyboardInterrupt:
        print("Interrupted; clearing lit clock-test LEDs.", file=output)
        if previous:
            clear_leds(client, previous, segment_id=segment_id, color=background_color, max_pairs=max_pairs)
        return
    if previous and not leave_on:
        clear_leds(client, previous, segment_id=segment_id, color=background_color, max_pairs=max_pairs)
