"""Destination-independent sinks for complete logical Thunderdome RGB frames."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Iterable
from urllib.parse import urlparse

import aiohttp

from .controllers import load_controllers
from .frame import RGBFrame
from .streaming import FrameProtocolError, encode_frame
from .transport.multi_ddp import MultiControllerDDPSession
from .wled.multi import run_wled_operation


@dataclass(frozen=True)
class SinkResult:
    name: str
    ok: bool
    error: str | None = None


class FrameSink:
    name = "sink"

    def open(self) -> None:
        return None

    def send_frame(self, frame: RGBFrame, *, timestamp: float | None = None, sequence: int | None = None) -> SinkResult:
        raise NotImplementedError

    def close(self) -> None:
        return None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class NullFrameSink(FrameSink):
    name = "null"

    def __init__(self) -> None:
        self.frame_count = 0
        self.byte_count = 0

    def send_frame(self, frame: RGBFrame, *, timestamp: float | None = None, sequence: int | None = None) -> SinkResult:
        try:
            encode_frame(frame, sequence=0 if sequence is None else sequence, timestamp=time.time() if timestamp is None else timestamp)
        except FrameProtocolError as exc:
            return SinkResult(self.name, False, str(exc))
        self.frame_count += 1
        self.byte_count += len(frame.data)
        return SinkResult(self.name, True)


class SimulatorFrameSink(FrameSink):
    name = "simulator"

    def __init__(self, url: str, *, timeout_seconds: float = 2.0) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.netloc or not parsed.path:
            raise ValueError("simulator URL must be an absolute ws:// or wss:// producer endpoint")
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: aiohttp.ClientSession | None = None
        self._socket: aiohttp.ClientWebSocketResponse | None = None
        self._sequence = 0

    async def _connect(self) -> None:
        self._session = aiohttp.ClientSession()
        self._socket = await self._session.ws_connect(self.url, timeout=self.timeout_seconds, max_msg_size=16_000)

    def open(self) -> None:
        if self._socket is not None:
            return
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as exc:
            self.close()
            raise OSError(f"unable to connect to simulator at {self.url}: {exc}") from exc

    async def _send(self, message: bytes) -> None:
        assert self._socket is not None
        await self._socket.send_bytes(message)

    def send_frame(self, frame: RGBFrame, *, timestamp: float | None = None, sequence: int | None = None) -> SinkResult:
        if self._socket is None or self._loop is None:
            return SinkResult(self.name, False, "simulator connection is not open")
        current_sequence = self._sequence if sequence is None else sequence
        try:
            message = encode_frame(frame, sequence=current_sequence, timestamp=time.time() if timestamp is None else timestamp)
            self._loop.run_until_complete(asyncio.wait_for(self._send(message), timeout=self.timeout_seconds))
        except (FrameProtocolError, OSError, asyncio.TimeoutError, aiohttp.ClientError) as exc:
            return SinkResult(self.name, False, f"simulator streaming failed: {exc}")
        self._sequence = current_sequence + 1
        return SinkResult(self.name, True)

    async def _close(self) -> None:
        if self._socket is not None:
            await self._socket.close()
        if self._session is not None:
            await self._session.close()

    def close(self) -> None:
        if self._loop is not None:
            try:
                self._loop.run_until_complete(self._close())
            finally:
                self._loop.close()
        self._loop = None
        self._session = None
        self._socket = None


class DDPFrameSink(FrameSink):
    name = "ddp"

    def __init__(self, controllers_path: str) -> None:
        self.controllers_path = controllers_path
        self._session: MultiControllerDDPSession | None = None

    def open(self) -> None:
        if self._session is None:
            controllers = load_controllers(self.controllers_path)
            results = run_wled_operation(controllers, lambda client: client.set_brightness(255))
            failures = [f"controller {result.controller_number}: {result.error}" for result in results if result.error]
            if failures:
                raise OSError(f"unable to set WLED brightness to 255 before DDP: {'; '.join(failures)}")
            self._session = MultiControllerDDPSession(controllers)

    def send_frame(self, frame: RGBFrame, *, timestamp: float | None = None, sequence: int | None = None) -> SinkResult:
        if self._session is None:
            return SinkResult(self.name, False, "DDP sink is not open")
        results = self._session.send_frame(frame)
        failures = [f"controller {result.controller_number}: {result.error}" for result in results if result.error]
        return SinkResult(self.name, not failures, "; ".join(failures) if failures else None)

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None


class CompositeFrameSink(FrameSink):
    name = "composite"

    def __init__(self, sinks: Iterable[FrameSink]) -> None:
        self.sinks = list(sinks)

    def open(self) -> None:
        opened: list[FrameSink] = []
        try:
            for sink in self.sinks:
                sink.open()
                opened.append(sink)
        except Exception:
            for sink in reversed(opened):
                sink.close()
            raise

    def send_frame(self, frame: RGBFrame, *, timestamp: float | None = None, sequence: int | None = None) -> SinkResult:
        failures = []
        for sink in self.sinks:
            result = sink.send_frame(frame, timestamp=timestamp, sequence=sequence)
            if not result.ok:
                failures.append(f"{result.name}: {result.error or 'delivery failed'}")
        return SinkResult(self.name, not failures, "; ".join(failures) if failures else None)

    def close(self) -> None:
        failures = []
        for sink in reversed(self.sinks):
            try:
                sink.close()
            except Exception as exc:  # close every sink even if one fails
                failures.append(f"{sink.name}: {exc}")
        if failures:
            raise OSError("; ".join(failures))
