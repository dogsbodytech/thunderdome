"""Monotonic frame scheduling for held frames and generated animations."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from threading import Event
from typing import TypeVar


FrameT = TypeVar("FrameT")
FrameProducer = Callable[[int, float], FrameT] | Iterator[FrameT]
FrameSender = Callable[[FrameT], object]


@dataclass(frozen=True)
class FrameLoopStats:
    """Result of a frame loop run."""

    frames_sent: int
    elapsed_seconds: float
    interrupted: bool = False


def run_frame_loop(
    producer: FrameProducer[FrameT],
    sender: FrameSender[FrameT],
    *,
    fps: int,
    duration: float | None = None,
    loops: int | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], object] = time.sleep,
    cancel_event: Event | None = None,
) -> FrameLoopStats:
    """Send frames at a monotonic, drift-resistant cadence.

    ``producer`` may be a callback receiving ``(frame_number, elapsed_seconds)``
    or an iterator/generator yielding frames.  The callback form supports future
    stateful effects such as a moving clock hand; an iterator is convenient for
    prebuilt or generator-based animations.  Passing neither ``duration`` nor
    ``loops`` runs until Ctrl+C.
    """
    if not 1 <= fps <= 60:
        raise ValueError("fps must be in range 1..60")
    if duration is not None and duration <= 0:
        raise ValueError("duration must be greater than zero")
    if loops is not None and loops <= 0:
        raise ValueError("loops must be a positive integer")

    iterator = None if callable(producer) else iter(producer)
    started_at = clock()
    frames_sent = 0
    interrupted = False

    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                interrupted = True
                break
            now = clock()
            elapsed = now - started_at
            if duration is not None and elapsed >= duration:
                break
            if loops is not None and frames_sent >= loops:
                break

            if iterator is None:
                frame = producer(frames_sent, elapsed)
            else:
                try:
                    frame = next(iterator)
                except StopIteration:
                    break
            sender(frame)
            frames_sent += 1

            if loops is not None and frames_sent >= loops:
                break
            next_frame_at = started_at + (frames_sent / fps)
            delay = next_frame_at - clock()
            if delay > 0:
                if cancel_event is None:
                    sleep(delay)
                else:
                    cancel_event.wait(delay)
    except KeyboardInterrupt:
        interrupted = True

    return FrameLoopStats(
        frames_sent=frames_sent,
        elapsed_seconds=clock() - started_at,
        interrupted=interrupted,
    )
