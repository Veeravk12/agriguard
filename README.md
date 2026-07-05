# AgriGuard

Cost-aware multi-agent crop monitoring and response system. A free local model
(Ollama) handles routine decisions; an expensive cloud model (Gemini) is only
called in when a decision is uncertain or high-stakes; a deterministic safety
layer has the final say over both; and a human farm owner is notified over
Telegram whenever the two models disagree.

Track: **Agents for Good** (Agriculture) — Kaggle "AI Agents: Intensive Vibe
Coding Capstone Project".

## Course concepts demonstrated

| Concept | Where |
|---|---|
| Multi-agent system (ADK) | `src/agents/` — 7 ADK-based/deterministic agents cooperating in a cost-aware cascade: `local_decision_agent.py` (Ollama), `cloud_reasoning_agent.py` (Gemini), `consensus_agent.py`, `safety_rules.py`, `actuator_agent.py`, `notification_agent.py`, `query_agent.py`, `chat_agent.py` |
| Security features | `safety_rules.py` is plain deterministic Python that no model — and no human Telegram reply — can override; secrets are loaded from `.env` (gitignored) via `src/config.py`, never hardcoded; `.env.example` ships with placeholders only |
| Deployability | This README gives full local setup instructions (Ollama, Python deps, `.env` config); `run.sh` is a single command to start continuous operation |

That's 3 of the 6 listed concepts, comfortably meeting the "at least 3" requirement.

## For reviewers

This runs against local infrastructure (Ollama, and optionally a personal
Gemini API key / Telegram bot), so there's no hosted public demo — this
repository is the required "public project link," with full setup below.
The demo video covers the same walkthrough end to end if you'd rather watch
it than run it locally.

## Status

Built and verified end-to-end against live Ollama, Gemini, and Telegram:

- Sensor simulation + fan-in aggregator (`src/sensors/`)
- Local Decision Agent (Ollama via ADK) and Cloud Reasoning Agent (Gemini via
  ADK), both structured-output, both fail safe on malformed/failed responses
- Deterministic Consensus Agent and Safety Rule Layer — no LLM can override
  the safety layer, including a human's Telegram reply
- Simulated actuator, cost/decision metrics, and a self-refreshing HTML
  dashboard with live agent/bot status and a full per-cycle activity trace
- Telegram notifications with a numbered reply menu — replying resolves the
  pending decision through the real safety layer and logs it distinctly
  (`decision_source="human_confirmed"`)
- Free-form chat with the local model over the same Telegram bot (`chat_agent.py`)
  — answers questions using current conditions and recent decisions as
  context, and proactively mentions any decision awaiting a reply
- A continuous live-monitoring mode (`src/live_monitor.py`) with background
  sensor writes, a bounded Gemini call budget per session, and guaranteed
  human-in-the-loop demo escalations so the whole loop is visible without
  spending real API quota

Note: Gemini's free tier caps `gemini-2.5-flash` at 20 requests/day per
Google Cloud project. If you see `escalated_to_human` with a "Cloud
Reasoning Agent call failed" reasoning message, that's the quota, not a
bug — the fail-safe design is working as intended.

## Project layout

```
run.py                  One-shot scripted demo: 6 fixed scenarios, then exits
run.sh                  Starts continuous live monitoring (recommended)

src/
  config.py             Env-driven settings (Ollama, Gemini, Telegram, safety limits)
  orchestrator.py        One decision cycle: snapshot -> local -> (escalate?) -> safety -> actuator
  live_monitor.py         Continuous mode: background sensors, decision loop, Telegram listener
  metrics.py              Cost/decision CSV log + summary stats
  trace_logger.py         Per-cycle agent activity log (for the dashboard)
  status_check.py         Live health checks for Ollama/Gemini/Telegram
  demo_notification.py    Sends one demo Telegram alert on illustrative decisions

  agents/
    local_decision_agent.py   Ollama, always-on, first-pass decision
    cloud_reasoning_agent.py  Gemini, second opinion on escalations
    consensus_agent.py        Deterministic agree/disagree check
    safety_rules.py            Deterministic safety gate (wind, power, rain)
    actuator_agent.py          Simulated actuator
    notification_agent.py      Telegram/console alerts, numbered reply menu
    query_agent.py              Parses Telegram replies (menu number or keyword), status queries
    chat_agent.py                Free-form chat with the local model

  sensors/
    sensor_simulator.py    Synthetic sensor readings
    aggregator_agent.py     Latest-value-wins snapshot per zone

dashboard/dashboard.py    Generates the self-contained HTML dashboard
data/scenarios.json        The 6 fixed scenarios used by run.py
```

