"""Network-free regression coverage for simulator connection cleanup."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.sinks import SimulatorFrameSink


class SimulatorFrameSinkCleanupTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)
        loop_patch = patch("thunderdome.sinks.asyncio.new_event_loop", return_value=self.loop)
        loop_patch.start()
        self.addCleanup(loop_patch.stop)
        self.socket = Mock(close=AsyncMock())
        self.session = Mock(ws_connect=AsyncMock(return_value=self.socket), close=AsyncMock())
        session_patch = patch("thunderdome.sinks.aiohttp.ClientSession", return_value=self.session)
        self.create_session = session_patch.start()
        self.addCleanup(session_patch.stop)
        self.sink = SimulatorFrameSink("ws://simulator.invalid/producer")

    def assert_released(self):
        self.assertIsNone(self.sink._socket)
        self.assertIsNone(self.sink._session)
        self.assertIsNone(self.sink._loop)
        self.assertTrue(self.loop.is_closed())

    def assert_closed_once(self):
        self.assert_released()
        self.sink.close()
        self.socket.close.assert_awaited_once_with()
        self.session.close.assert_awaited_once_with()

    def test_close_releases_connection_and_is_repeatable(self):
        self.sink.open()
        self.sink.close()

        self.assert_closed_once()

    def test_session_is_closed_after_websocket_close_fails(self):
        self.sink.open()
        socket_error = RuntimeError("websocket close failed")
        events = []

        async def close_socket():
            events.append("socket")
            raise socket_error

        async def close_session():
            events.append("session")

        self.socket.close.side_effect = close_socket
        self.session.close.side_effect = close_session

        with self.assertRaises(RuntimeError) as caught:
            self.sink.close()

        self.assertIs(caught.exception, socket_error)
        self.assertEqual(events, ["socket", "session"])
        self.assert_closed_once()

    def test_session_close_failure_still_releases_references_and_loop(self):
        self.sink.open()
        session_error = RuntimeError("session close failed")
        self.session.close.side_effect = session_error

        with self.assertRaises(RuntimeError) as caught:
            self.sink.close()

        self.assertIs(caught.exception, session_error)
        self.assert_closed_once()

    def test_both_close_failures_still_release_connection(self):
        self.sink.open()
        socket_error = RuntimeError("websocket close failed")
        self.socket.close.side_effect = socket_error
        self.session.close.side_effect = RuntimeError("session close failed")

        with self.assertRaises(RuntimeError) as caught:
            self.sink.close()

        self.assertIs(caught.exception, socket_error)
        self.assert_closed_once()

    def test_failed_connection_closes_partially_created_session(self):
        connection_error = ConnectionError("connection refused")
        self.session.ws_connect.side_effect = connection_error

        with self.assertRaisesRegex(OSError, "unable to connect.*connection refused") as caught:
            self.sink.open()

        self.assertIs(caught.exception.__cause__, connection_error)
        self.create_session.assert_called_once_with()
        self.session.ws_connect.assert_awaited_once_with(
            self.sink.url, timeout=self.sink.timeout_seconds, max_msg_size=16_000
        )
        self.assert_released()
        self.sink.close()
        self.session.close.assert_awaited_once_with()
        self.socket.close.assert_not_awaited()

    def test_failed_session_creation_closes_loop_without_resources(self):
        creation_error = RuntimeError("session creation failed")
        self.create_session.side_effect = creation_error

        with self.assertRaisesRegex(OSError, "unable to connect.*session creation failed") as caught:
            self.sink.open()

        self.assertIs(caught.exception.__cause__, creation_error)
        self.assert_released()
        self.sink.close()
        self.session.close.assert_not_awaited()
        self.socket.close.assert_not_awaited()

    def test_close_before_open_is_repeatable(self):
        self.sink.close()
        self.sink.close()

        self.assertIsNone(self.sink._socket)
        self.assertIsNone(self.sink._session)
        self.assertIsNone(self.sink._loop)
        self.create_session.assert_not_called()
        self.session.close.assert_not_awaited()
        self.socket.close.assert_not_awaited()

    def test_connection_failure_remains_primary_when_session_cleanup_fails(self):
        connection_error = ConnectionError("connection refused")
        cleanup_error = RuntimeError("session cleanup failed")
        self.session.ws_connect.side_effect = connection_error
        self.session.close.side_effect = cleanup_error

        with self.assertRaisesRegex(OSError, "unable to connect.*connection refused") as caught:
            self.sink.open()

        self.assertIs(caught.exception.__cause__, connection_error)
        self.assertIn("session cleanup failed", " ".join(caught.exception.__notes__))
        self.session.close.assert_awaited_once_with()
        self.socket.close.assert_not_awaited()
        self.assert_released()
        self.sink.close()
        self.session.close.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
