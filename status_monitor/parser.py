
# parses the Statuspage.io /api/v2/incidents.json response into IncidentUpdate
# objects — one per update entry, not one per incident.

# Design decisions:
#   - One IncidentUpdate per update entry (not per incident) so the differ can
#     track each lifecycle transition individually by its update_id.
#   - Sorts update entries by updated_at before processing — API ordering
#     is not contractually guaranteed.
#   - All timestamps are parsed to datetime objects (never kept as raw strings).
#   - Component status check uses .get("status", "") — prevents silent bugs
#     from None comparisons when the key is absent.

from datetime import datetime, timezone
from status_monitor.models import IncidentUpdate, parse_dt

def _sort_key(entry: dict) -> datetime:
    """Safe sort key: entries with missing/unparseable updated_at sort first."""
    return parse_dt(entry.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)

def parse_incidents(provider: str, data: dict) -> list[IncidentUpdate]:
    """
    Parse a Statuspage.io incidents.json payload.

    Returns a flat, chronologically sorted list of IncidentUpdate objects —
    one per update entry across all incidents in the response.
    """
    result: list[IncidentUpdate] = []

    for incident in data.get("incidents", []):
        incident_updates = incident.get("incident_updates", [])
        if not incident_updates:
            continue

        incident_id     = incident.get("id", "")
        incident_name   = incident.get("name", "Unknown Incident")
        impact          = incident.get("impact", "unknown")
        shortlink       = incident.get("shortlink", "")
        incident_status = incident.get("status", "unknown")

        # Collect components that are actively degraded.
        # .get("status", "") ensures a missing key doesn't accidentally match
        # the "not operational" condition (None != "operational" is always True).
        affected = [
            c.get("name", "Unknown")
            for c in incident.get("components", [])
            if c.get("status", "") not in ("operational", "")
        ]
        if not affected:
            # fall back to all listed components if none are flagged as degraded
            affected = [c.get("name", "Unknown") for c in incident.get("components", [])]

        # Sort entries chronologically — do not trust API-implied ordering
        for entry in sorted(incident_updates, key=_sort_key):
            result.append(IncidentUpdate(
                provider=provider,
                incident_id=incident_id,
                update_id=entry.get("id", ""),
                incident_name=incident_name,
                status=entry.get("status", incident_status),
                impact=impact,
                affected_components=affected,
                message=entry.get("body", "No message provided."),
                updated_at=parse_dt(entry.get("updated_at")),
                shortlink=shortlink,
            ))

    # final sort across all incidents by time so events fire in chronological order
    result.sort(key=lambda u: u.updated_at or datetime.min.replace(tzinfo=timezone.utc))
    return result