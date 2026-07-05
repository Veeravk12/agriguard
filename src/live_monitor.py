"""Live monitoring mode: sensors keep writing in the background every few
seconds, a decision cycle runs on its own slower cadence, and the dashboard
regenerates after every cycle so it's always current in the browser.

Gemini quota is scarce and the two models rarely disagree, so gambling a
limited quota on live escalations happening to disagree isn't reliable. This
loop guarantees the first few escalations use a real, unmocked consensus +
notification pass against a clearly labeled illustrative cloud opinion (no
Gemini call spent), then spends a capped number of real Gemini calls on
whatever escalations come after that. Once the budget's used up it fails
safe — treats further escalations as quota-exhausted rather than guessing.

Stop with Ctrl+C.
"""

import random
import threading
import time

from src import config, metrics, trace_logger
from src.agents import actuator_agent, chat_agent, local_decision_agent, notification_agent, query_agent, safety_rules
from src.orchestrator import needs_escalation, run_cycle
from src.sensors.aggregator_agent import SensorAggregator
from src.sensors.sensor_simulator import generate_reading

LIVE_CYCLE_SECONDS = 10
SENSOR_WRITE_SECONDS = 3
REPLY_POLL_SECONDS = 5
DEMO_HUMAN_IN_LOOP_TARGET = 3
MAX_LIVE_GEMINI_CALLS = 5

# The sensor simulator's default baseline is deliberately "healthy" (kept
# narrow so the scripted demo in data/scenarios.json stays deterministic),
# which means pure random live readings almost never cross an escalation
# threshold on their own — pest risk never gets high enough to trigger
# spray_pesticide, so there'd be nothing to escalate, ever. Real farms do
# get occasional pest spikes or dry spells, so simulate that here: each
# sensor write has a chance of reporting a spike instead of a calm reading.
ANOMALY_PROBABILITY = 0.3

ZONE_ID = config.ZONE_IDS[0]

_stop_event = threading.Event()
_demo_disagreements_shown = 0
_gemini_calls_used = 0

_pending_lock = threading.Lock()
_pending_human_reviews: list[dict] = []
_aggregator: SensorAggregator | None = None


def _sensor_writer(aggregator: SensorAggregator):
    """Independent "sensors" writing on their own cadence. The decision loop
    below just reads whatever's latest whenever it runs, so a reading that
    lands mid-cycle is queued in the aggregator's shared state, not lost."""
    while not _stop_event.is_set():
        overrides = None
        if random.random() < ANOMALY_PROBABILITY:
            overrides = {"pest_risk_score": round(random.uniform(0.7, 0.95), 2)}
        reading = generate_reading(ZONE_ID, overrides=overrides)
        aggregator.ingest(reading)
        flag = " [PEST SPIKE]" if overrides else ""
        print(f"[SENSOR] zone={ZONE_ID} reading queued — "
              f"soil={reading['soil_moisture_pct']}% pest={reading['pest_risk_score']} "
              f"leaf={reading['leaf_health_score']}{flag}")
        _stop_event.wait(SENSOR_WRITE_SECONDS)


def _forced_demo_cloud_decision(cycle_num: int) -> dict:
    """A clearly labeled illustrative cloud decision, guaranteed to disagree
    with a routine local escalation, so the human-in-the-loop path shows up
    without spending real Gemini quota. See module docstring."""
    return {
        "action": "uncertain",
        "confidence": 0.3,
        "reasoning": f"[DEMO cycle {cycle_num}] illustrative second opinion — genuinely "
                     f"diverges from the local agent to demonstrate the human-in-the-loop "
                     f"path deterministically (real disagreement is rare between two "
                     f"well-calibrated models; not a live Gemini call).",
    }


def _budget_exhausted_cloud_decision() -> dict:
    return {
        "action": "uncertain",
        "confidence": 0.0,
        "reasoning": f"Live session's Gemini call budget ({MAX_LIVE_GEMINI_CALLS}) is "
                     f"exhausted — failing safe to human escalation instead of spending "
                     f"more of the remaining API quota.",
    }


