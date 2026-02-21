
# ETag-based conditional HTTP GET client.

# core efficiency mechanism:
#   Every response from Statuspage.io includes an ETag header.
#   We store it and send it back as If-None-Match on the next request.
#   If nothing changed, the server returns 304 Not Modified with NO body —
#   meaning zero JSON parsing, zero diffing, zero alerts, near-zero bandwidth.

# This is the correct "event-driven" mechanism for HTTP sources that don't expose WebSockets or webhooks.

import asyncio
import logging
from typing import Any

import aiohttp

from status_monitor.config import REQUEST_TIMEOUT_SECONDS

log = logging.getLogger(__name__)


class ConditionalHTTPClient:
    """
    Wraps an aiohttp.ClientSession with ETag-based conditional GET support.

    One instance is shared across all watchers (via the shared session),
    with per-URL ETag state stored in a dict.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._etags: dict[str, str] = {}   # url → last received ETag

    async def get_json_if_changed(self, url: str) -> tuple[bool, Any]:
        """
        Perform a conditional GET.

        Returns:
            (True, data)   — server returned 200 with new data
            (False, None)  — server returned 304 (nothing changed)

        Raises:
            aiohttp.ClientResponseError  on non-2xx / non-304 responses
            asyncio.TimeoutError         on request timeout
        """
        headers: dict[str, str] = {}
        if url in self._etags:
            headers["If-None-Match"] = self._etags[url]

        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status == 304:
                    return False, None   # Not Modified —> skip all processing

                resp.raise_for_status()

                etag = resp.headers.get("ETag")
                if etag:
                    self._etags[url] = etag

                data = await resp.json()
                return True, data

        except aiohttp.ClientResponseError as exc:
            log.warning("HTTP error fetching %s: %s %s", url, exc.status, exc.message)
            raise
        except asyncio.TimeoutError:
            log.warning("Timeout fetching %s", url)
            raise