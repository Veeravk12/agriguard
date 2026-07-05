import random
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_reading(zone_id: str, overrides: dict | None = None) -> dict:
    """Generate one synthetic sensor reading for a zone.

    Each field simulates an independent sensor writing at its own cadence —
    callers normally set only the fields relevant to a scenario via `overrides`
    and let the rest default to a "healthy baseline" random reading.
    """
    reading = {
        "timestamp": _now(),
        "zone_id": zone_id,
        "soil_moisture_pct": round(random.uniform(60, 75), 1),
        "leaf_health_score": round(random.uniform(0.8, 1.0), 2),
        "pest_risk_score": round(random.uniform(0.0, 0.2), 2),
        "temperature_c": round(random.uniform(22, 30), 1),
        "wind_speed_kmh": round(random.uniform(2, 10), 1),
        "wind_direction": random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
        "power_available": True,
        "forecast_rain_next_6h": False,
    }
    if overrides:
        reading.update(overrides)
    return reading