def _register_pending_review(result: dict):
    options = query_agent.build_options(
        result["local_decision"].get("action", "uncertain"),
        result["cloud_decision"].get("action", "uncertain"),
    )
    with _pending_lock:
        _pending_human_reviews.append({
            "zone_id": result["zone_id"],
            "snapshot": result["snapshot"],
            "local_decision": result["local_decision"],
            "cloud_decision": result["cloud_decision"],
            "options": options,
        })
    menu = ", ".join(f"{i}={opt}" for i, opt in enumerate(options, start=1))
    print(f"[QUERY AGENT] awaiting your Telegram reply for zone={result['zone_id']} ({menu})")


def _status_message() -> str:
    if _aggregator is None:
        return "Still starting up — no readings yet."

    snapshot = _aggregator.snapshot(ZONE_ID)
    lines = [f"Zone {ZONE_ID} — current readings:"]
    for field, (label, unit) in notification_agent.SNAPSHOT_LABELS.items():
        if field not in snapshot:
            continue
        value = snapshot[field]
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        lines.append(f"  {label}: {value}{unit}")

    with _pending_lock:
        pending_count = len(_pending_human_reviews)
    if pending_count:
        lines.append(f"\n{pending_count} decision(s) waiting on your reply — reply with a number.")
    else:
        lines.append("\nNothing waiting on you right now, everything's resolving on its own.")
    return "\n".join(lines)


def _handle_reply(text: str):
    if query_agent.is_status_query(text):
        notification_agent.notify(_status_message())
        return

    with _pending_lock:
        pending = _pending_human_reviews[0] if _pending_human_reviews else None
        action = query_agent.parse_reply(text, pending["options"]) if pending else None
        if pending and action is not None:
            _pending_human_reviews.pop(0)

    if pending and action is not None:
        _resolve_pending_decision(text, pending, action)
        return

    # Not a menu pick (or nothing's pending right now) — treat it as a
    # question and let the local model answer instead of staying silent.
    snapshot = _aggregator.snapshot(ZONE_ID) if _aggregator else {}
    recent = trace_logger.read_all()[-5:]
    answer = chat_agent.reply(text, snapshot, recent, pending)
    notification_agent.notify(answer)
    print(f"[CHAT AGENT] {text!r} -> {answer!r}")


def _resolve_pending_decision(text: str, pending: dict, action: str):
    zone_id = pending["zone_id"]
    snapshot = pending["snapshot"]
    final_action, block_reason = safety_rules.apply(snapshot, action)
    print(f"[QUERY AGENT] reply {text!r} -> action={action} "
          f"[SAFETY RULE LAYER] -> final={final_action}"
          + (f" ({block_reason})" if block_reason else " (no override)"))

    actuator_agent.execute(zone_id, final_action, block_reason)
    metrics.record(zone_id, "human_confirmed", final_action, 1.0, block_reason)
    trace_logger.record(
        zone_id, snapshot, pending["local_decision"], escalated=True,
        cloud_decision=pending["cloud_decision"], resolution="human_confirmed",
        decision_source="human_confirmed", final_action=final_action,
        block_reason=block_reason, notification_channel=None,
    )

    chosen_label = query_agent.ACTION_LABELS.get(action, action)
    if block_reason:
        confirmation = f"Got it — you chose {chosen_label.lower()}, but safety rules blocked it: {block_reason}."
    else:
        confirmation = f"Got it — {chosen_label.lower()} now."
    notification_agent.notify(confirmation)
    print(f"[NOTIFICATION AGENT] {confirmation}")
    _regenerate_dashboard()


def _reply_listener():
    last_update_id = query_agent.get_latest_update_id()
    while not _stop_event.is_set():
        replies, last_update_id = query_agent.fetch_new_replies(last_update_id)
        for text in replies:
            _handle_reply(text)
        _stop_event.wait(REPLY_POLL_SECONDS)


def _regenerate_dashboard():
    from dashboard.dashboard import REPORT_PATH, generate
    with open(REPORT_PATH, "w") as f:
        f.write(generate(auto_refresh_seconds=LIVE_CYCLE_SECONDS))


