# AgriGuard — Cost-Aware Multi-Agent Crop Monitoring & Response System

**Track:** Agents for Good (Agriculture)
**Competition:** AI Agents: Intensive Vibe Coding Capstone Project (Kaggle)
**Deadline:** July 6, 2026, 11:59 PM PT
**Author:** Veera

---

## 1. Problem Statement

Small/medium farms (our case: a 2-acre farm) lack affordable, autonomous systems to monitor crop health and respond to threats (water stress, pests, adverse weather) in real time. Cloud-only AI solutions are too expensive to run continuously on every sensor reading. AgriGuard solves this by using a **local, free model (Ollama) for routine decisions** and only calling an **expensive cloud model (Gemini) for ambiguous or high-stakes decisions**, with a human (the farm owner) as the final safety net when models disagree or are uncertain.

**Core value proposition:** Real-time, low-cost, safe autonomous farm management — with quantifiable cost savings vs. an all-cloud approach.

---

## 2. Scope for the Hackathon (Realistic 2-Day Build)

We do **not** have physical sensors/drones installed yet. This is explicitly a **simulated environment**:
- Sensor readings (soil moisture, pest/leaf health, weather, wind, power) are generated synthetically (randomized + scripted scenarios to demonstrate all code paths).
- Actuators (irrigation valve, pesticide drone) are **simulated** — actions are logged, not physically executed.
- This should be stated clearly and confidently in the submission write-up: the agent logic, decision architecture, and cost-tracking are fully real; only the physical I/O layer is mocked, and is designed to be swapped for real sensor/drone APIs later.

---

## 3. High-Level Architecture

```
        ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
        │Soil Sensor│ │Pest/Leaf  │ │Weather/   │ │Power      │
        │           │ │Cam Sensor │ │Wind Sensor│ │Supply Mon.│
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │             │             │             │
              └─────────────┴──────┬──────┴─────────────┘
                                    │ each sensor writes its
                                    │ latest reading independently
                                    ▼
                    ┌───────────────────────────┐
                    │   Sensor Aggregator Agent   │  (plain Python,
                    │  Maintains shared state:    │   no LLM call here)
                    │  {soil, pest, weather,      │
                    │   power} — always current   │
                    └──────────────┬──────────────┘
                                   │ ONE consolidated snapshot
                                   │ per decision cycle (e.g. every 60s)
                                   │ or per zone, if multi-zone
                                   ▼
                    ┌─────────────────────┐
                    │  Local Decision Agent│  (Ollama or llama.cpp,
                    │  Fast, free, always-on│  see Section 3a)
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
         confident / routine          uncertain / high-stakes
                 │                           │
                 ▼                           ▼
       ┌───────────────────┐      ┌───────────────────────┐
       │  Safety Rule Layer │      │  Cloud Reasoning Agent │
       │  (hard-coded limits)│     │  (Gemini API)          │
       └─────────┬──────────┘      └───────────┬────────────┘
                 │                              │
                 ▼                              ▼
                 └───────────► Consensus Agent ◄┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
            models AGREE                models DISAGREE
                 │                       or both uncertain
                 ▼                           ▼
       ┌───────────────────┐      ┌───────────────────────┐
       │  Actuator Agent    │      │  Notification Agent    │
       │  (simulated action)│      │  (alert farm owner)    │
       └────────────────────┘      └────────────────────────┘
                 │
                 ▼
       ┌───────────────────┐
       │  Logging / Metrics  │
       │  Dashboard          │
       └────────────────────┘

                    ┌──────────────────────────────────────┐
                    │      Landlord Telegram Concierge       │
                    │                                        │
                    │  ┌────────────────┐  ┌───────────────┐│
                    │  │ Query Agent     │  │ Scheduled      ││
                    │  │ (on-demand      │  │ Reporter Agent ││
                    │  │  "what's the    │  │ (every 2 hrs,  ││
                    │  │  status?")      │  │  auto push +   ││
                    │  │                 │  │  photo)        ││
                    │  └────────┬────────┘  └───────┬────────┘│
                    │           │                    │         │
                    │           ▼                    ▼         │
                    │     reads shared Aggregator + Metrics/    │
                    │     Logging state (Sections 3a, 9)        │
                    │     + latest camera snapshot (simulated)  │
                    └──────────────────┬─────────────────────┘
                                       │ Telegram Bot API
                                       │ (sendMessage / sendPhoto)
                                       ▼
                                 Farm Owner / Landlord
```

