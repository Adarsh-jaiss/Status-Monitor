
#event handlers: the output layer of the pipeline.

# each handler receives an IncidentUpdate and decides what to do with it.
# all formatting decisions live here — the model (IncidentUpdate) is kept
# as a pure data container with zero display logic.

# to add a new output target, implement a class with:
#     async def handle(self, update: IncidentUpdate) -> None: ...
# and pass it into StatusPageWatcher in orchestrator.py.
#

# examples of handlers you could add:
#   - SlackEventHandler   → post to a Slack channel via webhook
#   - PagerDutyHandler    → trigger an alert via Events API v2
#   - WebhookHandler      → POST JSON to any arbitrary endpoint
#   - FileHandler         → append structured lines to a JSONL log file


import logging
from datetime import datetime, timezone

from status_monitor.models import IncidentUpdate, format_dt

log = logging.getLogger(__name__)

# ─── Impact colour map (ANSI — safe to strip if plain output is needed) ───────

_R = "\033[0m"   # reset

_STATUS_COLOR: dict[str, str] = {
    "investigating": "\033[33m",   # yellow  — something is wrong, unknown cause
    "identified":    "\033[31m",   # red     — root cause confirmed
    "monitoring":    "\033[34m",   # blue    — fix deployed, watching
    "resolved":      "\033[32m",   # green   — all clear
}

_IMPACT_COLOR: dict[str, str] = {
    "critical": "\033[91m",   # bright red
    "major":    "\033[33m",   # yellow
    "minor":    "\033[34m",   # blue
    "none":     "\033[32m",   # green
}


def _ts() -> str:
    """ISO 8601 UTC timestamp, e.g. 2026-02-21T12:39:08Z"""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _color_status(status: str) -> str:
    c = _STATUS_COLOR.get(status.lower(), "")
    return f"{c}{status.upper()}{_R}" if c else status.upper()


def _color_impact(impact: str) -> str:
    c = _IMPACT_COLOR.get(impact.lower(), "")
    return f"{c}{impact.upper()}{_R}" if c else impact.upper()


class ConsoleEventHandler:
    """
    Emits one structured log line per incident update to stdout.

    Format:
        [2026-02-21T12:39:08Z] OpenAI | IDENTIFIED | Impact=MINOR | Product=ChatGPT availability degraded | Affected=Chat Completions | Message=We are investigating...

    Design decisions:
      - Single line per event  → trivially grep/awk/cut-able in a terminal or log aggregator
      - ISO 8601 + Z suffix    → unambiguous, sorts lexicographically, standard across all tooling
      - pipe-delimited fields  → easy to parse with `cut -d'|' -f3` or feed into Splunk/Loki
      - ANSI colour on STATUS and Impact value only → human scannable without breaking parsers
      - Message truncated at 120 chars → keeps lines readable; full text is in the status page
      - Prints to stdout       → plays well with docker logs, journalctl, any log collector
    """

    # Truncate long messages so lines stay scannable in a terminal
    _MAX_MSG_LEN = 120

    async def handle(self, update: IncidentUpdate) -> None:
        print(self._format(update), flush=True)

    def _format(self, u: IncidentUpdate) -> str:
        affected = ", ".join(u.affected_components) if u.affected_components else "N/A"
        message  = self._truncate(u.message)
        status   = _color_status(u.status)
        impact   = _color_impact(u.impact)

        return (
            f"[{_ts()}] "
            f"{u.provider} | "
            f"{status} | "
            f"Impact={impact} | "
            f"Product={u.incident_name} | "
            f"Affected={affected} | "
            # f"Message={message}"
        )

    def _truncate(self, text: str) -> str:
        text = " ".join(text.split())          # collapse internal whitespace
        if len(text) <= self._MAX_MSG_LEN:
            return text
        return text[: self._MAX_MSG_LEN - 1].rstrip() + "…"
