"""Versioned binary RGB-frame protocol for the local simulator."""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Final

from .config import LOGICAL_LED_COUNT
from .frame import RGBFrame

FRAME_MAGIC: Final = b"TDFR"
FRAME_VERSION: Final = 1
RGB8_ENCODING: Final = "rgb8"
FRAME_HEADER: Final = struct.Struct("!4sBBHQdII")
FRAME_HEADER_LENGTH: Final = FRAME_HEADER.size
FRAME_PAYLOAD_LENGTH: Final = LOGICAL_LED_COUNT * 3


class FrameProtocolError(ValueError):
    """Raised when a simulator frame is not a supported complete RGB frame."""


@dataclass(frozen=True)
class DecodedFrame:
    sequence: int
    timestamp: float
    pixel_count: int
    payload: bytes


def encode_frame(frame: RGBFrame, *, sequence: int, timestamp: float) -> bytes:
    if frame.led_count != LOGICAL_LED_COUNT or len(frame.data) != FRAME_PAYLOAD_LENGTH:
        raise FrameProtocolError("simulator frames must contain exactly 5,000 RGB pixels / 15,000 bytes")
    if not isinstance(sequence, int) or sequence < 0:
        raise FrameProtocolError("frame sequence must be a non-negative integer")
    payload = bytes(frame.data)
    return FRAME_HEADER.pack(
        FRAME_MAGIC,
        FRAME_VERSION,
        0,
        FRAME_HEADER_LENGTH,
        sequence,
        float(timestamp),
        LOGICAL_LED_COUNT,
        len(payload),
    ) + payload


def decode_frame(message: bytes | bytearray | memoryview) -> DecodedFrame:
    if not isinstance(message, (bytes, bytearray, memoryview)):
        raise FrameProtocolError("simulator frame must be binary")
    raw = bytes(message)
    if len(raw) < FRAME_HEADER_LENGTH:
        raise FrameProtocolError("simulator frame is shorter than its header")
    magic, version, flags, header_length, sequence, timestamp, pixel_count, payload_length = FRAME_HEADER.unpack(raw[:FRAME_HEADER_LENGTH])
    if magic != FRAME_MAGIC:
        raise FrameProtocolError("simulator frame has invalid magic")
    if version != FRAME_VERSION:
        raise FrameProtocolError(f"unsupported simulator frame protocol version: {version}")
    if flags != 0 or header_length != FRAME_HEADER_LENGTH:
        raise FrameProtocolError("simulator frame has unsupported header fields")
    if pixel_count != LOGICAL_LED_COUNT:
        raise FrameProtocolError(f"simulator frame pixel count must be {LOGICAL_LED_COUNT}")
    if payload_length != FRAME_PAYLOAD_LENGTH:
        raise FrameProtocolError(f"simulator frame payload length must be {FRAME_PAYLOAD_LENGTH}")
    if len(raw) != FRAME_HEADER_LENGTH + payload_length:
        raise FrameProtocolError("simulator frame payload is truncated or oversized")
    return DecodedFrame(sequence=sequence, timestamp=timestamp, pixel_count=pixel_count, payload=raw[FRAME_HEADER_LENGTH:])
