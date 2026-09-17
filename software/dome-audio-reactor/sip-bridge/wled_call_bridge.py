#!/usr/bin/env python3
"""Bridge Asterisk EAGI call audio to WLED Audio Sync packets.

Asterisk EAGI exposes inbound channel audio on file descriptor 3. This script
reads signed linear 16 kHz audio, calculates volume and frequency data, and
sends WLED Audio Sync V2 UDP packets.
"""

from __future__ import annotations

import argparse
import ipaddress
import math
import os
import socket
import struct
import sys
import time
from typing import BinaryIO, Iterable

import numpy as np

AUDIO_SYNC_GROUP = "239.0.0.1"
AUDIO_SYNC_PORT = 11988
SAMPLE_RATE = 16000
FRAME_MS = 20
SAMPLES_PER_FRAME = int(SAMPLE_RATE * FRAME_MS / 1000)
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2
PACKET = struct.Struct("<6s2xffBB16B2xff")
HEADER_V2 = b"00002\0"


def clamp_float(value: float, low: float = 0.0, high: float = 255.0) -> float:
    return max(low, min(high, value))


def clamp_byte(value: float) -> int:
    return max(0, min(255, int(round(value))))


def is_multicast(address: str) -> bool:
    return ipaddress.ip_address(address).is_multicast


def consume_agi_environment() -> dict[str, str]:
    """Read the AGI environment from stdin until the blank separator line."""
    environment: dict[str, str] = {}
    while True:
        line = sys.stdin.readline()
        if line in ("", "\n", "\r\n"):
            break
        key, _, value = line.rstrip("\r\n").partition(":")
        if key:
            environment[key.strip()] = value.strip()
    return environment


def build_socket(target: str, ttl: int, interface_ip: str | None) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    if is_multicast(target):
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        if interface_ip:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_ip))
    return sock


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


def audio_to_packet_values(
    samples: np.ndarray,
    previous_smoothed: float,
    gain: float,
    noise_floor: float,
) -> tuple[float, float, bool, list[int], float, float]:
    """Convert one audio frame to volume and FFT values."""
    if samples.size == 0:
        return 0.0, previous_smoothed * 0.8, False, [0] * 16, 0.0, 0.0

    normalised = samples.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(normalised * normalised)))
    sample_raw = 0.0 if rms < noise_floor else clamp_float((rms - noise_floor) * gain)
    sample_smoothed = (previous_smoothed * 0.70) + (sample_raw * 0.30)
    peak = sample_raw > 180.0 and sample_raw > (sample_smoothed * 1.20)

    windowed = normalised * np.hanning(normalised.size)
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(normalised.size, 1.0 / SAMPLE_RATE)
    bands = np.geomspace(40, SAMPLE_RATE / 2, 17)
    fft_bins: list[int] = []
    for low, high in zip(bands[:-1], bands[1:]):
        mask = (freqs >= low) & (freqs < high)
        value = float(np.mean(fft[mask])) if np.any(mask) else 0.0
        fft_bins.append(clamp_byte(math.log1p(value * 100.0) * 50.0))

    if fft.size > 1:
        major_index = int(np.argmax(fft[1:]) + 1)
        major_peak = float(freqs[major_index])
        magnitude = clamp_float(float(fft[major_index] * 300.0), 0.0, 4096.0)
    else:
        major_peak = 0.0
        magnitude = 0.0

    return sample_raw, sample_smoothed, peak, fft_bins, magnitude, major_peak


def read_exact(audio: BinaryIO, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        chunk = audio.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def generated_audio_frame(frame: int, frequency: float = 220.0) -> np.ndarray:
    """Generate a pulsing tone for self-test mode."""
    t = (np.arange(SAMPLES_PER_FRAME) + (frame * SAMPLES_PER_FRAME)) / SAMPLE_RATE
    pulse = math.exp(-((frame % 25) / 6.0))
    samples = np.sin(2.0 * math.pi * frequency * t) * pulse * 0.80
    return np.round(samples * 32767.0).astype(np.int16)


def run_bridge(args: argparse.Namespace, audio: BinaryIO | None) -> int:
    sock = build_socket(args.target, args.ttl, args.interface_ip)
    destination = (args.target, args.port)
    frame = 0
    smoothed = 0.0
    started = time.monotonic()
    try:
        while True:
            if args.duration is not None and (time.monotonic() - started) >= args.duration:
                break
            if args.self_test:
                samples = generated_audio_frame(frame)
                time.sleep(FRAME_MS / 1000.0)
            else:
                if audio is None:
                    raise RuntimeError("Audio stream is required outside self-test mode")
                chunk = read_exact(audio, BYTES_PER_FRAME)
                if len(chunk) < BYTES_PER_FRAME:
                    break
                samples = np.frombuffer(chunk, dtype=np.int16)

            raw, smoothed, peak, fft_bins, magnitude, major_peak = audio_to_packet_values(
                samples, smoothed, args.gain, args.noise_floor
            )
            packet = make_packet(raw, smoothed, peak, frame, fft_bins, magnitude, major_peak)
            sock.sendto(packet, destination)
            if args.verbose and frame % 80 == 0:
                print(
                    f"frame={frame:3d} raw={raw:6.1f} smoothed={smoothed:6.1f} "
                    f"peak={int(peak)} major_peak={major_peak:7.1f}",
                    file=sys.stderr,
                    flush=True,
                )
            frame = (frame + 1) % 256
    finally:
        sock.close()
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge Asterisk EAGI audio to WLED Audio Sync")
    parser.add_argument("--target", default=AUDIO_SYNC_GROUP)
    parser.add_argument("--port", type=int, default=AUDIO_SYNC_PORT)
    parser.add_argument("--interface-ip")
    parser.add_argument("--ttl", type=int, default=1)
    parser.add_argument("--gain", type=float, default=900.0)
    parser.add_argument("--noise-floor", type=float, default=0.004)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        return run_bridge(args, audio=None)

    consume_agi_environment()
    try:
        audio = os.fdopen(3, "rb", buffering=0)
    except OSError as exc:
        print(f"Unable to open Asterisk EAGI audio fd 3: {exc}", file=sys.stderr)
        return 1
    with audio:
        return run_bridge(args, audio)


if __name__ == "__main__":
    raise SystemExit(main())