### 3a. How Multiple Sensors Feed a Single Model (Fan-In Pattern)

A common mistake is letting every sensor independently call the LLM whenever it has a new reading. This causes three problems: redundant/wasted model calls, race conditions (e.g., a spray decision made from pest data alone, unaware wind just spiked), and unpredictable concurrency load on Ollama. AgriGuard avoids this with a **fan-in aggregator**:

1. **Sensors never call the LLM directly.** Each sensor (real or simulated) simply writes its latest reading to a shared in-memory state (or a small local DB/Redis if you want persistence) on its own cadence.
2. **The Sensor Aggregator Agent** holds the single source of truth: `{soil_moisture, pest_risk, leaf_image_ref, wind_speed, wind_direction, power_available, forecast_rain}` — always reflecting the latest known value per field, timestamped.
3. **The Orchestrator triggers a decision cycle on a fixed interval** (e.g., every 60 seconds), or immediately if a sensor reports a value past a critical threshold (e.g., pest_risk spikes above 0.9) — an event-driven override on top of the polling loop.
4. **One consolidated request is sent to the Local Decision Agent per cycle** — not one per sensor. This is both more efficient and agronomically correct, since real decisions (e.g., "should I spray?") depend jointly on multiple signals at once.
5. **Multi-zone scaling:** if the 2-acre farm is split into multiple monitoring zones, each zone gets its own aggregated snapshot and its own decision request. These *can* run concurrently — this is where Ollama's `OLLAMA_NUM_PARALLEL` setting matters (see Section 3b) — but each zone's request is still a single consolidated call, not per-sensor.

This pattern is also your strongest technical talking point for judges: it shows deliberate systems design (reducing token/compute cost, avoiding race conditions) rather than a naive "call the LLM on every event" approach.

---

## 3b. Local Model Runtime: Ollama vs. llama.cpp — What to Actually Use

Both Ollama and llama.cpp can serve your local model. They matter for different phases of this project.

### For the Hackathon Demo (next 2 days): **Ollama**
- Fastest to set up and iterate on — you already have it working (`llama-server` via llama.cpp, but Ollama wraps this with less friction for switching models, prompts, and testing).
- Built-in concurrency handling out of the box: `OLLAMA_NUM_PARALLEL` controls how many requests a model handles at once (auto-selects 1 or 4 based on available memory); excess requests queue in FIFO order up to `OLLAMA_MAX_QUEUE` (default 512), then return a 503 if the queue is full.
- Recommended local model: **Gemma 4 (E4B)**, tag `gemma4:e4b` — confirmed locally via `ollama show`: 8.0B params, Q4_K_M quant, **9.6GB on disk**, 131072 context, capabilities `completion/vision/audio/tools/thinking`. Tool-calling covers the structured JSON decision output; vision covers the pest/leaf image path directly, no separate vision pipeline needed. Note this is a newer release outside training knowledge for verification beyond what's observable locally — the metadata above is what was actually pulled and inspected, not a spec-sheet claim.
- At 9.6GB, this leaves only ~6.4GB of headroom on a 16GB card for KV cache — less than the original ~6GB estimate assumed. **Verify actual VRAM usage with `ollama ps` / `nvidia-smi` under `OLLAMA_NUM_PARALLEL=3` before committing to a 3-zone demo** — 2 concurrent zones may be the safer starting point, scale up only if headroom confirms.
- Ollama also handles model load/unload automatically, which is convenient but adds cold-start latency (several seconds) the first time a model is called after being idle — worth noting as a bottleneck (Section 14).

### For a "Production/Field Deployment" Story (mention in write-up, don't necessarily build): **llama.cpp server**
- Lower overhead, finer control over context size, batching, and quantization — better suited to a resource-constrained edge device actually sitting on the farm (e.g., a small mini-PC or Jetson-class board), rather than your full desktop GPU workstation.
- `llama-server` supports continuous batching and precise control of `--parallel` (concurrent slots) and `--ctx-size`, letting you tune exactly how much VRAM/RAM each concurrent zone decision consumes — useful once you know your real hardware budget in the field.
- No automatic model unloading — the model stays resident, avoiding Ollama's cold-start reload penalty, which matters more for a 24/7 unattended field deployment than for a demo.
- **Recommendation for your submission:** build and demo on Ollama (faster, less risk before the deadline), but explicitly state in the write-up that the production deployment path is a llama.cpp server on lower-power edge hardware, since you already have hands-on experience building llama.cpp from source (this is a legitimate, technically credible "future work" point, not a hand-wave).

