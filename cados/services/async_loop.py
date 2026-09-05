from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class AsyncLoopThread:
    def __init__(self) -> None:
        self._stopping = False
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro: Any, timeout: float = 15.0) -> Any:
        if self._stopping or self.loop.is_closed():
            coro.close()
            raise RuntimeError("Bluetooth-Eventloop ist bereits geschlossen.")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    def stop(self) -> None:
        if self._stopping or self.loop.is_closed():
            return
        self._stopping = True
        try:
            cleanup = asyncio.run_coroutine_threadsafe(self._cleanup_loop(), self.loop)
            cleanup.result(timeout=5)
        except Exception:
            logger.debug("Bluetooth-Eventloop-Cleanup fehlgeschlagen.", exc_info=True)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        if not self.thread.is_alive():
            self.loop.close()

    async def _cleanup_loop(self) -> None:
        current = asyncio.current_task(self.loop)
        tasks = [task for task in asyncio.all_tasks(self.loop) if task is not current and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.loop.shutdown_asyncgens()
