---
name: check-scope-status
description: Audit the current agriguard/ repo against the Must/Should/Could tiers in AgriGuard_Project_Plan.md Section 10, report what's done vs. missing, and recommend the next single task given how much time is left before the July 6 11:59pm PT deadline.
---

# Check Scope Status

A status/planning check, not a build task — use this when picking up the project after a break, or when deciding what to work on next. Read `AgriGuard_Project_Plan.md` Section 10 (Must/Should/Could tiers) as the source of truth for what "done" means, then verify against actual files, not assumptions.

## Steps

1. Ask the user (or infer from system context) the current date/time to compute hours remaining until July 6, 2026, 11:59pm PT.

2. Check Must-have tier completion by verifying each item actually exists and works, not just that a file is present:
   - `src/config.py`, `requirements.txt`, `.env.example` — exist?
   - `src/sensors/sensor_simulator.py`, `aggregator_agent.py` — exist and importable?
   - `src/agents/local_decision_agent.py` — exists; has it actually been run against a live Ollama instance successfully (check for recent entries in `data/logs/decisions_log.csv` with `decision_source == "local"`), or only compiled/never executed?
   - `src/agents/safety_rules.py`, `actuator_agent.py` — exist?
   - `src/orchestrator.py` — does `run_scripted_scenarios()` complete without error end-to-end?
   - In-kernel Ollama verified working in an actual Kaggle notebook session yet? (Check for `notebooks/kaggle_submission_notebook.ipynb` and whether it's been run on Kaggle, not just drafted.)

3. Check Should-have tier: `cloud_reasoning_agent.py`, `consensus_agent.py`, `notification_agent.py`, `metrics.py` (already built), `dashboard/`, demo video, notebook write-up — which exist, which are stubs, which actually work.

4. Check Could-have tier: `query_agent.py`, `scheduled_reporter_agent.py`, `sample_farm_images/`, MCP wrapper — likely still unbuilt; that's expected and fine per Section 10's explicit prioritization.

5. Report as a punch list: done / partial-or-untested / missing, grouped by tier.

6. Recommend exactly one next action based on the Section 10 checkpoint rule: if Must-have isn't fully working, that's the only thing to work on — don't recommend Should/Could-have items yet. If Must-have is solid, recommend `build-cloud-escalation`, then `build-kaggle-notebook` (this one has the highest schedule risk per Section 3b-i and should not be left until last), then only mention `add-telegram-concierge` as optional with remaining time.

Keep the report concise — a punch list plus one recommended next step, not a full re-read of the plan back to the user.
