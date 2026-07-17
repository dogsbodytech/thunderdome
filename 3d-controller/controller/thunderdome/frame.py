"""Transport-independent linear RGB frame primitives."""
from __future__ import annotations

from dataclasses import dataclass

from .config import LOGICAL_LED_COUNT


DEFAULT_LOGICAL_LED_COUNT = LOGICAL_LED_COUNT
RGB = tuple[int, int, int]


class FrameError(ValueError):
    """Raised for invalid RGB values, ranges, or frame dimensions."""


def validate_rgb(rgb: RGB) -> RGB:
    if len(rgb) != 3 or any(not isinstance(value, int) or not 0 <= value <= 255 for value in rgb):
        raise FrameError("RGB must be exactly three integers in range 0..255")
    return rgb


@dataclass
class RGBFrame:
    """A mutable linear physical LED frame; index 0 maps to physical LED 0."""

    led_count: int
    data: bytearray

    @classmethod
    def allocate(cls, led_count: int = DEFAULT_LOGICAL_LED_COUNT, fill: RGB = (0, 0, 0)) -> "RGBFrame":
        if not isinstance(led_count, int) or led_count <= 0:
            raise FrameError("led_count must be a positive integer")
        rgb = validate_rgb(fill)
        return cls(led_count, bytearray(bytes(rgb) * led_count))

    def clear(self) -> None:
        self.data[:] = bytes(len(self.data))

    def fill(self, rgb: RGB) -> None:
        self.data[:] = bytes(validate_rgb(rgb)) * self.led_count

    def set_pixel(self, index: int, rgb: RGB) -> None:
        if not isinstance(index, int) or not 0 <= index < self.led_count:
            raise FrameError("pixel index is outside frame")
        self.data[index * 3 : index * 3 + 3] = bytes(validate_rgb(rgb))

    def set_range(self, start: int, count: int, rgb: RGB) -> None:
        if not isinstance(start, int) or not isinstance(count, int) or start < 0 or count < 0 or start + count > self.led_count:
            raise FrameError("range must be within frame")
        self.data[start * 3 : (start + count) * 3] = bytes(validate_rgb(rgb)) * count

    def apply_brightness(self, brightness: int) -> None:
        if not isinstance(brightness, int) or not 0 <= brightness <= 255:
            raise FrameError("brightness must be an integer in range 0..255")
        self.data[:] = bytes((channel * brightness) // 255 for channel in self.data)

    def as_bytes(self) -> bytes:
        return bytes(self.data)
