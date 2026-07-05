# AgriGuard Demo Script

Two options depending on how much time you have: a 3-5 min scripted
walkthrough (deterministic, safe to record multiple takes), or a longer live
demo that shows the Telegram human-in-the-loop and chat features for real.

## Option A — Scripted walkthrough (3–5 min)

Walks through all 6 scripted scenarios end-to-end. Record terminal + a
browser tab with `dashboard/report.html` open. No editing required — the
system's own console output carries the narration.

### Before recording

```
cd agriguard
source .venv/bin/activate
ollama list | grep gemma4:e4b   # confirm model is pulled
curl -s http://localhost:11434/api/version   # confirm ollama serve is up
```

Have two windows ready: a terminal (full screen) and a browser tab on
`dashboard/report.html` (generated at the end).

### 0:00 – Problem statement (15s, talk over a static title card or README)

"Small farms can't afford to run cloud AI on every sensor reading. AgriGuard
uses a free local model for routine decisions, and only calls an expensive
cloud model — Gemini — when a decision is uncertain or high-stakes. A
deterministic safety layer and a human farm owner are the final backstops."

### 0:15 – Run the demo

```
python run.py
```

This clears old logs, runs all 6 scenarios, and generates the dashboard —
one command. Narrate each scenario as it prints:

- **Scenario 1 — clear_cut_irrigation_need**: "Soil moisture is critically low,
  no rain forecast. The local model alone decides to irrigate — no cloud call,
  zero cost."
- **Scenario 2 — clear_cut_no_action**: "Healthy readings across the board.
  Local model confidently says no action needed."
- **Scenario 3 — ambiguous_pest_signal**: "High pest risk is treated as
  high-stakes by design — even though the local model is confident, spraying
  pesticide always gets a second opinion from Gemini before proceeding. Watch
  the `escalating to Cloud Reasoning Agent` line."
- **Scenario 4 — cloud_escalation_consensus**: "Another high-stakes case —
  local and cloud both weigh in, agree, and the spray is approved."
- **Scenario 5 — safety_override_wind**: "Both models agree spraying is
  warranted, but wind speed is above the safety threshold. The deterministic
  safety layer blocks it regardless of what the models decided — no LLM can
  override this."
- **Scenario 6 — power_constraint**: "Same pattern, this time blocked because
  the drone has no power available."

### ~1:30 – Cost summary

Point at the `=== Cost summary ===` block printed at the end: percentage of
decisions resolved locally (free) vs. escalated to Gemini vs. escalated to a
human, and the actual cost vs. the hypothetical cost if every decision had
gone straight to Gemini.

### ~2:00 – Dashboard

Open `dashboard/report.html` in a browser: agent/bot status panel, stat
tiles, the decision-source breakdown bars, the cascading-vs-all-cloud cost
comparison, the full per-cycle agent trace, and the decision log table.

### ~2:45 – Architecture & safety talking points (30–45s)

- Fan-in pattern: sensors never call the LLM directly; one consolidated
  snapshot per cycle (avoids race conditions and redundant calls).
- Safety Rule Layer is plain deterministic Python — not a model — so it can't
  be argued or reasoned around. This applies equally to a human's Telegram
  reply, not just model decisions.
- Human-in-the-loop: any model disagreement or mutual uncertainty blocks
  action and notifies the farm owner over Telegram instead of guessing.

### ~3:15 – Close

"Everything physical here — sensors, irrigation valve, pesticide drone — is
simulated for the demo, clearly logged as such. The decision architecture,
safety layer, and cost-cascade logic are fully real and are the parts that
carry over unchanged to a real deployment."

### Notes for recording

- If a run happens to escalate to Gemini and the free-tier daily quota (20
  requests/day for `gemini-2.5-flash`) is exhausted, the system fails safe:
  it logs `escalated_to_human` and prints a notification rather than crashing
  or guessing. That's expected, safe behavior — mention it if it comes up,
  don't treat it as a bug.
- `python run.py` clears old logs itself at the start of each run, so takes
  are reproducible without any manual cleanup between them.

## Option B — Live mode with Telegram (5–8 min)

Shows the continuous monitoring loop and the parts a scripted run can't:
real-time sensor writes, a live-updating dashboard, and actually resolving a
disagreement (or just chatting) over Telegram.

```
./run.sh
```

- Open the printed dashboard link — it refreshes on its own every 10s.
- Narrate the background sensor writes and decision cycles as they print.
  Point out the occasional `[PEST SPIKE]` reading — the simulator injects
  these periodically so escalations actually happen live, instead of hoping
  for one by chance.
- When a disagreement alert lands on Telegram, show the numbered menu (e.g.
  "1. Spray pesticide  2. No action") and reply with a number on your phone.
  Point out the confirmation message that comes back, and that the decision
  now shows up in the dashboard trace as `human_confirmed`.
- Text the bot something conversational, like "hi" or "how's zone 1 doing?" —
  show the natural-language reply from the local model, using live sensor
  data as context. This never touches the Gemini quota.
- Stop with Ctrl+C and show the final cost summary: human-in-the-loop demos
  shown, real Gemini calls used, and any decisions left pending.
