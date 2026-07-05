import csv
import os
from datetime import datetime, timezone

from src import config

_FIELDNAMES = [
    "timestamp",
    "zone_id",
    "decision_source",
    "action",
    "confidence",
    "block_reason",
    "estimated_cost_usd",
]


def _ensure_log_file():
    os.makedirs(os.path.dirname(config.DECISIONS_LOG_PATH), exist_ok=True)
    if not os.path.exists(config.DECISIONS_LOG_PATH):
        with open(config.DECISIONS_LOG_PATH, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=_FIELDNAMES).writeheader()


_COST_INCURRING_SOURCES = {"escalated_to_gemini", "escalated_to_human"}


def record(zone_id: str, decision_source: str, action: str, confidence: float, block_reason: str | None):
    """decision_source is one of: 'local', 'escalated_to_gemini',
    'escalated_to_human', or 'human_confirmed' (a farm owner's Telegram
    reply resolving an earlier escalation — free, and not counted as a
    second decision in the cost story, see summary())."""
    _ensure_log_file()
    estimated_cost = (
        config.ESTIMATED_GEMINI_COST_PER_CALL_USD if decision_source in _COST_INCURRING_SOURCES else 0.0
    )
    with open(config.DECISIONS_LOG_PATH, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_FIELDNAMES).writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "zone_id": zone_id,
                "decision_source": decision_source,
                "action": action,
                "confidence": confidence,
                "block_reason": block_reason or "",
                "estimated_cost_usd": estimated_cost,
            }
        )


def summary() -> dict:
    """Cost-savings story: % resolved locally vs escalated, and actual cost
    vs. a hypothetical all-cloud baseline.

    'human_confirmed' rows are excluded from the count — they're a
    follow-up on an already-counted 'escalated_to_human' row, not a second
    decision — and reported separately as human_confirmations.
    """
    _ensure_log_file()
    with open(config.DECISIONS_LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    decision_rows = [r for r in rows if r["decision_source"] != "human_confirmed"]
    human_confirmations = sum(1 for r in rows if r["decision_source"] == "human_confirmed")

    total = len(decision_rows)
    if total == 0:
        return {"total_decisions": 0, "human_confirmations": human_confirmations}

    local_count = sum(1 for r in decision_rows if r["decision_source"] == "local")
    gemini_count = sum(1 for r in decision_rows if r["decision_source"] == "escalated_to_gemini")
    human_count = sum(1 for r in decision_rows if r["decision_source"] == "escalated_to_human")
    actual_cost = sum(float(r["estimated_cost_usd"]) for r in decision_rows)
    hypothetical_all_cloud_cost = total * config.ESTIMATED_GEMINI_COST_PER_CALL_USD

    return {
        "total_decisions": total,
        "pct_local": round(100 * local_count / total, 1),
        "pct_escalated_to_gemini": round(100 * gemini_count / total, 1),
        "pct_escalated_to_human": round(100 * human_count / total, 1),
        "human_confirmations": human_confirmations,
        "actual_cost_usd": round(actual_cost, 4),
        "hypothetical_all_cloud_cost_usd": round(hypothetical_all_cloud_cost, 4),
        "savings_usd": round(hypothetical_all_cloud_cost - actual_cost, 4),
        "savings_pct": round(
            100 * (hypothetical_all_cloud_cost - actual_cost) / hypothetical_all_cloud_cost, 1
        )
        if hypothetical_all_cloud_cost
        else 0.0,
    }
