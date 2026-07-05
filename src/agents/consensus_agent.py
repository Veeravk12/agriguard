def decide(local_decision: dict, cloud_decision: dict) -> tuple[str, str]:
    """Plain comparison between the Local and Cloud decisions, no LLM
    involved. Returns (resolution, decision_source): resolution is "agree"
    or "disagree"; decision_source is "escalated_to_gemini" on agreement,
    "escalated_to_human" on disagreement.
    """
    local_action = local_decision.get("action", "uncertain")
    cloud_action = cloud_decision.get("action", "uncertain")

    if local_action == cloud_action and local_action != "uncertain":
        return "agree", "escalated_to_gemini"

    return "disagree", "escalated_to_human"
