import asyncio
import threading
import unittest

from cados.services.async_loop import AsyncLoopThread


class AsyncLoopTests(unittest.TestCase):
    def test_timeout_cancels_underlying_bluetooth_operation(self):
        loop = AsyncLoopThread()
        self.addCleanup(loop.stop)
        started = threading.Event()
        cancelled = threading.Event()

        async def operation():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with self.assertRaises(TimeoutError):
            loop.call(operation(), timeout=0.1)
        self.assertTrue(started.is_set())
        self.assertTrue(cancelled.wait(timeout=1))

    def test_close_cancels_pending_tasks_and_is_idempotent(self):
        loop = AsyncLoopThread()
        self.addCleanup(loop.stop)
        loop.stop()
        loop.stop()
        self.assertTrue(loop.loop.is_closed())
        self.assertFalse(loop.thread.is_alive())
        with self.assertRaises(RuntimeError):
            loop.call(asyncio.sleep(0))
