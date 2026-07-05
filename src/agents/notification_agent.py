import requests

from src import config
from src.agents.query_agent import ACTION_LABELS, build_options

SNAPSHOT_LABELS = {
    "soil_moisture_pct": ("Soil moisture", "%"),
    "pest_risk_score": ("Pest risk", ""),
    "leaf_health_score": ("Leaf health", ""),
    "temperature_c": ("Temperature", "°C"),
    "wind_speed_kmh": ("Wind speed", " km/h"),
    "power_available": ("Power available", ""),
    "forecast_rain_next_6h": ("Rain forecast (6h)", ""),
}


def format_disagreement_alert(
    zone_id: str, snapshot: dict, local_decision: dict, cloud_decision: dict
) -> str:
    """Readable farm-status alert with a numbered menu to reply with,
    shown when the Local and Cloud agents disagree and a human needs to
    make the call."""
    conditions = []
    for field, (label, unit) in SNAPSHOT_LABELS.items():
        if field not in snapshot:
            continue
        value = snapshot[field]
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        conditions.append(f"  {label}: {value}{unit}")

    options = build_options(
        local_decision.get("action", "uncertain"), cloud_decision.get("action", "uncertain")
    )
    menu = "\n".join(f"  {i}. {ACTION_LABELS.get(opt, opt)}" for i, opt in enumerate(options, start=1))

    return (
        f"AgriGuard Alert — Zone {zone_id}\n"
        f"Local and Cloud models disagree — no action taken, please review.\n"
        f"\n"
        f"Farm conditions:\n" + "\n".join(conditions) + "\n"
        f"\n"
        f"Local Decision Agent (Ollama): {local_decision.get('action', '?').upper()} "
        f"(confidence {local_decision.get('confidence', '?')})\n"
        f"  \"{local_decision.get('reasoning', '')}\"\n"
        f"\n"
        f"Cloud Reasoning Agent (Gemini): {cloud_decision.get('action', '?').upper()} "
        f"(confidence {cloud_decision.get('confidence', '?')})\n"
        f"  \"{cloud_decision.get('reasoning', '')}\"\n"
        f"\n"
        f"Reply with a number to decide:\n" + menu + "\n"
        "\n"
        "(or just reply \"status\" any time for the latest readings)"
    )


def notify(message: str) -> str:
    """Sends `message` as-is over Telegram if it's configured, otherwise
    prints it to the console. Returns which channel was actually used."""
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(
                url,
                json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
                timeout=10,
            )
            return "telegram"
        except requests.RequestException as exc:
            print(f"[NOTIFICATION] Telegram send failed ({exc!r}), falling back to console")

    print(f"[NOTIFICATION] {message}")
    return "console"
