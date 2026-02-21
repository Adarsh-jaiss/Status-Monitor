
# StatusMonitor: the top-level orchestrator.

# Responsibilities:
#   - Create a shared aiohttp session and connection pool
#   - Spin up one StatusPageWatcher coroutine per configured provider
#   - Run all watchers concurrently in a single asyncio event loop
#   - Provide a clean stop() method for graceful shutdown
#
# Concurrency model:
#   100 status pages = 100 asyncio coroutines, not 100 threads.
#   All coroutines share one event loop and one connection pool.
#   Each coroutine yields control while awaiting I/O, so the loop is
#   never blocked.

import asyncio
import logging

import aiohttp

from status_monitor.differ import IncidentDiffer
from status_monitor.handlers import ConsoleEventHandler
from status_monitor.http_client import ConditionalHTTPClient
from status_monitor.watcher import StatusPageWatcher

log = logging.getLogger(__name__)


class StatusMonitor:

    def __init__(self, pages: list[dict[str, str]]) -> None:
        self._pages = pages
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        connector = aiohttp.TCPConnector(limit=50)  # shared connection pool with limit 50
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "StatusMonitor/2.0 (status-tracker)"},
        ) as session:

            http_client = ConditionalHTTPClient(session)
            handler     = ConsoleEventHandler()

            for page in self._pages:
                watcher = StatusPageWatcher(
                    provider=page["name"],
                    api_base=page["api_base"],
                    http_client=http_client,
                    differ=IncidentDiffer(),   # isolated differ per provider
                    handler=handler,
                )
                task = asyncio.create_task(
                    watcher.run_forever(),
                    name=f"watcher-{page['name'].lower()}",
                )
                self._tasks.append(task)

            log.info(
                "StatusMonitor running — watching %d page(s). Press Ctrl+C to stop.",
                len(self._pages),
            )

            # blocks until all tasks finish (normally only on cancellation)
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def stop(self) -> None:
        """Cancel all watcher tasks. The event loop will drain them cleanly."""
        for task in self._tasks:
            task.cancel()