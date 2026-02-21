from status_monitor.models import IncidentUpdate

class IncidentDiffer:
    """
    Tracks seen update_ids so we never emit the same update twice.

    Why track update_id and not incident.updated_at?

    The old approach (incident_id → updated_at) collapsed all update entries
    for one incident into a single record. If an incident went through two
    transitions between polls (e.g. investigating → identified → monitoring),
    only 'monitoring' would surface — the intermediate step was silently lost.

    By tracking every individual update_id, we guarantee:
      - Every lifecycle transition fires its own event
      - No intermediate steps are lost regardless of poll frequency
      - Already-seen entries are never re-emitted (no duplicate alerts)
    """

    def __init__(self) -> None:
        self._seen_update_ids: set[str] = set()

    def diff(self, updates: list[IncidentUpdate]) -> list[IncidentUpdate]:
        """
        Return only update entries whose update_id hasn't been emitted before.
        Updates the internal seen-set as a side effect.
        """
        novel: list[IncidentUpdate] = []
        for update in updates:
            if update.update_id not in self._seen_update_ids:
                novel.append(update)
                self._seen_update_ids.add(update.update_id)
        return novel