def _print_dashboard_path():
    import os
    import re

    abs_path = os.path.abspath("dashboard/report.html")
    print(f"\nDashboard (auto-refreshes every {LIVE_CYCLE_SECONDS}s): file://{abs_path}")
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", abs_path)
    if match:
        drive, rest = match.groups()
        print(f"On WSL, your Windows browser needs: {drive.upper()}:\\{rest.replace('/', chr(92))}")
    print("Open that now — it'll update on its own as cycles run below.\n")


def main():
    global _gemini_calls_used, _demo_disagreements_shown, _aggregator

    print("=" * 70)
    print("AgriGuard — live monitoring mode")
    print(f"Decision cycle every {LIVE_CYCLE_SECONDS}s, sensors writing every {SENSOR_WRITE_SECONDS}s")
    print(f"First {DEMO_HUMAN_IN_LOOP_TARGET} escalations: guaranteed human-in-the-loop demo "
          f"(no Gemini spent). After that: up to {MAX_LIVE_GEMINI_CALLS} real Gemini calls.")
    print("Press Ctrl+C to stop.")
    print("=" * 70)

    aggregator = SensorAggregator()
    _aggregator = aggregator
    aggregator.ingest(generate_reading(ZONE_ID))  # seed a reading before cycle 1 runs
    _regenerate_dashboard()
    _print_dashboard_path()

    writer_thread = threading.Thread(target=_sensor_writer, args=(aggregator,), daemon=True)
    writer_thread.start()

    reply_thread = None
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        reply_thread = threading.Thread(target=_reply_listener, daemon=True)
        reply_thread.start()
        print(f"[QUERY AGENT] listening for Telegram replies every {REPLY_POLL_SECONDS}s "
              f"— reply to an alert with its number, or just ask \"status\" any time")
    else:
        print("[QUERY AGENT] Telegram not configured — replies won't be picked up")

    cycle_num = 0
    try:
        while True:
            cycle_num += 1
            print(f"\n{'=' * 25} Cycle {cycle_num} — {time.strftime('%H:%M:%S')} {'=' * 25}")

            snapshot = aggregator.snapshot(ZONE_ID)
            decision = local_decision_agent.decide(snapshot)

            if needs_escalation(decision):
                if _demo_disagreements_shown < DEMO_HUMAN_IN_LOOP_TARGET:
                    _demo_disagreements_shown += 1
                    print(f"[ORCHESTRATOR] guaranteeing human-in-the-loop demo #{_demo_disagreements_shown}"
                          f"/{DEMO_HUMAN_IN_LOOP_TARGET} for this escalation")
                    override = _forced_demo_cloud_decision(cycle_num)
                elif _gemini_calls_used < MAX_LIVE_GEMINI_CALLS:
                    _gemini_calls_used += 1
                    print(f"[ORCHESTRATOR] spending a real Gemini call "
                          f"({_gemini_calls_used}/{MAX_LIVE_GEMINI_CALLS} this session)")
                    override = None
                else:
                    print("[ORCHESTRATOR] Gemini call budget exhausted for this session")
                    override = _budget_exhausted_cloud_decision()
            else:
                override = None

            result = run_cycle(
                aggregator, ZONE_ID,
                precomputed_snapshot=snapshot,
                precomputed_decision=decision,
                cloud_decision_override=override,
            )
            if result.get("resolution") == "disagree":
                _register_pending_review(result)
            _regenerate_dashboard()

            _stop_event.wait(LIVE_CYCLE_SECONDS)
    except KeyboardInterrupt:
        print("\n\nStopping live monitor...")
        _stop_event.set()
        writer_thread.join(timeout=2)
        if reply_thread:
            reply_thread.join(timeout=REPLY_POLL_SECONDS + 2)
        print("\n=== Final cost summary ===")
        print(metrics.summary())
        print(f"\nHuman-in-the-loop demos shown: {_demo_disagreements_shown}")
        print(f"Real Gemini calls used: {_gemini_calls_used}")
        with _pending_lock:
            if _pending_human_reviews:
                print(f"Still awaiting a reply for {len(_pending_human_reviews)} escalation(s) — "
                      f"they'll be dropped now that the session is stopping.")


if __name__ == "__main__":
    main()
