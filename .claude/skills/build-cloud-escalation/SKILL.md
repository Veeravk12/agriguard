---
name: build-cloud-escalation
description: Implement AgriGuard's Should-have tier — the Gemini Cloud Reasoning Agent, the deterministic Consensus Agent, and the Notification Agent — and wire them into the orchestrator's escalation path (currently stubbed). Use once the Must-have local-only loop (run-local-demo) passes cleanly.
---

# Build Cloud Escalation (Should-have Tier)

Extends AgriGuard (`kaggle_project/agriguard/`) past the local-only Must-have loop by wiring in Gemini escalation, consensus, and farm-owner notification — matching Section 5 (steps 4-7) and Section 4 of `AgriGuard_Project_Plan.md`. Only start this after `run-local-demo`'s Must-have scenarios (1, 2, 5, 6) pass.

## Design constraints (from the plan — don't relitigate these)

- Cloud Reasoning Agent is a real ADK `LlmAgent` using ADK's native Gemini support (not LiteLLM — that's only needed for Ollama). Model: `config.GEMINI_MODEL`. Use `config.GEMINI_API_KEY`.
- Same JSON schema as the local agent: `{"action": ..., "confidence": ..., "reasoning": ...}` — build the Gemini prompt so both agents answer against the identical schema, so the Consensus Agent can compare `action` fields directly.
- Consensus Agent and Safety Rule Layer are **deterministic Python, not agents/LLM calls** — this is a security/safety talking point in Section 8 (models can't override the safety gate), don't reintroduce an LLM into this comparison step.
- Consensus logic (Section 5, step 7): if local and Gemini `action` fields agree → proceed to `safety_rules.apply`. If they disagree, or Gemini also returns `"uncertain"` → do **not** act; call the Notification Agent with both opinions and reasoning, and log as `escalated_to_human` (see `metrics.record`'s `decision_source` values).
- Fail-safe on Gemini errors/timeouts/rate limits (Section 12.B): default to `no_action`, log the failure, and queue for retry — never default to an unverified autonomous action.
- Notification Agent: Telegram Bot API if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are set in `.env`, else fall back to a console/log message — don't make Telegram a hard dependency for this tier to be considered done.

## Files to create

1. `src/agents/cloud_reasoning_agent.py` — mirror the structure of `src/agents/local_decision_agent.py` (already built) but use ADK's Gemini model instead of `LiteLlm`, and `config.GEMINI_MODEL`/`config.GEMINI_API_KEY`. Same JSON-parse-with-fallback pattern.
2. `src/agents/consensus_agent.py` — pure function `decide(local_decision: dict, cloud_decision: dict) -> tuple[str, str]` returning `(resolution, decision_source)` where `resolution` is `"agree"` or `"disagree"` and `decision_source` is one of the `metrics.record` values.
3. `src/agents/notification_agent.py` — `notify(zone_id: str, message: str) -> None`, Telegram-if-configured else console.

## Wiring into `src/orchestrator.py`

Replace the current stub (the `else` branch in `run_cycle` that prints "pending cloud escalation") with:
1. Call `cloud_reasoning_agent.decide(snapshot)`.
2. Pass both decisions to `consensus_agent.decide(...)`.
3. On agreement → `safety_rules.apply` → `actuator_agent.execute` → `metrics.record(..., "escalated_to_gemini", ...)`.
4. On disagreement/still-uncertain → `notification_agent.notify(...)` with both reasoning strings → `metrics.record(..., "escalated_to_human", ...)`, action stays `no_action`.

## Verification

Run `run-local-demo`'s steps again — Scenario 3 (ambiguous pest, both should agree to spray) and Scenario 4 (crafted to plausibly diverge) should now exercise the full escalation path instead of the stub message. If Scenario 4 doesn't actually produce a disagreement with the real models, adjust `data/scenarios.json`'s overrides rather than faking the consensus logic.