### 3b-i. Actual Submission Runtime: Ollama Runs Self-Contained Inside the Kaggle Kernel

**Decision:** the Kaggle notebook must be re-runnable end-to-end by judges without depending on your local GPU workstation. Local development happens on your own machine for fast iteration, but the *submitted* notebook installs and serves Ollama inside the Kaggle kernel itself, using Kaggle's free GPU quota (T4, 16GB).

Setup inside the notebook (first cells) — **idempotent: never blind-pull**:
```
!curl -fsSL https://ollama.com/install.sh | sh
!nohup ollama serve > /kaggle/working/ollama.log 2>&1 &
!sleep 5

# Check before pulling — `ollama pull` re-verifies/re-downloads layers even if the
# model is already present, which wastes minutes on every single re-run of the notebook.
MODEL="gemma3:4b"
if ! ollama list | awk '{print $1}' | grep -qx "$MODEL"; then
    ollama pull "$MODEL"
else
    echo "$MODEL already present locally — skipping pull"
fi
```
(Equivalent Python check if you prefer running this from a code cell instead of shell:
`subprocess.run(["ollama","list"])` output parsed for the model tag before conditionally calling `ollama pull`.)

Notes:
- **Two different caching problems, don't conflate them:**
  1. **Within a session** (re-running cells without restarting the kernel) — the `ollama list` check above is sufficient; the model stays loaded in `~/.ollama` for the rest of that container's life.
  2. **Across sessions** (every fresh "Save & Run All" / new kernel start spins up a clean container) — `~/.ollama` does **not** persist across sessions by default, so the check above will still trigger a fresh pull the first time in every new session. If minimizing repeated downloads across sessions matters (e.g. you're iterating on the notebook many times on demo day), attach the pulled model directory as a **Kaggle Dataset** (pull once locally or in one kernel run, save `~/.ollama/models` as dataset output, then mount that dataset as input and point `OLLAMA_MODELS` at its path on subsequent runs) so the pull step becomes a no-op check against already-mounted files instead of a network download.
  3. For the actual judged submission run, one full pull is expected and fine — the check above mainly protects your own iteration time on Day 1/2, not judge-facing behavior.
- Verify the Kaggle notebook's internet access is enabled (Settings → Internet: On) — required both for `ollama pull` and for the Gemini API escalation calls. Confirm this doesn't conflict with the competition's submission format (this is a capstone write-up notebook, not a no-internet code competition, but verify before demo day).
- Budget kernel session time: model pull is **~9.6GB** for `gemma4:e4b` (confirmed locally, larger than originally estimated) + serve startup + full scenario run — should still fit a single Kaggle session, but this is a bigger download than planned for, so time-box a test pull+run early on Day 1 rather than discovering a timeout/disk-quota issue on Day 2.
- Keep `local_decision_agent.py`'s Ollama host configurable (`OLLAMA_HOST` env var, default `http://localhost:11434`) so the exact same code runs against your local dev instance and the in-kernel instance without changes.
- If in-kernel Ollama setup turns out to be flaky close to the deadline, the fallback is the previously-considered plan: local run + recorded demo video + notebook as writeup. Don't burn more than a few hours on this before falling back — see Section 10 scope tiers.

---

## 3c. Landlord Telegram Concierge (Status Queries + Auto Reports with Photos)

This is a genuinely strong addition — it directly matches the **Concierge Agents** track language ("personal assistants that simplify everyday life... while keeping user data secure") even though your primary track is Agents for Good, and it makes the project feel complete rather than just a backend automation loop.

### Feature 1: On-Demand Status Queries
- The landlord messages the bot directly, e.g., *"What's the status of the farm?"* or *"What did you do today?"*
- **Query Agent** flow:
  1. Receives the Telegram message.
  2. Pulls the latest Aggregator snapshot (Section 3a) and recent entries from the Metrics/Logging store (Section 9).
  3. For simple factual asks ("current soil moisture?") → answers directly from the data, no LLM call needed (cheap, fast).
  4. For open-ended asks ("how's everything going?", "any concerns?") → passes the recent data window to the **local model** to generate a natural-language summary; only escalates to Gemini if the landlord's question requires deeper reasoning (e.g., "should I be worried about the pest situation?").
  5. Sends the response back via Telegram.

### Feature 2: Scheduled Auto-Reports Every 2 Hours
- **Scheduled Reporter Agent** runs on a timer (e.g., APScheduler or a simple cron-style loop in `orchestrator.py`).
- Every 2 hours, it:
  1. Gathers a summary of sensor readings and any actions taken since the last report.
  2. Grabs the latest camera snapshot per zone (simulated image for the demo — see below).
  3. Generates a short natural-language summary via the local model ("Zone 1: soil moisture stable, no action needed. Zone 2: irrigation triggered at 2:15pm due to low moisture.").
  4. Sends the summary text + photo(s) via Telegram's Bot API (`sendMessage` + `sendPhoto`, or `sendMediaGroup` for multiple images at once).

### Implementation Notes
- Telegram Bot API is well-suited for this — you've already used it in a past project (Zerodha/NSE alert bot), so the integration pattern is familiar.
- For the hackathon demo: since there's no real camera installed yet, use a small set of **sample farm/crop images** that get "captured" on schedule — clearly labeled as simulated in the write-up, same treatment as your sensor data.
- Keep the Query Agent and Scheduled Reporter Agent reading from the **same shared state** (Aggregator + Metrics Logger) that the decision-making agents use — don't create a second, separate data path. This keeps the "single source of truth" design clean and is a good architecture talking point.

### New Bottlenecks This Introduces (add to Section 12 mitigations)
| Bottleneck | Mitigation |
|---|---|
| Telegram Bot API rate limits (especially `sendPhoto`) | Batch multiple zone photos into one `sendMediaGroup` call per report cycle rather than separate messages per zone |
| Image size / bandwidth on poor rural internet | Compress/resize images before sending; fall back to text-only summary if photo upload fails, rather than blocking the whole report |
| Camera capture at night / low light (real deployment) | Out of scope for demo; note in write-up that low-light imaging (IR camera) is a real-world hardware consideration, not solved here |
| Landlord query arrives during a decision cycle (race condition) | Query Agent should read a snapshot copy of state, not block/interfere with the live decision loop |
| Over-reliance on LLM for every query increases cost | Route simple factual queries straight to data (no LLM call); only use the local/cloud model for genuinely open-ended questions (mirrors your existing cost-cascade philosophy) |

---

## 4. Agent Roles (Built on Google ADK — `google-adk`)

**Decision:** these agents are implemented as actual `google.adk` constructs, not just conceptually mirrored. Each LLM-backed agent is an ADK `LlmAgent`; the Local Decision Agent wraps Ollama via ADK's `LiteLlm` model wrapper (`LiteLlm(model="ollama_chat/gemma3:4b")`, since Ollama exposes an OpenAI-compatible endpoint LiteLLM already speaks); the Cloud Reasoning Agent uses ADK's native Gemini support directly. The Consensus Agent and Safety Rule Layer are plain deterministic Python (no LLM involved), invoked as ADK custom `Tool`/step functions rather than agents — this is deliberate, per Section 8: deterministic logic must not be delegated to a model. Orchestration across the fan-in cycle uses an ADK `Runner`/`SequentialAgent` (or custom `BaseAgent` for the polling+event-trigger loop, since ADK's built-in workflow agents assume a simpler linear handoff than the polling/threshold-override pattern here).

| Agent | Model / Tooling | Responsibility |
|---|---|---|
| Sensor Agent(s) | Python data generator (mock) | Each sensor independently emits readings on its own cadence |
| Sensor Aggregator Agent | Plain Python (no LLM) | Maintains latest shared state across all sensors; triggers decision cycles |
| Local Decision Agent | ADK `LlmAgent` + `LiteLlm` wrapper over Ollama (Gemma 4 E4B) | First-pass decision on the consolidated snapshot; flags uncertainty |
| Safety Rule Layer | Deterministic Python (ADK Tool/step, no LLM) | Hard limits models cannot override (e.g., no spraying above wind threshold) |
| Cloud Reasoning Agent | ADK `LlmAgent` with native Gemini model | Second opinion for ambiguous/high-stakes cases |
| Consensus Agent | Deterministic Python (ADK Tool/step, no LLM) | Compares Ollama + Gemini outputs; decides act / escalate to human |
| Actuator Agent | Simulated action executor | "Executes" irrigation/spraying, logs action |
| Notification Agent | Telegram Bot API (or console/log for demo) | Alerts farm owner on disagreement/uncertainty |
| Metrics/Logging | JSON/CSV logs + simple dashboard | Tracks cost savings, escalation rate, action history |
| Query Agent *(stretch — see Section 10)* | Telegram bot + local/cloud model | Answers landlord's on-demand status questions |
| Scheduled Reporter Agent *(stretch — see Section 10)* | Telegram bot + local model + sample images | Sends automatic status summary + photos every 2 hours |

**Required competition concepts this satisfies (need 3+):**
1. **Multi-agent system built on Google ADK** (real `google-adk` framework usage — `LlmAgent`, `LiteLlm`, `Runner` — not just a hand-rolled orchestrator mirroring the concepts)
2. **Security/safety feature** (human-in-the-loop escalation + hard-coded safety rule layer that overrides both models)
3. **Cost optimization / model routing** (local-first, Gemini-on-demand — a strong differentiator most submissions won't have)
4. *(Stretch, if Section 10's Must/Should tiers finish early)* **Conversational concierge interface** (Telegram Query Agent + Scheduled Reporter Agent — echoes the Concierge track's "safe, useful personal assistant" language even though you're submitting under Agents for Good)
5. *(Optional stretch)* MCP server — could wrap the Telegram bot or weather API as an MCP tool if time allows

---

## 5. Decision Logic (Core Loop)

```
1. Sensors independently write readings to the Sensor Aggregator Agent's
   shared state as they arrive (not synchronized, just latest-value wins
   per field).

2. On each decision cycle (fixed interval, e.g. every 60s, OR immediately
   if a sensor crosses a critical threshold), the Aggregator emits ONE
   consolidated snapshot, e.g.:
   {
     "timestamp": "...",
     "zone_id": "zone_1",
     "soil_moisture_pct": 18,
     "leaf_health_score": 0.62,
     "pest_risk_score": 0.71,
     "temperature_c": 34,
     "wind_speed_kmh": 22,
     "wind_direction": "NE",
     "power_available": true,
     "forecast_rain_next_6h": false
   }

3. Local Decision Agent (Ollama/llama.cpp) evaluates the snapshot against a prompt template
   → returns structured JSON:
   {
     "action": "irrigate" | "spray_pesticide" | "no_action" | "uncertain",
     "confidence": 0.0-1.0,
     "reasoning": "short explanation"
   }

4. IF confidence >= threshold (e.g. 0.85) AND action != "uncertain":
     → pass to Safety Rule Layer

5. ELSE (low confidence OR action == "uncertain" OR action is high-stakes
        like "spray_pesticide"):
     → send same snapshot + local model's tentative answer to Gemini for a second opinion

6. Gemini returns its own structured decision.

7. Consensus Agent compares local model vs Gemini:
   - If both agree on action → proceed to Safety Rule Layer
   - If they disagree → do NOT act → Notification Agent alerts farm owner
     with both opinions and reasoning, awaiting manual confirmation

8. Safety Rule Layer (non-negotiable, model-independent):
   - Block spraying if wind_speed_kmh > 15
   - Block spraying if power_available == false (for drone charge/ops)
   - Block irrigation if forecast_rain_next_6h == true
   - Any rule violation → downgrade to "no_action" + log reason,
     regardless of model consensus

9. Actuator Agent executes (simulated) approved action, logs result.

10. Metrics Logger records:
   - Decision source (local-only / escalated-to-gemini / human-escalated)
   - Estimated cost (assign $ per Gemini call, $0 for local)
   - Outcome
```

---

## 6. Repository / Project Structure

```
agriguard/
├── README.md                      # Project overview, setup, how to run
├── PROJECT_PLAN.md                # This file
├── requirements.txt                # incl. google-adk, litellm
├── .env.example                   # GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, OLLAMA_HOST, etc.
│
├── src/
│   ├── sensors/
│   │   ├── sensor_simulator.py     # Generates synthetic sensor events per sensor
│   │   └── aggregator_agent.py     # Shared state; builds consolidated snapshot per cycle
│   │
│   ├── agents/
│   │   ├── local_decision_agent.py # ADK LlmAgent + LiteLlm(ollama_chat/...) wrapper
│   │   ├── cloud_reasoning_agent.py# ADK LlmAgent with native Gemini model
│   │   ├── consensus_agent.py      # Deterministic agreement/disagreement logic (ADK tool/step)
│   │   ├── safety_rules.py         # Hard-coded deterministic safety limits (ADK tool/step)
│   │   ├── actuator_agent.py       # Simulated action executor
│   │   ├── notification_agent.py   # Telegram/console alert to farm owner
│   │   ├── query_agent.py          # STRETCH — landlord's on-demand Telegram questions
│   │   └── scheduled_reporter_agent.py # STRETCH — every-2-hour auto status + photo report
│   │
│   ├── media/
│   │   └── sample_farm_images/     # STRETCH — simulated camera snapshots per zone
│   │
│   ├── orchestrator.py             # ADK Runner / custom BaseAgent: polling + event triggers
│   ├── metrics.py                  # Cost/decision logging + summary stats
│   └── config.py                   # Thresholds, safety limits, model names,
│                                    # OLLAMA_NUM_PARALLEL / zone count settings
│
├── data/
│   ├── scenarios.json               # Scripted test scenarios (see Section 7)
│   └── logs/
│       └── decisions_log.csv        # Output log of all decisions/actions
│
├── notebooks/
│   └── kaggle_submission_notebook.ipynb  # Self-contained: installs+serves Ollama
│                                          # in-kernel (Section 3b-i), runs full demo,
│                                          # final Kaggle write-up
│
├── dashboard/
│   └── dashboard.py or .html        # Simple cost/decision visualization
│
└── demo/
    └── demo_script.md               # Step-by-step script for recording demo video
```

---

## 7. Test Scenarios to Script (for a Convincing Demo)

Build 5–6 hand-crafted scenarios in `scenarios.json` so the demo reliably shows every code path:

1. **Clear-cut irrigation need** → low soil moisture, no rain forecast → Ollama handles alone, high confidence, action taken.
2. **Clear-cut no-action** → healthy readings across the board → Ollama says no_action, no escalation.
3. **Ambiguous pest signal** → moderate pest_risk_score → Ollama uncertain → escalate to Gemini → both agree → spray approved.
4. **Model disagreement** → craft inputs where Ollama and Gemini plausibly diverge → Notification Agent alerts farm owner.
5. **Safety override** → models agree to spray, but wind_speed_kmh is high → Safety Rule Layer blocks it regardless.
6. **Power constraint** → drone action requested but power_available is false → blocked + logged.

---

## 8. Security / Safety Design (Write-up Talking Points)

- **Human-in-the-loop for disagreement/uncertainty** — no autonomous action when models don't agree.
- **Deterministic safety layer** — cannot be overridden by any LLM decision (wind speed, power, rain forecast checks are hard-coded, not model-judged).
- **Data minimization** — only the aggregated, structured snapshot (Section 3a) is sent to Gemini (cloud) on escalation — not a raw stream of every individual sensor reading, and not any personally identifying farm data.
- **Action confirmation logging** — every action (or blocked action) is logged with full reasoning trail for auditability.

---

## 9. Cost-Optimization Story (Your Differentiator)

Track and present in the final dashboard/notebook:
- **% of decisions resolved locally (Ollama only, $0 cost)**
- **% escalated to Gemini (with $ cost estimate based on token usage)**
- **% escalated to human (farm owner)**
- **Estimated cost if every decision had gone to Gemini directly** vs. **actual cost with cascading** → show the $ and % savings

This quantified comparison is the single most memorable slide/section for judges — most competing projects won't have this.

---

## 10. Build Plan (2 Days) — Must / Should / Could Tiers

Deadline is July 6, 11:59pm PT; today is July 4 — roughly 60 hours. Given that, scope is tiered up front so a slip triggers an automatic cut, not a re-plan under pressure. **Only move to the next tier once the current one works end-to-end.**

**Must-have (this is the submission if nothing else lands):**
- Repo structure, `requirements.txt` (incl. `google-adk`, `litellm`)
- `sensor_simulator.py` + `scenarios.json`
- `local_decision_agent.py` — ADK `LlmAgent` + `LiteLlm(ollama_chat/gemma3:4b)`, JSON-structured output parsing with a retry/fallback if the model returns malformed JSON
- `safety_rules.py` — hard-coded limits, deterministic
- `actuator_agent.py` — simulated execution + logging
- `orchestrator.py` — ADK-based loop: sensor → local decision agent → safety check → action → log
- In-kernel Ollama setup verified working inside an actual Kaggle notebook session (Section 3b-i) — do this early, it's the highest-uncertainty item
- Test end-to-end on Scenarios 1, 2, 5, 6 (no Gemini needed yet)

**Should-have (the differentiators — build if Must-have lands with time to spare):**
- `cloud_reasoning_agent.py` — ADK `LlmAgent` with Gemini
- `consensus_agent.py` — agree/disagree logic
- `notification_agent.py` — console/log alert is enough; Telegram only if trivial by this point
- Test Scenarios 3 and 4 (escalation + disagreement paths)
- `metrics.py` — cost/decision summary stats
- Simple `dashboard.py` (a matplotlib chart or HTML table is enough — don't over-build this)
- Demo video (3–5 min) walking through all 6 scenarios
- Kaggle notebook / submission write-up mapping to required concepts

**Could-have (cut first if behind schedule):**
- Telegram `query_agent.py` (on-demand landlord Q&A)
- Telegram `scheduled_reporter_agent.py` (2-hour auto photo reports)
- `sample_farm_images/` and the `sendMediaGroup` batching logic
- MCP server wrapper for Telegram/weather API

**Checkpoint:** if Must-have isn't fully working by end of Day 1, stop adding scope and spend Day 2 solely on hardening + the write-up — a small system that reliably runs all 6 scenarios beats a large one that half-works on demo day.

---

## 11. Submission Checklist

- [ ] Project demonstrates **3+ required concepts** (ADK-based multi-agent, security, cost-routing; concierge/MCP if stretch tier landed)
- [ ] Kaggle notebook installs and serves Ollama in-kernel and actually re-runs end-to-end (Section 3b-i) — not just a description of a local setup
- [ ] Clear README explaining problem, architecture, and how to run
- [ ] Demo video or GIF showing the system working end-to-end
- [ ] Explicit note that sensors/drones are simulated, with a clear path to real hardware integration
- [ ] Cost-savings metrics included and explained
- [ ] Code is organized, commented, and reproducible
- [ ] Track selected: **Agents for Good**
- [ ] Submitted before **July 6, 2026, 11:59 PM PT**

---

## 12. Bottlenecks & Mitigations

Being upfront about bottlenecks — and showing you've designed around them — is a strength in the write-up, not a weakness. Group them by category:

### A. Compute / Model Serving Bottlenecks
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Ollama queuing under load | Requests beyond `OLLAMA_NUM_PARALLEL` queue FIFO; queue full → 503 error | Keep one consolidated request per zone per cycle (Section 3a), not per-sensor; size `OLLAMA_NUM_PARALLEL` to your actual zone count |
| Cold-start latency | Ollama unloads idle models after ~5 min by default; reload takes several seconds | Set `keep_alive` to a longer duration (or `-1`) so the model stays resident during active monitoring hours |
| VRAM growth with parallel zones | Each concurrent decision slot consumes additional KV-cache VRAM | Budget VRAM per zone before scaling zone count; Gemma 4 E4B's actual footprint is 9.6GB (confirmed via `ollama show`, larger than first estimated), leaving only ~6.4GB headroom on a 16GB card — verify with `ollama ps` / `nvidia-smi` before assuming 3 parallel zones fit |
| Single GPU = single point of failure | Your entire local decision layer depends on one workstation | For hackathon, acceptable; for real deployment, note this as a resilience gap — fallback-to-cloud-only mode if local GPU is down |

### B. Connectivity Bottlenecks (Critical for a Real Farm)
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Rural/farm internet unreliability | Gemini calls and Telegram alerts require internet; farms often have weak/intermittent connectivity | Design Gemini escalation and notifications to **fail safe**: if the cloud call times out, default to "no_action" + queue the escalation for retry, never default to an unverified autonomous action |
| Gemini API rate limits / quota | Frequent escalations could hit rate limits during a pest outbreak (bursty load) | Cap and log escalation rate; if quota exceeded, fall back to the safety rule layer only + notify farm owner for manual judgment |

### C. Power Bottlenecks (You Explicitly Called This Out)
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Local compute needs power too | If the GPU workstation loses power, both local AND cloud-escalation decisions stop | Treat "system offline" as its own alert state — notify the farm owner via a separate low-power channel (SMS is more resilient than push/Telegram if internet is also down) |
| Actuator power constraints | Drone/pump need power to act even if a decision is made | Already modeled in Section 5 (`power_available` check in Safety Rule Layer) — keep this as a hard block, not a model judgment call |

### D. Sensor Data Quality Bottlenecks
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Sensor noise / drift / false readings | Cheap soil/pest sensors can give spurious spikes | Use a simple smoothing/debounce rule (e.g., require 2 consecutive readings past threshold) before triggering a decision cycle — mention this as a planned refinement even if not fully implemented in the demo |
| Vision model reliability outdoors | Lighting, occlusion, and image quality affect pest/leaf detection accuracy in the field | For the demo, simulate a range of image-quality/confidence scenarios rather than claiming production-grade accuracy |
| Stale data if a sensor fails silently | Aggregator may act on an old cached value indefinitely | Timestamp every field in the aggregator state; treat data older than N minutes as "unknown" and route to escalation/human rather than assuming it's still valid |

### E. Decision-Latency Bottlenecks
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Two sequential model calls (local → Gemini) add latency on escalation | Consensus requires both opinions before acting | Acceptable for irrigation/pesticide decisions (not sub-second time-critical), but call this out explicitly as a design tradeoff in the write-up: safety over speed |
| Fixed polling interval misses fast-developing issues | E.g., a rapid pest outbreak between cycles | Add the event-driven override mentioned in Section 3a: any sensor crossing a critical threshold triggers an immediate out-of-cycle decision, not just the scheduled poll |

### F. Cost Bottlenecks
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Escalation rate too high in practice | If confidence thresholds are miscalibrated, too many cases go to Gemini, eroding the cost-savings story | Tune the confidence threshold using your test scenarios (Section 7); report the actual observed escalation rate honestly in the write-up rather than an idealized number |

### G. Safety / Trust Bottlenecks
| Bottleneck | Why it happens | Mitigation |
|---|---|---|
| Over-trusting model consensus | Two models agreeing doesn't guarantee correctness (correlated errors) | Keep the deterministic Safety Rule Layer as a non-negotiable final gate regardless of model agreement — already in your design (Section 5, step 8) |
| Alert fatigue for the farm owner | Too many notifications reduce trust and response rate | Only notify on genuine disagreement/uncertainty or system-offline states, not on every routine action |

---

## 13. Future Improvements (Post-Hackathon, for Your Own Roadmap)

- Replace simulated sensors with real IoT sensor integration (soil moisture probes, cameras + a vision model for pest detection)
- Replace simulated actuator with real drone/irrigation valve APIs
- Fine-tune the local model on real farm decision logs (ties into your existing LoRA/Unsloth interest)
- Add a proper MCP server wrapping weather API + Telegram, for a cleaner "MCP servers" story
- Expand safety rules based on real agronomic guidelines (consult actual pesticide safety data sheets)
- Add a proper time-series dashboard (Grafana or a small web app) instead of a static summary

---

## 14. Notes / Open Questions to Resolve While Building

- Confirm exact confidence threshold for escalation (start with 0.85, tune based on demo scenarios)
- Decide crop type / pest type to reference specifically (make the scenarios concrete — e.g., "tomato crop, aphid risk" — judges respond well to specificity over generic placeholders)
- Confirm Gemini model/endpoint and rate limits before demo day to avoid last-minute API issues
- Decide number of simulated zones (2–3 is realistic for a 2-acre farm) and set `OLLAMA_NUM_PARALLEL` accordingly
- Confirm whether to mention llama.cpp production path in write-up only, or actually build a small llama.cpp comparison for extra credibility (time-permitting, only after Must+Should tiers are done)
- Confirm exact small Ollama model tag (e.g. `gemma3:4b`) that (a) supports tool-calling/structured output well enough via ADK's `LiteLlm` wrapper, and (b) pulls quickly enough inside a Kaggle kernel session — test this on Day 1, not Day 2
- Confirm `google-adk`'s `LiteLlm` wrapper correctly round-trips structured JSON output from an Ollama-served model before committing to it as the Local Decision Agent's interface — have a plain-`requests`-to-Ollama fallback in mind if it doesn't
- Confirm Kaggle notebook internet access is enabled and permitted for this submission format (needed for `ollama pull` and Gemini API calls)