## Setup

1. Install [Ollama](https://ollama.com) locally and pull the model:
   ```
   ollama pull gemma4:e4b
   ollama serve
   ```
2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in:
   - `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/apikey)
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — optional but needed for
     notifications and chat. Message [@BotFather](https://t.me/BotFather) on
     Telegram, run `/newbot`, and it gives you the token. For the chat ID,
     message your new bot once, then visit
     `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`
     from the JSON response.

## Running it

**Continuous / live mode (recommended)** — sensors write in the background,
a decision cycle runs every 10s, the dashboard auto-refreshes, and (if
Telegram is configured) you can reply to alerts or just chat with the local
model:

```
./run.sh
```

Stop with Ctrl+C — it prints a final cost summary on exit.

**One-shot scripted demo** — runs the 6 fixed scenarios in `data/scenarios.json`
once and exits. Useful for a quick, reproducible sanity check, but there's no
reply listener, so Telegram replies during this won't do anything:

```
python run.py
```

**Dashboard only** (reads existing logs, doesn't run new scenarios):

```
python -m dashboard.dashboard
```

## Architecture at a glance

```
sensors --> aggregator --> Local Decision Agent (Ollama, free)
                                     |
                    confident & routine?  --yes--> Safety Rule Layer --> Actuator
                                     |
                                    no (low confidence / uncertain / high-stakes)
                                     v
                          Cloud Reasoning Agent (Gemini)
                                     v
                            Consensus Agent (deterministic)
                             /                        \
                          agree                     disagree
                            v                            v
                  Safety Rule Layer --> Actuator    Telegram alert --> farm owner
                                                       (numbered menu reply,
                                                        still passes through
                                                        the Safety Rule Layer)
```

The Safety Rule Layer is plain deterministic Python, not a model, and applies
identically whether the action came from a model consensus or a human's
Telegram reply — nothing can talk it out of blocking an unsafe action.

## Future improvements

- **Workflow automation via n8n** — route notifications and human-in-the-loop
  decisions through an n8n workflow instead of talking to the Telegram API
  directly, so the same alert can fan out to email/Slack/SMS, or trigger a
  downstream action (e.g. auto-ordering more pesticide) without touching this
  codebase.
- **MCP server wrapper** — expose the agents as MCP tools so other AI clients
  can query farm status or trigger the same safety-gated actions, instead of
  Telegram being the only interface.
- **Real sensor/actuator hardware** — swap the simulated sensor readings and
  actuator calls for real IoT devices (soil probes, a drone control API);
  the decision cascade and safety layer don't need to change at all.
- **Multi-zone scaling** — `config.py` already models zones as a list;
  `live_monitor.py` currently only runs one. Running several zones
  concurrently, each on its own decision cadence, is a natural next step for
  a real multi-field farm.
- **Computer vision pest detection** — replace the synthetic pest risk score
  with real image classification on camera feed input.
- **Persistent storage** — move from CSV/JSONL logs to a proper database for
  historical analytics across many sessions, instead of per-run log files.
- **Conversational memory** — the chat agent currently treats every Telegram
  message independently; carrying session context across messages would
  let it handle natural follow-up questions.
