"""DDP UDP transport helpers for WLED realtime RGB frames.

DDP header format follows common WLED/LedFX implementations:
  byte 0: flags1 = VER1 (0x40) plus PUSH (0x01) on the final packet
  byte 1: sequence number (0 for this simple sender)
  byte 2: data type, 0x0B for 8-bit RGB
  byte 3: destination id, normally 1 (virtual display)
  bytes 4-7: big-endian byte offset/address into the DDP frame
  bytes 8-9: big-endian payload length in bytes
  bytes 10..: RGB payload

Reference checked while implementing: LedFX DDP sender uses
struct.pack("!BBBBLH", VER1|PUSH, sequence, DATATYPE, destination_id,
offset, length) and WLED documents DDP as the recommended realtime UDP input.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Callable, Iterable

from ..frame import FrameError, RGBFrame, validate_rgb

DDP_PORT = 4048
DDP_CHUNK_LEDS = 480
DDP_HEADER_LEN = 10
DDP_VER1 = 0x40
DDP_PUSH = 0x01
DDP_DATATYPE_RGB8 = 0x0B
DDP_DESTINATION_ID = 1


class DDPError(ValueError):
    pass


@dataclass(frozen=True)
class DDPChunk:
    led_offset: int
    byte_offset: int
    payload: bytes
    is_last: bool


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise DDPError("colour must be a 6-character hex RGB value like FF0000")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def scale_color(rgb: tuple[int, int, int], brightness: int = 255) -> tuple[int, int, int]:
    if not 0 <= brightness <= 255:
        raise DDPError("brightness must be in range 0..255")
    return tuple((component * brightness) // 255 for component in rgb)  # type: ignore[return-value]


def validate_led_count(led_count: int) -> None:
    if led_count <= 0:
        raise DDPError("led-count must be positive")


def empty_frame(led_count: int, background: tuple[int, int, int] = (0, 0, 0)) -> bytearray:
    """Compatibility helper backed by transport-independent :class:`RGBFrame`."""
    try:
        return RGBFrame.allocate(led_count, background).data
    except FrameError as exc:
        raise DDPError(str(exc)) from exc


def set_pixel(frame: bytearray, index: int, rgb: tuple[int, int, int]) -> None:
    if len(frame) % 3:
        raise DDPError("RGB frame length must be a multiple of 3")
    try:
        wrapper = RGBFrame(len(frame) // 3, frame)
        wrapper.set_pixel(index, rgb)
    except FrameError as exc:
        raise DDPError(str(exc)) from exc


def solid_frame(led_count: int, color: str, brightness: int = 255) -> bytearray:
    return empty_frame(led_count, scale_color(parse_hex_color(color), brightness))


def pixel_frame(led_count: int, index: int, color: str, brightness: int = 255) -> bytearray:
    frame = empty_frame(led_count)
    set_pixel(frame, index, scale_color(parse_hex_color(color), brightness))
    return frame


def range_frame(led_count: int, start: int, count: int, color: str, brightness: int = 255) -> bytearray:
    frame = empty_frame(led_count)
    try:
        RGBFrame(led_count, frame).set_range(start, count, scale_color(parse_hex_color(color), brightness))
    except FrameError as exc:
        raise DDPError(str(exc)) from exc
    return frame


def chunk_frame(frame: bytes | bytearray, *, chunk_leds: int = DDP_CHUNK_LEDS) -> list[DDPChunk]:
    if chunk_leds <= 0:
        raise DDPError("ddp-chunk-leds must be positive")
    if len(frame) % 3:
        raise DDPError("RGB frame length must be a multiple of 3")
    chunk_size = chunk_leds * 3
    chunks: list[DDPChunk] = []
    for byte_offset in range(0, len(frame), chunk_size):
        payload = bytes(frame[byte_offset : byte_offset + chunk_size])
        chunks.append(
            DDPChunk(
                led_offset=byte_offset // 3,
                byte_offset=byte_offset,
                payload=payload,
                is_last=byte_offset + chunk_size >= len(frame),
            )
        )
    return chunks


def build_ddp_packet(payload: bytes, *, byte_offset: int = 0, is_last: bool = True, sequence: int = 0, destination_id: int = DDP_DESTINATION_ID) -> bytes:
    if byte_offset < 0:
        raise DDPError("byte offset must be non-negative")
    if len(payload) > 65535:
        raise DDPError("DDP payload length must fit in 16 bits")
    flags = DDP_VER1 | (DDP_PUSH if is_last else 0)
    header = struct.pack("!BBBBLH", flags, sequence & 0xFF, DDP_DATATYPE_RGB8, destination_id & 0xFF, byte_offset, len(payload))
    return header + bytes(payload)


def packets_for_frame(frame: bytes | bytearray, *, chunk_leds: int = DDP_CHUNK_LEDS) -> list[bytes]:
    return [build_ddp_packet(chunk.payload, byte_offset=chunk.byte_offset, is_last=chunk.is_last) for chunk in chunk_frame(frame, chunk_leds=chunk_leds)]


def normalize_host(host: str) -> str:
    host = host.strip()
    if host.startswith("http://"):
        host = host[len("http://") :]
    elif host.startswith("https://"):
        host = host[len("https://") :]
    return host.split("/", 1)[0]


class DirectDDPSession:
    """Reusable UDP socket for a sequence of DDP frames to one controller."""

    def __init__(
        self,
        host: str,
        *,
        port: int = DDP_PORT,
        chunk_leds: int = DDP_CHUNK_LEDS,
        socket_factory: Callable[..., socket.socket] = socket.socket,
    ) -> None:
        self.host = host
        self.port = port
        self.chunk_leds = chunk_leds
        self._socket_factory = socket_factory
        self._socket: socket.socket | None = None

    def __enter__(self) -> "DirectDDPSession":
        self._socket = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def send(self, frame: bytes | bytearray) -> int:
        if self._socket is None:
            raise RuntimeError("DirectDDPSession must be entered before sending")
        return send_frame(
            self.host,
            frame,
            port=self.port,
            chunk_leds=self.chunk_leds,
            sock=self._socket,
        )


def send_frame(host: str, frame: bytes | bytearray, *, port: int = DDP_PORT, chunk_leds: int = DDP_CHUNK_LEDS, sock: socket.socket | None = None) -> int:
    packets = packets_for_frame(frame, chunk_leds=chunk_leds)
    dest_host = normalize_host(host)
    owns_socket = sock is None
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for packet in packets:
            sock.sendto(packet, (dest_host, port))
    finally:
        if owns_socket:
            sock.close()
    return len(packets)


def derive_led_count(positions: Iterable[object]) -> int:
    max_index = -1
    for position in positions:
        max_index = max(max_index, int(getattr(position, "led_index")))
    if max_index < 0:
        raise DDPError("cannot derive led-count from empty positions")
    return max_index + 1
