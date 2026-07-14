#!/usr/bin/env python3
"""Send fake WLED Audio Sync packets for testing AudioReactive receive mode.

This does not play audio. It emulates the network packets produced by a WLED
AudioReactive sender so a controller in receive mode has something to react to.
"""

from __future__ import annotations

import argparse
import ipaddress
import math
import socket
import struct
import sys
import time
from typing import Iterable

AUDIO_SYNC_GROUP = "239.0.0.1"
AUDIO_SYNC_PORT = 11988
PACKET = struct.Struct("<6s2xffBB16B2xff")
HEADER_V2 = b"00002\0"


def clamp(value: float, low: int = 0, high: int = 255) -> int:
    return max(low, min(high, int(round(value))))


def is_multicast(address: str) -> bool:
    return ipaddress.ip_address(address).is_multicast


def make_fft_bins(level: float, frame: int, mode: str) -> list[int]:
    """Create 16 fake frequency bins for WLED's GEQ style effects."""

    if mode == "sweep":
        active = (frame // 3) % 16
        bins = []
        for index in range(16):
            distance = min(abs(index - active), 16 - abs(index - active))
            bins.append(clamp(level * max(0.0, 1.0 - (distance / 4.0))))
        return bins

    # Pulse and sine modes bias the energy towards lower bins, like a bass hit.
    return [clamp(level * (1.0 - (index / 20.0))) for index in range(16)]


def pulse_level(now: float, bpm: float, mode: str, maximum: int) -> float:
    period = 60.0 / bpm
    phase = (now % period) / period

    if mode == "sine":
        normalised = (math.sin(phase * math.tau) + 1.0) / 2.0
    elif mode == "sweep":
        normalised = 0.65
    else:
        # Sharp attack and smooth decay.
        normalised = math.exp(-phase * 8.0)

    return maximum * normalised


def make_packet(
    sample_raw: float,
    sample_smoothed: float,
    peak: bool,
    frame: int,
    fft_bins: Iterable[int],
    magnitude: float,
    major_peak: float,
) -> bytes:
    bins = list(fft_bins)
    if len(bins) != 16:
        raise ValueError("WLED Audio Sync packets require exactly 16 FFT bins")

    return PACKET.pack(
        HEADER_V2,
        float(sample_raw),
        float(sample_smoothed),
        1 if peak else 0,
        frame % 256,
        *bins,
        float(magnitude),
        float(major_peak),
    )


def build_socket(target: str, ttl: int, interface_ip: str | None) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    if is_multicast(target):
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        if interface_ip:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_ip))

    return sock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send fake WLED Audio Sync V2 pulse packets")
    parser.add_argument("--target", default=AUDIO_SYNC_GROUP, help="Target IP address. Defaults to WLED multicast address.")
    parser.add_argument("--port", type=int, default=AUDIO_SYNC_PORT, help="Target UDP port. Defaults to 11988.")
    parser.add_argument("--interface-ip", help="Source interface IP to use for multicast on multi-homed hosts.")
    parser.add_argument("--ttl", type=int, default=1, help="Multicast TTL. Defaults to 1.")
    parser.add_argument("--fps", type=float, default=40.0, help="Packets per second. Defaults to 40.")
    parser.add_argument("--bpm", type=float, default=120.0, help="Pulse tempo. Defaults to 120 BPM.")
    parser.add_argument("--level", type=int, default=220, help="Maximum fake audio level from 0 to 255. Defaults to 220.")
    parser.add_argument("--duration", type=float, help="Stop after this many seconds. Defaults to running until Ctrl+C.")
    parser.add_argument("--mode", choices=("pulse", "sine", "sweep"), default="pulse", help="Generated pattern. Defaults to pulse.")
    parser.add_argument("--verbose", action="store_true", help="Print periodic status messages.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.fps <= 0:
        print("--fps must be greater than zero", file=sys.stderr)
        return 2

    if args.bpm <= 0:
        print("--bpm must be greater than zero", file=sys.stderr)
        return 2

    level_max = clamp(args.level)
    interval = 1.0 / args.fps
    started = time.monotonic()
    frame = 0
    smoothed = 0.0

    sock = build_socket(args.target, args.ttl, args.interface_ip)
    destination = (args.target, args.port)

    print(f"Sending WLED Audio Sync packets to {args.target}:{args.port}. Press Ctrl+C to stop.")

    try:
        while True:
            loop_started = time.monotonic()
            elapsed = loop_started - started

            if args.duration is not None and elapsed >= args.duration:
                break

            raw = pulse_level(elapsed, args.bpm, args.mode, level_max)
            smoothed = (smoothed * 0.70) + (raw * 0.30)
            peak = raw > (level_max * 0.80)
            fft_bins = make_fft_bins(raw, frame, args.mode)

            packet = make_packet(
                sample_raw=raw,
                sample_smoothed=smoothed,
                peak=peak,
                frame=frame,
                fft_bins=fft_bins,
                magnitude=raw * 16.0,
                major_peak=80.0 + (raw * 2.0),
            )

            sock.sendto(packet, destination)

            if args.verbose and frame % int(max(1, args.fps * 2)) == 0:
                print(f"frame={frame % 256:3d} raw={raw:6.1f} smoothed={smoothed:6.1f} peak={int(peak)}")

            frame = (frame + 1) % 256
            sleep_for = interval - (time.monotonic() - loop_started)
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        pass
    finally:
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
