
# StatusPageWatcher: monitors a single Statuspage.io provider indefinitely.

# responsibilities:
#   - poll the provider's incidents endpoint on a fixed interval
#   - skip processing when the server signals no change (304 Not Modified)
#   - diff the response against previously seen update_ids
#   - forward only novel updates to the event handler
#   - retry with exponential backoff on transient network failures

import asyncio
import logging

import aiohttp

from status_monitor.config import (
    MAX_RETRIES,
    MAX_RETRY_DELAY_SECONDS,
    POLL_INTERVAL_SECONDS,
    RETRY_BASE_DELAY_SECONDS,
)
from status_monitor.differ import IncidentDiffer
from status_monitor.handlers import ConsoleEventHandler
from status_monitor.http_client import ConditionalHTTPClient
from status_monitor.parser import parse_incidents


class StatusPageWatcher:
    """
    Runs an infinite poll loop for a single status page provider.

    Backoff formula: delay = RETRY_BASE_DELAY_SECONDS * 2^retry_count
    Capped at MAX_RETRY_DELAY_SECONDS to avoid indefinite silence.
    retry_count is capped at MAX_RETRIES before the formula to prevent
    integer overflow in very long-running processes.
    """

    def __init__(
        self,
        provider: str,
        api_base: str,
        http_client: ConditionalHTTPClient,
        differ: IncidentDiffer,
        handler: ConsoleEventHandler,
    ) -> None:
        self.provider = provider
        self.url = f"{api_base}/incidents.json"
        self._http = http_client
        self._differ = differ
        self._handler = handler
        self._log = logging.getLogger(f"watcher.{provider.lower()}")

    async def run_forever(self) -> None:
        retry_count = 0
        self._log.info("Started watching %s → %s", self.provider, self.url)

        while True:
            try:
                changed, data = await self._http.get_json_if_changed(self.url)

                if not changed:
                    self._log.debug("304 Not Modified — no new updates for %s", self.provider)
                else:
                    updates = parse_incidents(self.provider, data)
                    novel   = self._differ.diff(updates)

                    if novel:
                        self._log.info("%d new update(s) detected for %s", len(novel), self.provider)
                        for update in novel:
                            await self._handler.handle(update)
                    else:
                        self._log.debug("Data changed but all updates already seen for %s", self.provider)

                retry_count = 0  # reset backoff on every successful request

            except (aiohttp.ClientError, asyncio.TimeoutError):
                retry_count = min(retry_count + 1, MAX_RETRIES)  # cap before formula
                delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** retry_count), MAX_RETRY_DELAY_SECONDS)
                self._log.warning(
                    "Transient error for %s. Retry %d/%d in %ds.",
                    self.provider, retry_count, MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
                continue  # skip the normal sleep at the bottom

            except asyncio.CancelledError:
                self._log.info("Watcher for %s cancelled.", self.provider)
                raise  # propagate so the task terminates cleanly

            except Exception as exc:
                self._log.exception("Unexpected error in watcher for %s: %s", self.provider, exc)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)