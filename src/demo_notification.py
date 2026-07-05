"""Demo-only trigger for the disagreement / human-notification path.

Genuine disagreement between the Local and Cloud agents is rare in practice,
so waiting for a live one to happen isn't a great way to see the Telegram
alert. This runs the real consensus_agent.decide() and notification_agent.
notify() — nothing about the notification path is mocked — against a
hand-crafted, clearly labeled pair of decisions instead.
"""

from src.agents import consensus_agent, notification_agent


def main():
    zone_id = "zone_1"
    snapshot = {
        "zone_id": zone_id,
        "soil_moisture_pct": 38,
        "pest_risk_score": 0.7,
        "leaf_health_score": 0.55,
        "temperature_c": 31,
        "wind_speed_kmh": 6.0,
        "power_available": True,
        "forecast_rain_next_6h": False,
    }
    local_decision = {
        "action": "irrigate",
        "confidence": 0.9,
        "reasoning": "[DEMO] Soil moisture reads low; irrigation recommended.",
    }
    cloud_decision = {
        "action": "spray_pesticide",
        "confidence": 0.88,
        "reasoning": "[DEMO] Pest risk reads high; pesticide recommended instead.",
    }

    print("=== DEMO: illustrative snapshot + local vs. cloud decisions (not live model output) ===")
    print(f"Snapshot: {snapshot}")
    print(f"Local: {local_decision}")
    print(f"Cloud: {cloud_decision}")

    resolution, decision_source = consensus_agent.decide(local_decision, cloud_decision)
    print(f"[CONSENSUS AGENT] {resolution.upper()} -> decision_source={decision_source}")

    if resolution == "disagree":
        alert = notification_agent.format_disagreement_alert(zone_id, snapshot, local_decision, cloud_decision)
        channel = notification_agent.notify(f"[DEMO]\n{alert}")
        print(f"[NOTIFICATION AGENT] sent via: {channel}")
    else:
        print("(models agreed — no notification would be sent; this demo pair is designed to disagree)")


if __name__ == "__main__":
    main()
