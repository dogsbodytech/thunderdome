import asyncio
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.simulator import SimulatorHTTPServer


def bare_server(*, thread_alive=False, loop_running=False, control_api=None):
    server = SimulatorHTTPServer.__new__(SimulatorHTTPServer)
    server._closed = False
    server._loop = Mock()
    server._loop.is_running.return_value = loop_running
    server._thread = Mock()
    server._thread.is_alive.return_value = thread_alive
    server._shutdown_timeout = 0.01
    server._stopped = threading.Event()
    server._ready = threading.Event()
    server._startup_error = None
    server._shutdown_error = None
    server.control_api = control_api
    return server


class SimulatorLifecycleTests(unittest.TestCase):
    def test_normal_shutdown_is_idempotent(self):
        server = bare_server(thread_alive=True, loop_running=True)
        server._thread.is_alive.side_effect = [True, False]

        server.shutdown()
        server.shutdown()

        self.assertTrue(server._closed)
        server._loop.call_soon_threadsafe.assert_called_once_with(server._loop.stop)
        server._thread.join.assert_called_once_with(timeout=0.01)

    def test_stuck_thread_retains_ownership_and_can_be_retried(self):
        server = bare_server(thread_alive=True, loop_running=True)
        with self.assertRaisesRegex(TimeoutError, "did not stop"):
            server.shutdown()
        self.assertFalse(server._closed)
        server._thread.is_alive.return_value = False

        server.shutdown()
        self.assertTrue(server._closed)
        self.assertEqual(server._thread.join.call_count, 1)

    def test_cleanup_exception_still_closes_loop_and_signals_stopped(self):
        server = bare_server()
        loop = asyncio.new_event_loop()
        server._loop = loop
        cleanup_error = RuntimeError("runner cleanup failed")
        server._start = AsyncMock()
        server._cleanup = AsyncMock(side_effect=cleanup_error)
        calls = []

        def run_until_complete(awaitable):
            awaitable.close()
            calls.append(awaitable)
            if len(calls) == 2:
                raise cleanup_error

        loop.run_until_complete = Mock(side_effect=run_until_complete)
        loop.run_forever = Mock()
        try:
            server._run()
            self.assertTrue(server._stopped.is_set())
            self.assertTrue(loop.is_closed())
            self.assertIs(server._shutdown_error, cleanup_error)
        finally:
            if not loop.is_closed():
                loop.close()

    def test_shutdown_reports_prior_cleanup_failure_then_allows_retry(self):
        server = bare_server(control_api=Mock())
        cleanup_error = RuntimeError("runner cleanup failed")
        server._shutdown_error = cleanup_error

        with self.assertRaisesRegex(RuntimeError, "runner cleanup failed"):
            server.shutdown()
        self.assertFalse(server._closed)
        server.shutdown()
        self.assertTrue(server._closed)
        self.assertEqual(server.control_api.shutdown.call_count, 2)


if __name__ == "__main__":
    unittest.main()