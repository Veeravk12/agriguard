from datetime import datetime, timezone

STALE_AFTER_MINUTES = 15


class SensorAggregator:
    """Holds the single source of truth per zone: latest-value-wins per
    field, each timestamped independently so sensors can write on their own
    schedule without stepping on each other. No LLM calls happen here.
    """

    def __init__(self):
        self._state: dict[str, dict] = {}

    def ingest(self, reading: dict) -> None:
        zone_id = reading["zone_id"]
        zone_state = self._state.setdefault(zone_id, {})
        for field, value in reading.items():
            if field == "zone_id":
                continue
            zone_state[field] = value

    def snapshot(self, zone_id: str) -> dict:
        """Return one consolidated snapshot for a zone, flagging it stale if
        the last reading is older than STALE_AFTER_MINUTES rather than
        silently reusing an old cached value."""
        zone_state = self._state.get(zone_id, {})
        result = {"zone_id": zone_id, **zone_state}

        timestamp = zone_state.get("timestamp")
        if timestamp:
            age_minutes = (
                datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)
            ).total_seconds() / 60
            if age_minutes > STALE_AFTER_MINUTES:
                result["stale"] = True

        return result
