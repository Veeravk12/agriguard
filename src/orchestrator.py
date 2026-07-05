import json

from src import config, metrics, trace_logger
from src.agents import (
    actuator_agent,
    cloud_reasoning_agent,
    consensus_agent,
    local_decision_agent,
    notification_agent,
    safety_rules,
)
from src.sensors.aggregator_agent import SensorAggregator
from src.sensors.sensor_simulator import generate_reading


HIGH_STAKES_ACTIONS = {"spray_pesticide"}


def needs_escalation(decision: dict) -> bool:
    """True if a decision needs a second opinion: low confidence, uncertain,
    or a high-stakes action like spray_pesticide."""
    action = decision.get("action", "uncertain")
    confidence = decision.get("confidence", 0.0)
    return (
        confidence < config.CONFIDENCE_THRESHOLD
        or action == "uncertain"
        or action in HIGH_STAKES_ACTIONS
    )


def run_cycle(
    aggregator: SensorAggregator,
    zone_id: str,
    precomputed_snapshot: dict | None = None,
    precomputed_decision: dict | None = None,
    cloud_decision_override: dict | None = None,
) -> dict:
    """One decision cycle for a zone: aggregator snapshot -> local decision
    agent -> (if confident and routine) safety gate -> actuator, OR (if low
    confidence, uncertain, or high-stakes) cloud escalation -> consensus ->
    safety gate -> actuator / human notification.

    The precomputed_* / cloud_decision_override params let live_monitor.py
    reuse a snapshot and decision it already has (so a background sensor
    write can't land between the two and desync them) and swap in a
    demo/budget-exhausted cloud opinion without calling Gemini.
    """
    snapshot = precomputed_snapshot if precomputed_snapshot is not None else aggregator.snapshot(zone_id)
    print(f"\n[SENSOR AGGREGATOR] zone={zone_id} snapshot fed to Local Decision Agent:")
    print(f"  {json.dumps(snapshot)}")

    if precomputed_decision is not None:
        decision = precomputed_decision
    else:
        decision = local_decision_agent.decide(snapshot)
    print(f"[LOCAL DECISION AGENT] (Ollama/{config.OLLAMA_MODEL}) says:")
    print(f"  action={decision.get('action')} confidence={decision.get('confidence')}")
    print(f"  reasoning: {decision.get('reasoning')}")

    action = decision.get("action", "uncertain")
    confidence = decision.get("confidence", 0.0)

    if not needs_escalation(decision):
        final_action, block_reason = safety_rules.apply(snapshot, action)
        print(f"[SAFETY RULE LAYER] proposed={action} -> final={final_action}"
              + (f" ({block_reason})" if block_reason else " (no override)"))
        result = actuator_agent.execute(zone_id, final_action, block_reason)
        metrics.record(zone_id, "local", final_action, confidence, block_reason)
        trace_logger.record(
            zone_id, snapshot, decision, escalated=False, cloud_decision=None,
            resolution=None, decision_source="local", final_action=final_action,
            block_reason=block_reason, notification_channel=None,
        )
        return {**result, "resolution": "local", "local_decision": decision, "cloud_decision": None, "snapshot": snapshot}

    print(f"[ORCHESTRATOR] confidence={confidence} action={action} — needs a second opinion "
          f"(low confidence, uncertain, or high-stakes) — escalating to Cloud Reasoning Agent")

    if cloud_decision_override is not None:
        cloud_decision = cloud_decision_override
        print("[CLOUD REASONING AGENT] (override, not a live API call) says:")
    else:
        cloud_decision = cloud_reasoning_agent.decide(snapshot, decision)
        print(f"[CLOUD REASONING AGENT] ({config.GEMINI_MODEL}) says:")
    print(f"  action={cloud_decision.get('action')} confidence={cloud_decision.get('confidence')}")
    print(f"  reasoning: {cloud_decision.get('reasoning')}")

    resolution, decision_source = consensus_agent.decide(decision, cloud_decision)
    print(f"[CONSENSUS AGENT] local={decision.get('action')} vs cloud={cloud_decision.get('action')} "
          f"-> {resolution.upper()}")

    if resolution == "agree":
        agreed_action = cloud_decision["action"]
        agreed_confidence = min(confidence, cloud_decision.get("confidence", 0.0))
        final_action, block_reason = safety_rules.apply(snapshot, agreed_action)
        print(f"[SAFETY RULE LAYER] proposed={agreed_action} -> final={final_action}"
              + (f" ({block_reason})" if block_reason else " (no override)"))
        result = actuator_agent.execute(zone_id, final_action, block_reason)
        metrics.record(zone_id, decision_source, final_action, agreed_confidence, block_reason)
        trace_logger.record(
            zone_id, snapshot, decision, escalated=True, cloud_decision=cloud_decision,
            resolution=resolution, decision_source=decision_source, final_action=final_action,
            block_reason=block_reason, notification_channel=None,
        )
        return {**result, "resolution": resolution, "local_decision": decision, "cloud_decision": cloud_decision, "snapshot": snapshot}

    alert = notification_agent.format_disagreement_alert(zone_id, snapshot, decision, cloud_decision)
    channel = notification_agent.notify(alert)
    print(f"[NOTIFICATION AGENT] sent via: {channel}")
    metrics.record(zone_id, decision_source, "no_action", confidence, "disagreement — human escalation")
    trace_logger.record(
        zone_id, snapshot, decision, escalated=True, cloud_decision=cloud_decision,
        resolution=resolution, decision_source=decision_source, final_action="no_action",
        block_reason="disagreement — human escalation", notification_channel=channel,
    )
    return {
        "zone_id": zone_id, "action": "no_action", "executed": False,
        "block_reason": "disagreement — human escalation",
        "resolution": resolution, "local_decision": decision, "cloud_decision": cloud_decision, "snapshot": snapshot,
    }


def run_scripted_scenarios(scenarios_path: str = "data/scenarios.json"):
    """Feeds each scripted scenario through one decision cycle — a reliable,
    reproducible demo instead of live randomness."""
    with open(scenarios_path) as f:
        scenarios = json.load(f)

    aggregator = SensorAggregator()
    for scenario in scenarios:
        print(f"\n=== Scenario {scenario['id']}: {scenario['name']} ===")
        reading = generate_reading(scenario["zone_id"], overrides=scenario["overrides"])
        aggregator.ingest(reading)
        run_cycle(aggregator, scenario["zone_id"])

    print("\n=== Cost summary ===")
    print(metrics.summary())


if __name__ == "__main__":
    run_scripted_scenarios()
