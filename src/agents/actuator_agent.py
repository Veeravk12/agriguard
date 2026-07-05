from datetime import datetime, timezone


def execute(zone_id: str, action: str, block_reason: str | None) -> dict:
    """Simulated actuator — logs what would have happened rather than
    driving real hardware."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": zone_id,
        "action": action,
        "executed": action != "no_action",
        "block_reason": block_reason,
    }
    print(f"[ACTUATOR] zone={zone_id} action={action} executed={result['executed']}"
          + (f" ({block_reason})" if block_reason else ""))
    return result
