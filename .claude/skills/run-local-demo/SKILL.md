---
name: run-local-demo
description: Run AgriGuard's scripted-scenario demo locally against Ollama (Must-have tier) — verifies Ollama is serving, the model is pulled, runs all 6 scenarios through the orchestrator, and reports the cost summary.
---

# Run Local Demo

Runs the current Must-have tier of AgriGuard (`kaggle_project/agriguard/`) end-to-end against your local Ollama install. Use this to verify the core loop after any change to `src/agents/*`, `src/sensors/*`, or `src/orchestrator.py`.

Working directory for all commands: `kaggle_project/agriguard/`.

## Steps

1. Confirm Ollama is running and the model is present — don't blind-pull (see the project plan, Section 3b-i, for why):
   ```
   ollama list
   curl -s http://localhost:11434/api/version
   ```
   If the model tag from `.env`/`config.py` (`OLLAMA_MODEL`, currently `gemma4:e4b`) isn't in `ollama list`, pull it once: `ollama pull <tag>`. If the server isn't responding, start it: `ollama serve &`.

2. Ensure Python deps are installed: `pip install -r requirements.txt` (only if `google-adk`/`litellm` aren't already importable).

3. Run the scripted scenarios:
   ```
   python -m src.orchestrator
   ```
   This runs all 6 scenarios from `data/scenarios.json` (Section 7 of the plan) through one decision cycle each and prints the cost summary at the end (`src/metrics.summary()`).

4. Sanity-check the output against expected behavior per scenario (Section 7):
   - Scenario 1 (clear-cut irrigation): local-only, `irrigate`
   - Scenario 2 (clear-cut no-action): local-only, `no_action`
   - Scenario 3 (ambiguous pest) and Scenario 4 (model disagreement): currently fall into the "pending cloud escalation" stub in `orchestrator.run_cycle` since Gemini/consensus aren't wired in yet (Should-have tier — see the `build-cloud-escalation` skill) — expect `no_action` + a printed "pending cloud escalation" message, not a crash.
   - Scenario 5 (wind safety override) and Scenario 6 (power constraint): only reach the safety-rule gate if the local model is confident and non-"uncertain" — check `safety_rules.apply` actually downgrades to `no_action` with the right `block_reason`.

5. If `local_decision_agent.decide()` returns `action: "uncertain", reasoning: "local model returned non-JSON output: ..."` for scenarios that should be clear-cut, the prompt or the model's output format needs adjusting — inspect the raw `reply_text` before assuming the ADK/LiteLLM wiring is broken.

6. Check `data/logs/decisions_log.csv` was appended correctly and `python -c "from src import metrics; print(metrics.summary())"` gives sane percentages.

Report back: which scenarios passed/failed, and the printed cost summary.
