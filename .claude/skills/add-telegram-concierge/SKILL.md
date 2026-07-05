---
name: add-telegram-concierge
description: Build AgriGuard's Could-have stretch tier — the landlord Telegram concierge (on-demand status Query Agent + every-2-hour Scheduled Reporter Agent with photos). Only start this if Must-have and Should-have tiers are already done with time to spare — this is the first thing to cut if behind schedule.
---

# Add Telegram Concierge (Could-have Stretch Tier)

Implements Section 3c of `AgriGuard_Project_Plan.md` — the Concierge-track crossover feature. **Do not start this unless `run-local-demo` (Must-have) and `build-cloud-escalation` (Should-have) are already working end-to-end.** Per Section 10's checkpoint rule: a small system that reliably runs all 6 scenarios beats a large one that half-works on demo day. If time is tight, skip this tier entirely and go straight to `build-kaggle-notebook`.

## Design constraints (from the plan)

- Reads from the **same shared state** the decision agents use (`SensorAggregator` + `metrics` log) — do not create a second, separate data path (Section 3c, "Implementation Notes").
- Query Agent: simple factual questions ("current soil moisture?") answer directly from aggregator/metrics data, **no LLM call**. Open-ended questions ("how's everything going?") go to the local model first; only escalate to Gemini for questions requiring deeper reasoning. This mirrors the cost-cascade philosophy — don't route every query through Gemini by default.
- Scheduled Reporter Agent runs on a timer (APScheduler or a simple loop) every 2 hours, gathers a summary + a sample image per zone from `src/media/sample_farm_images/` (already created, currently empty — add a handful of labeled sample crop/farm images), and sends via Telegram `sendMessage` + `sendPhoto`/`sendMediaGroup`.
- Race condition: the Query Agent must read a **snapshot copy** of aggregator state, not block or interfere with the live decision loop (Section 3c bottleneck table).
- If photo upload fails (bandwidth/rate limits), fall back to text-only summary rather than blocking the whole report (Section 3c bottleneck table).
- Explicitly label all images/camera data as simulated in any write-up text these agents produce, consistent with the rest of the project's honesty about what's mocked (Section 2).

## Files to create

1. `src/agents/query_agent.py` — Telegram webhook/polling handler; `handle_message(text: str) -> str` that checks for simple factual patterns first, else routes to local/cloud model.
2. `src/agents/scheduled_reporter_agent.py` — timer loop; builds summary text via the local model, grabs a sample image per zone, sends via Telegram Bot API.
3. Sample images in `src/media/sample_farm_images/` (a handful, clearly farm/crop photos, labeled by zone).
4. Wire both into `src/orchestrator.py` or a small `src/telegram_bot.py` entry point — don't bury Telegram polling inside the main decision-cycle loop; run it as a separate concern reading the same shared state.

## Verification

Manually message the bot with a factual question (should answer with no LLM latency) and an open-ended question (should show local-model reasoning, escalating to Gemini only if you ask something genuinely ambiguous). Let one scheduled report cycle fire and confirm text + photo arrive together, and that a simulated photo-send failure falls back to text-only instead of throwing.
