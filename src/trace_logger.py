"""Per-cycle agent trace log: what data went in, what each model said, what
they agreed or disagreed on, what happened. Separate from metrics.py's
compact cost/decision CSV. Read by dashboard.dashboard for the agent
activity view.
"""

import json
import os
from datetime import datetime, timezone

TRACE_LOG_PATH = "data/logs/agent_trace.jsonl"


def _ensure_log_dir():
    os.makedirs(os.path.dirname(TRACE_LOG_PATH), exist_ok=True)


def record(
    zone_id: str,
    snapshot: dict,
    local_decision: dict,
    escalated: bool,
    cloud_decision: dict | None,
    resolution: str | None,
    decision_source: str,
    final_action: str,
    block_reason: str | None,
    notification_channel: str | None,
) -> None:
    _ensure_log_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": zone_id,
        "snapshot": snapshot,
        "local_decision": local_decision,
        "escalated": escalated,
        "cloud_decision": cloud_decision,
        "resolution": resolution,
        "decision_source": decision_source,
        "final_action": final_action,
        "block_reason": block_reason,
        "notification_channel": notification_channel,
    }
    with open(TRACE_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_all() -> list[dict]:
    if not os.path.exists(TRACE_LOG_PATH):
        return []
    with open(TRACE_LOG_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]
