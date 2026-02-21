import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

def parse_dt(value: str | None) -> datetime | None:
    """
    Parse an ISO 8601 timestamp string into an aware UTC datetime.

    Statuspage returns strings like '2024-11-03T14:32:00.000Z'.
    We store datetimes (not raw strings) so:
      - Comparison is chronologically correct, never lexicographic
      - Timezone bugs surface at parse time, not silently during comparison
      - Display formatting is controlled in one place
    """
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        log.warning("Could not parse datetime string: %r", value)
        return None


def format_dt(dt: datetime | None) -> str:
    """Human-readable UTC timestamp for console display."""
    if dt is None:
        return "Unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class IncidentUpdate:
    """
    Represents ONE update entry within an incident — not the incident itself.

    Key design: one object per update_id (not per incident).
    If an incident transitions through several statuses between polls,
    we emit one event per transition — no lifecycle step is ever lost.
    """
    provider: str
    incident_id: str
    update_id: str                 # unique id of this specific update entry
    incident_name: str
    status: str                    # investigating | identified | monitoring | resolved
    impact: str                    # none | minor | major | critical
    affected_components: list[str]
    message: str                   # body of this specific update entry
    updated_at: datetime | None    # stored as datetime, not str
    shortlink: str
