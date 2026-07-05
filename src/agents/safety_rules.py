from src import config


def apply(snapshot: dict, proposed_action: str) -> tuple[str, str | None]:
    """Deterministic safety gate, independent of any model's opinion —
    including a human's Telegram reply. Returns (final_action, block_reason);
    block_reason is None if proposed_action was allowed through unchanged.
    """
    if proposed_action == "spray_pesticide":
        if snapshot.get("wind_speed_kmh", 0) > config.MAX_WIND_SPEED_KMH_FOR_SPRAY:
            return "no_action", "blocked: wind_speed exceeds spray safety limit"
        if not snapshot.get("power_available", True):
            return "no_action", "blocked: no power available for drone operation"

    if proposed_action == "irrigate":
        if config.RAIN_FORECAST_BLOCKS_IRRIGATION and snapshot.get(
            "forecast_rain_next_6h", False
        ):
            return "no_action", "blocked: rain forecast within next 6 hours"

    return proposed_action, None
