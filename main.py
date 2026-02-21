import asyncio
import logging
import platform
import signal
import sys

from status_monitor.config import STATUS_PAGES
from status_monitor.orchestrator import StatusMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("main")

async def main() -> None:
    monitor = StatusMonitor(STATUS_PAGES)
    loop    = asyncio.get_running_loop()

    if platform.system() != "Windows":
     
        def _shutdown(sig: signal.Signals) -> None:
            log.info("Received %s — shutting down gracefully...", sig.name)
            monitor.stop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _shutdown, sig)

        try:
            await monitor.run()
        except asyncio.CancelledError:
            log.info("Monitor stopped.")

    else:
        try:
            await monitor.run()
        except (asyncio.CancelledError, KeyboardInterrupt):
            log.info("Shutting down...")
            monitor.stop()
            await asyncio.gather(*monitor._tasks, return_exceptions=True)
            log.info("Monitor stopped.")


if __name__ == "__main__":
    asyncio.run(main())