from __future__ import annotations

import asyncio
import sys
import threading
import unittest
from pathlib import Path

from aiohttp import ClientSession, WSServerHandshakeError, WSMsgType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.frame import RGBFrame
from thunderdome.config import GEOMETRY_PATH, LED_POSITIONS_PATH, REFERENCE_ROUTE_PATH
from thunderdome.simulator import create_http_server
from thunderdome.streaming import FrameProtocolError, decode_frame, encode_frame
from thunderdome.sinks import CompositeFrameSink, FrameSink, NullFrameSink, SinkResult


class FrameProtocolTests(unittest.TestCase):
    def test_round_trip_preserves_header_and_exact_rgb_payload(self):
        frame = RGBFrame.allocate(5_000, (1, 2, 3))
        encoded = encode_frame(frame, sequence=42, timestamp=123.5)
        decoded = decode_frame(encoded)
        self.assertEqual(decoded.sequence, 42)
        self.assertEqual(decoded.timestamp, 123.5)
        self.assertEqual(decoded.pixel_count, 5_000)
        self.assertEqual(decoded.payload, bytes(frame.data))
        self.assertEqual(len(decoded.payload), 15_000)
        self.assertEqual(encoded[:4], b"TDFR")

    def test_invalid_magic_version_count_and_length_are_rejected(self):
        frame = RGBFrame.allocate(5_000)
        encoded = bytearray(encode_frame(frame, sequence=1, timestamp=1.0))
        for offset, value in ((0, ord("X")), (4, 99), (27, 0)):
            with self.subTest(offset=offset):
                malformed = bytearray(encoded)
                malformed[offset] = value
                with self.assertRaises(FrameProtocolError):
                    decode_frame(bytes(malformed))
        with self.assertRaises(FrameProtocolError):
            decode_frame(bytes(encoded[:-1]))
        with self.assertRaises(FrameProtocolError):
            encode_frame(RGBFrame.allocate(4_999), sequence=1, timestamp=1.0)


class SimulatorLiveStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = create_http_server("127.0.0.1", 0, GEOMETRY_PATH, REFERENCE_ROUTE_PATH, LED_POSITIONS_PATH)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.session = ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    async def test_producer_frame_is_broadcast_to_viewer_and_status_reports_live_state(self):
        base_url = f"http://127.0.0.1:{self.port}"
        viewer = await self.session.ws_connect(f"{base_url}/ws/viewer")
        producer = await self.session.ws_connect(f"{base_url}/ws/producer")
        wire_frame = encode_frame(RGBFrame.allocate(5_000, (9, 8, 7)), sequence=12, timestamp=34.5)
        await producer.send_bytes(wire_frame)

        received = await viewer.receive(timeout=2)
        self.assertEqual(received.type, WSMsgType.BINARY)
        self.assertEqual(decode_frame(received.data).sequence, 12)

        async with self.session.get(f"{base_url}/api/simulator/metadata") as response:
            self.assertEqual(response.status, 200)
            metadata = await response.json()
        self.assertEqual(metadata["streaming"]["producer_websocket_path"], "/ws/producer")
        self.assertEqual(metadata["streaming"]["viewer_websocket_path"], "/ws/viewer")
        self.assertEqual(metadata["streaming"]["viewer_queue_size"], 1)
        self.assertTrue(metadata["streaming"]["supported"])
        self.assertEqual(metadata["streaming"]["expected_pixel_count"], 5_000)
        self.assertEqual(metadata["streaming"]["expected_payload_length"], 15_000)

        async with self.session.get(f"{base_url}/api/simulator/status") as response:
            self.assertEqual(response.status, 200)
            status = await response.json()
        self.assertTrue(status["producer_connected"])
        self.assertEqual(status["viewer_count"], 1)
        self.assertEqual(status["last_frame"]["sequence"], 12)
        self.assertEqual(status["last_frame"]["timestamp"], 34.5)

        with self.assertRaises(WSServerHandshakeError) as duplicate:
            await self.session.ws_connect(f"{base_url}/ws/producer")
        self.assertEqual(duplicate.exception.status, 409)

        await producer.close()
        await viewer.close()

    async def test_out_of_order_producer_frame_is_rejected_without_regressing_latest_frame(self):
        base_url = f"http://127.0.0.1:{self.port}"
        viewer = await self.session.ws_connect(f"{base_url}/ws/viewer")
        producer = await self.session.ws_connect(f"{base_url}/ws/producer")
        await producer.send_bytes(encode_frame(RGBFrame.allocate(5_000, (1, 2, 3)), sequence=12, timestamp=1.0))
        self.assertEqual(decode_frame((await viewer.receive(timeout=2)).data).sequence, 12)
        await producer.send_bytes(encode_frame(RGBFrame.allocate(5_000, (4, 5, 6)), sequence=11, timestamp=2.0))

        async with self.session.get(f"{base_url}/api/simulator/status") as response:
            status = await response.json()
        self.assertEqual(status["last_frame"]["sequence"], 12)
        self.assertEqual(status["rejected_frames"], 1)

        await producer.close()
        await viewer.close()


class RecordingSink(FrameSink):
    def __init__(self, name: str, *, fail: bool = False):
        self.name = name
        self.fail = fail
        self.opened = 0
        self.closed = 0
        self.frames = []

    def open(self):
        self.opened += 1

    def send_frame(self, frame, *, timestamp=None, sequence=None):
        self.frames.append(frame)
        return SinkResult(self.name, not self.fail, "simulated failure" if self.fail else None)

    def close(self):
        self.closed += 1


class SinkTests(unittest.TestCase):
    def test_null_sink_counts_without_network(self):
        sink = NullFrameSink()
        sink.open()
        result = sink.send_frame(RGBFrame.allocate(5_000))
        sink.close()
        self.assertTrue(result.ok)
        self.assertEqual((sink.frame_count, sink.byte_count), (1, 15_000))

    def test_composite_opens_sends_same_frame_and_closes_all(self):
        first = RecordingSink("first")
        second = RecordingSink("second", fail=True)
        frame = RGBFrame.allocate(5_000)
        sink = CompositeFrameSink([first, second])
        sink.open()
        result = sink.send_frame(frame)
        sink.close()
        self.assertFalse(result.ok)
        self.assertIs(first.frames[0], frame)
        self.assertIs(second.frames[0], frame)
        self.assertEqual((first.opened, second.opened, first.closed, second.closed), (1, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
